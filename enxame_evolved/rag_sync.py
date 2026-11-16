#!/usr/bin/env python3
"""
rag_sync.py — RAG Local Incremental CPU-First (FTS5 BM25) + Push ao Bibliotecário
==================================================================================
Resolve o requisito "iniciar o RAG local para enviar ao Bibliotecário" preservando
100% de compatibilidade com CPUs legadas (sem exigir AVX2 nem transferir documentos
pesados pela rede):
1. Indexa incrementalmente `documents/` em SQLite FTS5 BM25 (milissegundos em CPU).
2. Extrai um `TopicSketch` compacto (documentos, contagem de chunks e pesos TF-IDF
   dos termos principais do nó).
3. Envia via push (`POST /api/v1/rag/sketch`) para o Bibliotecário eleito (e mantém
   no catálogo global local caso esta máquina acumule o papel de Bibliotecário).
4. Roteia perguntas do enxame diretamente para os nós que possuem documentos sobre
   o tema consultado.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import sqlite3
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import aiohttp

logger = logging.getLogger("enxame.rag_sync")

STOPWORDS_PT_EN = frozenset(
    {
        "para", "com", "uma", "dos", "das", "nos", "nas", "por", "mais", "como",
        "mas", "foi", "são", "pelo", "pela", "seu", "sua", "seus", "suas", "isso",
        "este", "esta", "entre", "depois", "sem", "mesmo", "aos", "ter", "seus",
        "que", "não", "sim", "sobre", "quando", "onde", "qual", "quais", "the",
        "and", "for", "with", "that", "this", "from", "are", "was", "were", "have",
    }
)

TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".csv", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".py", ".js", ".ts", ".html", ".htm", ".log",
}


def _extract_tokens(text: str) -> list[str]:
    words = re.findall(r"[a-zA-ZÀ-ÿ0-9_]{3,}", (text or "").lower())
    return [w for w in words if w not in STOPWORDS_PT_EN and not w.isdigit()]


def _chunk_text(text: str, chunk_chars: int = 900, overlap: int = 150) -> list[str]:
    cleaned = re.sub(r"\n{3,}", "\n\n", (text or "")).strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_chars:
        return [cleaned]
    chunks: list[str] = []
    pos = 0
    step = max(200, chunk_chars - overlap)
    while pos < len(cleaned):
        piece = cleaned[pos : pos + chunk_chars].strip()
        if piece:
            chunks.append(piece)
        pos += step
    return chunks


@dataclass(slots=True)
class TopicSketch:
    """Resumo semântico/léxico leve enviado de cada Abelha ao Bibliotecário."""

    node_id: str
    machine_alias: str = ""
    host: str = "127.0.0.1"
    port: int = 8765
    doc_count: int = 0
    chunk_count: int = 0
    top_keywords: dict[str, float] = field(default_factory=dict)
    documents: list[dict[str, Any]] = field(default_factory=list)
    manifest_hash: str = ""
    updated_at: float = field(default_factory=time.time)
    # Campos legados de compatibilidade (kernel antigo / rota de cluster)
    domains: list[str] = field(default_factory=list)
    top_terms: list[str] = field(default_factory=list)
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.machine_alias:
            self.machine_alias = self.node_id
        if not self.manifest_hash and self.content_hash:
            self.manifest_hash = self.content_hash
        if not self.content_hash and self.manifest_hash:
            self.content_hash = self.manifest_hash
        if self.top_terms and not self.top_keywords:
            self.top_keywords = {str(t): 1.0 for t in self.top_terms[:40]}
        if self.top_keywords and not self.top_terms:
            self.top_terms = list(self.top_keywords.keys())[:40]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TopicSketch:
        kw = data.get("top_keywords") or {}
        if isinstance(kw, list):
            kw = {str(t): 1.0 for t in kw}
        return cls(
            node_id=str(data.get("node_id") or "unknown"),
            machine_alias=str(data.get("machine_alias", data.get("node_id") or "unknown")),
            host=str(data.get("host", "127.0.0.1")),
            port=int(data.get("port", 8765)),
            doc_count=int(data.get("doc_count", 0)),
            chunk_count=int(data.get("chunk_count", 0)),
            top_keywords={str(k): float(v) for k, v in kw.items()},
            documents=list(data.get("documents") or []),
            manifest_hash=str(data.get("manifest_hash", "") or data.get("content_hash", "")),
            updated_at=float(data.get("updated_at", time.time())),
            domains=[str(d) for d in (data.get("domains") or [])],
            top_terms=[str(t) for t in (data.get("top_terms") or [])],
            content_hash=str(data.get("content_hash", "") or data.get("manifest_hash", "")),
        )


class LocalCpuRagEngine:
    """
    Motor RAG local ultrarrápido em CPU usando SQLite FTS5 (BM25) + extração
    de PDF/DOCX/TXT/MD, sem exigir GPU nem AVX2.
    """

    def __init__(
        self,
        data_dir: Path | str | None = None,
        node_id: str = "bee-local",
        machine_alias: str = "",
        host: str = "127.0.0.1",
        port: int = 8765,
        db_path: Path | str | None = None,
        **kwargs: Any,
    ) -> None:
        if db_path is not None:
            self.db_path = Path(db_path)
            self.data_dir = Path(data_dir) if data_dir else self.db_path.parent
        else:
            self.data_dir = Path(data_dir) if data_dir else Path.cwd() / "enxame_data"
            self.db_path = self.data_dir / "local_rag_fts.db"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir = self.data_dir / "documents"
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.node_id = node_id or str(kwargs.get("node", "bee-local"))
        self.machine_alias = machine_alias or self.node_id
        self.host = host
        self.port = int(port)
        self._fts_ready = False
        self._last_sketch: TopicSketch | None = None
        self._init_db()

    # --- API pública esperada pelo EnxameKernel / Orquestrador ---

    def get_stats(self) -> dict[str, Any]:
        """Estatísticas do índice local (chaves `documents`/`chunks` garantidas)."""
        with self._connect() as conn:
            n_docs = conn.execute("SELECT COUNT(*) AS n FROM rag_files").fetchone()["n"]
            n_chunks = conn.execute("SELECT COUNT(*) AS n FROM rag_chunks").fetchone()["n"]
        return {
            "documents": int(n_docs),
            "chunks": int(n_chunks),
            "doc_count": int(n_docs),
            "chunk_count": int(n_chunks),
            "fts_enabled": self._fts_ready,
            "db_path": str(self.db_path),
            "docs_dir": str(self.docs_dir),
            "node_id": self.node_id,
        }

    def build_topic_sketch(self) -> TopicSketch:
        """Alias de `sync_local_documents` (reindexa e devolve o sketch)."""
        return self.sync_local_documents()

    def search(self, query: str, top_k: int = 5, **kwargs: Any) -> list[dict[str, Any]]:
        """Busca local com chaves `text`/`title` normalizadas (orquestrador)."""
        hits = self.search_local(query, top_k=top_k)
        for h in hits:
            h.setdefault("text", h.get("content", ""))
            h.setdefault("content", h.get("text", ""))
            h.setdefault("title", h.get("source", ""))
            h.setdefault("source", h.get("title", ""))
        return hits

    def list_documents(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT rel_path, size_bytes, chunk_count, top_terms_json, indexed_at"
                " FROM rag_files ORDER BY rel_path ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "path": r["rel_path"],
                "title": r["rel_path"],
                "size_bytes": int(r["size_bytes"]),
                "chunks": int(r["chunk_count"]),
                "top_terms": list((json.loads(r["top_terms_json"] or "{}")).keys())[:8],
                "indexed_at": float(r["indexed_at"]),
            }
            for r in rows
        ]

    def ingest_text(
        self,
        title: str = "Nota Local",
        text: str = "",
        source: str = "",
        domain: str = "geral",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Grava texto manual/upload em `documents/` e reindexa incrementalmente."""
        body = text or str(kwargs.get("content") or "")
        slug = re.sub(r"[^a-zA-Z0-9À-ÿ_-]+", "-", (title or "nota").strip().lower()).strip("-")[:60] or "nota"
        fname = f"{slug}-{hashlib.sha256(body.encode('utf-8')).hexdigest()[:8]}.md"
        target = self.docs_dir / fname
        header = f"# {title}\n\n_Fonte: {source or 'manual'} · Domínio: {domain}_\n\n"
        target.write_text(header + body, encoding="utf-8")
        sketch = self.sync_local_documents()
        return {
            "indexed": True,
            "title": title,
            "path": str(target),
            "source": source,
            "domain": domain,
            "doc_count": sketch.doc_count,
            "chunk_count": sketch.chunk_count,
        }

    def index_file(self, path: Path | str, collection: str = "geral") -> dict[str, Any]:
        """Indexa um arquivo avulso (copia para `documents/` quando externo)."""
        src = Path(path)
        if not src.exists() or not src.is_file():
            return {"indexed": False, "path": str(src), "error": "arquivo não encontrado"}
        try:
            src.resolve().relative_to(self.docs_dir.resolve())
            inside = True
        except (ValueError, OSError):
            inside = False
        if not inside:
            dest = self.docs_dir / src.name
            if dest.exists():
                dest = self.docs_dir / f"{src.stem}-{hashlib.sha256(str(src).encode()).hexdigest()[:6]}{src.suffix}"
            dest.write_bytes(src.read_bytes()[:4_000_000])
        sketch = self.sync_local_documents()
        return {
            "indexed": True,
            "path": str(src),
            "collection": collection,
            "doc_count": sketch.doc_count,
            "chunk_count": sketch.chunk_count,
        }

    def index_directory(self, path: Path | str, collection: str = "geral") -> dict[str, Any]:
        """Indexa recursivamente arquivos de texto de um diretório do projeto."""
        root = Path(path)
        if not root.exists() or not root.is_dir():
            return {"indexed_files": 0, "path": str(root), "error": "diretório não encontrado"}
        allowed = TEXT_EXTENSIONS | {".pdf", ".docx"}
        copied = 0
        for fp in sorted(root.rglob("*")):
            if not fp.is_file() or fp.name.startswith(".") or fp.suffix.lower() not in allowed:
                continue
            try:
                if fp.stat().st_size > 3_000_000:
                    continue
            except OSError:
                continue
            try:
                fp.resolve().relative_to(self.docs_dir.resolve())
                copied += 1
                continue
            except (ValueError, OSError):
                pass
            dest = self.docs_dir / f"{root.name}-{fp.name}"
            try:
                if not dest.exists():
                    dest.write_bytes(fp.read_bytes()[:2_000_000])
                copied += 1
            except OSError:
                continue
        sketch = self.sync_local_documents()
        return {
            "indexed_files": copied,
            "path": str(root),
            "collection": collection,
            "doc_count": sketch.doc_count,
            "chunk_count": sketch.chunk_count,
        }

    def close(self) -> None:
        """Fecha o motor (conexões SQLite são por operação; nada persistente)."""

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS rag_files (
                    rel_path TEXT PRIMARY KEY,
                    mtime REAL NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    top_terms_json TEXT NOT NULL,
                    indexed_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rag_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    rel_path TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    tokens TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_rag_chunks_path ON rag_chunks(rel_path);
                """
            )
            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(
                        chunk_id UNINDEXED,
                        rel_path,
                        content
                    );
                    """
                )
                self._fts_ready = True
            except sqlite3.OperationalError:
                self._fts_ready = False
            conn.commit()

    def _read_document_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in TEXT_EXTENSIONS:
            return path.read_text(encoding="utf-8", errors="ignore")[:1_500_000]
        if suffix == ".pdf":
            try:
                import fitz  # PyMuPDF
                with fitz.open(path) as doc:
                    return "\n".join(page.get_text("text") for page in doc)[:1_500_000]
            except Exception:
                pass
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    return "\n".join((p.extract_text() or "") for p in pdf.pages)[:1_500_000]
            except Exception:
                return ""
        if suffix == ".docx":
            try:
                import docx
                d = docx.Document(str(path))
                return "\n".join(p.text for p in d.paragraphs)[:1_500_000]
            except Exception:
                return ""
        return ""

    def sync_local_documents(self) -> TopicSketch:
        """Indexa incrementalmente arquivos novos/modificados/removidos e gera TopicSketch."""
        seen_paths: set[str] = set()
        now = time.time()

        with self._connect() as conn:
            existing = {
                r["rel_path"]: (float(r["mtime"]), int(r["size_bytes"]), str(r["sha256"]))
                for r in conn.execute("SELECT rel_path, mtime, size_bytes, sha256 FROM rag_files").fetchall()
            }

            for file_path in sorted(self.docs_dir.rglob("*")):
                if not file_path.is_file() or file_path.name.startswith("."):
                    continue
                if file_path.suffix.lower() not in (TEXT_EXTENSIONS | {".pdf", ".docx"}):
                    continue
                rel = str(file_path.relative_to(self.docs_dir))
                seen_paths.add(rel)

                try:
                    st = file_path.stat()
                except OSError:
                    continue

                prev = existing.get(rel)
                if prev and abs(prev[0] - st.st_mtime) < 0.5 and prev[1] == st.st_size:
                    continue

                raw_bytes = file_path.read_bytes()[:4_000_000]
                digest = hashlib.sha256(raw_bytes).hexdigest()[:24]
                if prev and prev[2] == digest:
                    continue

                text = self._read_document_text(file_path)
                chunks = _chunk_text(text)
                conn.execute("DELETE FROM rag_chunks WHERE rel_path = ?", (rel,))
                if self._fts_ready:
                    conn.execute("DELETE FROM rag_chunks_fts WHERE rel_path = ?", (rel,))

                doc_counter: Counter[str] = Counter()
                for idx, ch in enumerate(chunks):
                    cid = f"{digest[:10]}:{idx}"
                    toks = _extract_tokens(ch)
                    doc_counter.update(toks)
                    conn.execute(
                        "INSERT INTO rag_chunks (chunk_id, rel_path, chunk_index, content, tokens) VALUES (?, ?, ?, ?, ?)",
                        (cid, rel, idx, ch, " ".join(toks)),
                    )
                    if self._fts_ready:
                        conn.execute(
                            "INSERT INTO rag_chunks_fts (chunk_id, rel_path, content) VALUES (?, ?, ?)",
                            (cid, rel, ch),
                        )

                top_doc_terms = dict(doc_counter.most_common(20))
                conn.execute(
                    """
                    INSERT OR REPLACE INTO rag_files
                    (rel_path, mtime, size_bytes, sha256, chunk_count, top_terms_json, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (rel, st.st_mtime, st.st_size, digest, len(chunks), json.dumps(top_doc_terms, ensure_ascii=False), now),
                )

            # Remover arquivos apagados do disco
            stale = set(existing.keys()) - seen_paths
            for rel in stale:
                conn.execute("DELETE FROM rag_files WHERE rel_path = ?", (rel,))
                conn.execute("DELETE FROM rag_chunks WHERE rel_path = ?", (rel,))
                if self._fts_ready:
                    conn.execute("DELETE FROM rag_chunks_fts WHERE rel_path = ?", (rel,))

            conn.commit()

            # Construir TopicSketch consolidado
            frows = conn.execute("SELECT * FROM rag_files ORDER BY rel_path ASC").fetchall()

        global_tf: Counter[str] = Counter()
        doc_df: Counter[str] = Counter()
        docs_summary: list[dict[str, Any]] = []
        total_chunks = 0
        hash_acc = hashlib.sha256()

        for r in frows:
            total_chunks += int(r["chunk_count"])
            hash_acc.update(f"{r['rel_path']}:{r['sha256']}".encode("utf-8"))
            terms_map: dict[str, int] = json.loads(r["top_terms_json"] or "{}")
            for term, cnt in terms_map.items():
                global_tf[term] += int(cnt)
                doc_df[term] += 1
            docs_summary.append(
                {
                    "path": r["rel_path"],
                    "chunks": int(r["chunk_count"]),
                    "size_bytes": int(r["size_bytes"]),
                    "top_terms": list(terms_map.keys())[:8],
                }
            )

        n_docs = max(1, len(frows))
        weighted_kw: dict[str, float] = {}
        for term, tf in global_tf.most_common(80):
            idf = 1.0 + math.log((1.0 + n_docs) / (1.0 + doc_df[term]))
            weighted_kw[term] = round(tf * idf, 2)

        sketch = TopicSketch(
            node_id=self.node_id,
            machine_alias=self.machine_alias,
            host=self.host,
            port=self.port,
            doc_count=len(frows),
            chunk_count=total_chunks,
            top_keywords=weighted_kw,
            documents=docs_summary[:60],
            manifest_hash=hash_acc.hexdigest()[:16],
            updated_at=now,
        )
        self._last_sketch = sketch
        return sketch

    def ingest_bytes(self, filename: str, content_bytes: bytes) -> dict[str, Any]:
        """Salva documento enviado pelo usuário em documents/ e reindexa incrementalmente."""
        safe_name = Path(filename.replace("\\", "/")).name or f"doc_{int(time.time())}.txt"
        target = self.docs_dir / safe_name
        target.write_bytes(content_bytes)
        sketch = self.sync_local_documents()
        return {
            "saved_path": str(target),
            "filename": safe_name,
            "doc_count": sketch.doc_count,
            "chunk_count": sketch.chunk_count,
            "manifest_hash": sketch.manifest_hash,
        }

    def search_local(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Busca BM25 / FTS5 instantânea nos documentos locais deste nó."""
        tokens = _extract_tokens(query)
        if not tokens:
            return []

        with self._connect() as conn:
            if self._fts_ready:
                fts_q = " OR ".join(f'"{t}"*' for t in tokens[:8])
                rows = conn.execute(
                    """
                    SELECT chunk_id, rel_path, content, bm25(rag_chunks_fts) AS rank_score
                    FROM rag_chunks_fts
                    WHERE rag_chunks_fts MATCH ?
                    ORDER BY rank_score ASC
                    LIMIT ?
                    """,
                    (fts_q, top_k),
                ).fetchall()
                hits: list[dict[str, Any]] = []
                for idx, r in enumerate(rows):
                    # bm25() em SQLite retorna valores negativos (mais negativo = melhor)
                    raw_bm25 = abs(float(r["rank_score"] or 0.0))
                    # Combina cobertura de termos da pergunta + BM25 para score [0..1]
                    ch_toks = set(_extract_tokens(r["content"]))
                    coverage = len(set(tokens) & ch_toks) / max(1, min(len(tokens), 5))
                    conf = round(min(0.98, 0.45 + (0.35 * coverage) + min(0.20, raw_bm25 * 0.04) - (idx * 0.02)), 3)
                    hits.append(
                        {
                            "chunk_id": r["chunk_id"],
                            "source": r["rel_path"],
                            "content": r["content"],
                            "confidence": max(0.35, conf),
                        }
                    )
                return hits

            # Fallback caso FTS5 não esteja compilado
            where = " OR ".join(["tokens LIKE ?"] * min(4, len(tokens)))
            params = [f"%{t}%" for t in tokens[:4]] + [top_k]
            rows = conn.execute(
                f"SELECT chunk_id, rel_path, content FROM rag_chunks WHERE {where} LIMIT ?",
                params,
            ).fetchall()
            return [
                {
                    "chunk_id": r["chunk_id"],
                    "source": r["rel_path"],
                    "content": r["content"],
                    "confidence": 0.68,
                }
                for r in rows
            ]

    @property
    def current_sketch(self) -> TopicSketch:
        if self._last_sketch is None:
            return self.sync_local_documents()
        return self._last_sketch


class BibliotecarioGlobalCatalog:
    """
    Catálogo global mantido pelo Bibliotecário com os TopicSketches enviados
    por todas as máquinas do Enxame.
    """

    def __init__(self, data_dir: Path | str | None = None) -> None:
        base = Path(data_dir) if data_dir else Path.cwd() / "enxame_data"
        base.mkdir(parents=True, exist_ok=True)
        self.catalog_path = base / "bibliotecario_catalog.json"
        self.sketches: dict[str, TopicSketch] = {}
        self._load()

    def _load(self) -> None:
        if not self.catalog_path.exists():
            return
        try:
            raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            for node_id, sdict in raw.items():
                self.sketches[node_id] = TopicSketch.from_dict(sdict)
        except Exception as exc:
            logger.warning(f"Falha ao ler catálogo do Bibliotecário: {exc}")

    def _save(self) -> None:
        tmp = self.catalog_path.with_suffix(".json.tmp")
        payload = {nid: sk.to_dict() for nid, sk in self.sketches.items()}
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.catalog_path)

    def register_sketch(self, sketch: TopicSketch | dict[str, Any]) -> dict[str, Any]:
        sk = TopicSketch.from_dict(sketch) if isinstance(sketch, dict) else sketch
        self.sketches[sk.node_id] = sk
        self._save()
        return self.get_stats()

    def upsert_sketch(self, sketch: TopicSketch | dict[str, Any]) -> dict[str, Any]:
        """Alias de `register_sketch` usado pelo EnxameKernel."""
        return self.register_sketch(sketch)

    def get_catalog_stats(self) -> dict[str, Any]:
        """Alias de `get_stats` usado pelo EnxameKernel."""
        return self.get_stats()

    def find_candidate_nodes(self, query: str, exclude_node_id: str | None = None, top_n: int = 3) -> list[dict[str, Any]]:
        """Classifica em <2ms quais máquinas têm maior aderência temática à pergunta."""
        q_tokens = _extract_tokens(query)
        if not q_tokens:
            return []

        ranked: list[dict[str, Any]] = []
        for nid, sketch in self.sketches.items():
            if exclude_node_id and nid == exclude_node_id:
                continue
            if sketch.chunk_count <= 0:
                continue
            score = 0.0
            matched_terms: list[str] = []
            for qt in q_tokens:
                if qt in sketch.top_keywords:
                    score += sketch.top_keywords[qt]
                    matched_terms.append(qt)
                else:
                    # Prefixo parcial (ex.: tributo -> tributario)
                    for kw, w in sketch.top_keywords.items():
                        if len(qt) >= 4 and (kw.startswith(qt[:5]) or qt.startswith(kw[:5])):
                            score += w * 0.5
                            matched_terms.append(kw)
                            break
            if score > 0:
                ranked.append(
                    {
                        "node_id": nid,
                        "machine_alias": sketch.machine_alias,
                        "host": sketch.host,
                        "port": sketch.port,
                        "score": round(score, 2),
                        "matched_terms": matched_terms[:5],
                        "doc_count": sketch.doc_count,
                    }
                )
        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked[:top_n]

    def get_stats(self) -> dict[str, Any]:
        return {
            "nodes_indexed": len(self.sketches),
            "total_documents": sum(s.doc_count for s in self.sketches.values()),
            "total_chunks": sum(s.chunk_count for s in self.sketches.values()),
            "nodes": [
                {
                    "node_id": s.node_id,
                    "machine_alias": s.machine_alias,
                    "doc_count": s.doc_count,
                    "chunk_count": s.chunk_count,
                    "top_terms": list(s.top_keywords.keys())[:10],
                    "manifest_hash": s.manifest_hash,
                    "updated_at": s.updated_at,
                }
                for s in self.sketches.values()
            ],
        }


async def push_sketch_to_bibliotecario(
    sketch: TopicSketch | dict[str, Any],
    target_host: str | None = None,
    target_port: int = 8765,
    shared_secret: str | None = None,
    session: aiohttp.ClientSession | None = None,
    endpoint: str | None = None,
    cluster_token: str | None = None,
    **kwargs: Any,
) -> bool:
    """Envia o TopicSketch local ao nó Bibliotecário na LAN."""
    base = endpoint or kwargs.get("bib_endpoint") or target_host or ""
    base = str(base).strip()
    if base.startswith("http"):
        url = f"{base.rstrip('/')}/api/v1/cluster/sketch"
    else:
        host = base or "127.0.0.1"
        url = f"http://{host}:{target_port}/api/v1/cluster/sketch"
    payload = sketch.to_dict() if isinstance(sketch, TopicSketch) else dict(sketch)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    token = shared_secret or cluster_token or kwargs.get("token")
    if token:
        headers["X-Painel-Token"] = str(token)
    own_session = session is None
    sess = session or aiohttp.ClientSession()
    try:
        async with sess.post(
            url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=5.0)
        ) as resp:
            return resp.status == 200
    except Exception as exc:
        logger.debug(f"Push de TopicSketch para {url} falhou: {exc}")
        return False
    finally:
        if own_session:
            await sess.close()
