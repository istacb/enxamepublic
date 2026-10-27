"""RAG local por nó: indexa arquivos do próprio nó (exceto sistema) para
responder a partir do conhecimento local antes de recorrer à internet.

Indexação simples por palavras-chave + vetor de ocorrências (TF-lite).
Sem dependências externas (stdlib apenas). Guarda índice em SQLite.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# Diretórios e arquivos do sistema que nunca são indexados.
SYSTEM_DIRS = {
    'system32', 'syswow64', 'windows', 'program files', 'program files (x86)',
    'usr', 'lib', 'lib64', 'bin', 'sbin', 'etc', 'var', 'proc', 'sys',
    'dev', 'run', 'tmp', 'boot', 'root', 'home', 'opt', 'srv', 'mnt', 'media',
    'venv', '.venv', 'env', '__pycache__', '.git', '.github', '.opencode',
}
SYSTEM_PREFIXES = ('~', '.')  # arquivos ocultos e temporários
INDEX_EXTENSIONS = {
    '.txt', '.md', '.markdown', '.json', '.yaml', '.yml', '.py', '.js', '.ts',
    '.csv', '.log', '.html', '.htm', '.xml', '.toml', '.ini', '.cfg', '.conf',
    '.rst', '.org', '.tex',
}
MAX_FILE_BYTES = 2_000_000  # 2 MB por arquivo


@dataclass(slots=True)
class RagHit:
    found: bool
    snippets: list[str]
    sources: list[str]


class LocalRagIndex:
    """Índice local de um único nó. Cada nó indexa seus próprios arquivos."""

    def __init__(self, db_path: str, roots: list[str] | None = None) -> None:
        self.db_path = db_path
        self.roots = [Path(r) for r in (roots or []) if Path(r).exists()]
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            os.makedirs(os.path.dirname(self.db_path) or '.', exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute('PRAGMA journal_mode=WAL')
        return self._conn

    def _init_db(self) -> None:
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS docs (
                path TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                words TEXT NOT NULL,
                mtime REAL NOT NULL,
                indexed_at REAL NOT NULL
            )
            """
        )
        conn.execute('CREATE INDEX IF NOT EXISTS idx_docs_words ON docs(words)')
        conn.commit()

    def _should_index(self, path: Path) -> bool:
        parts = [p.lower() for p in path.parts]
        for part in parts:
            if part in SYSTEM_DIRS:
                return False
        name = path.name.lower()
        if name.startswith(SYSTEM_PREFIXES):
            return False
        if path.suffix.lower() not in INDEX_EXTENSIONS:
            return False
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                return False
        except OSError:
            return False
        return True

    def _iter_files(self) -> Iterable[Path]:
        for root in self.roots:
            try:
                for path in root.rglob('*'):
                    if path.is_file() and self._should_index(path):
                        yield path
            except Exception:
                continue

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [t for t in re.findall(r"[\wÀ-ú]+", text.lower()) if len(t) > 2]

    def index_files(self, force: bool = False) -> int:
        """Reindexa arquivos alterados ou novos. Retorna quantidade indexada."""
        conn = self._connect()
        import time

        now = time.time()
        indexed = 0
        for path in self._iter_files():
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            row = conn.execute('SELECT mtime FROM docs WHERE path = ?', (str(path),)).fetchone()
            if row and not force and abs(row[0] - mtime) < 1.0:
                continue
            try:
                content = path.read_text(encoding='utf-8', errors='ignore')[:MAX_FILE_BYTES]
            except Exception:
                continue
            words = ' '.join(self._tokenize(content))
            conn.execute(
                'INSERT OR REPLACE INTO docs (path, content, words, mtime, indexed_at) VALUES (?, ?, ?, ?, ?)',
                (str(path), content, words, mtime, now),
            )
            indexed += 1
        conn.commit()
        return indexed

    def search(self, query: str, limit: int = 5) -> RagHit:
        terms = self._tokenize(query)
        if not terms:
            return RagHit(False, [], [])
        # Uma palavra-chave já basta para match (como o local_search original,
        # mas limitado aos arquivos indexados deste nó).
        like_patterns = [f'%{t}%' for t in terms[:3]]
        conn = self._connect()
        where = ' OR '.join(['words LIKE ?'] * len(like_patterns))
        rows = conn.execute(
            f'SELECT path, content FROM docs WHERE {where} LIMIT ?',
            (*like_patterns, limit * 3),
        ).fetchall()

        snippets: list[str] = []
        sources: list[str] = []
        for path, content in rows:
            low = content.lower()
            idx = -1
            for t in terms:
                pos = low.find(t)
                if pos != -1:
                    idx = pos
                    break
            if idx == -1:
                continue
            start = max(0, idx - 120)
            end = min(len(content), idx + 180)
            snippet = content[start:end].replace('\n', ' ').strip()
            snippets.append(f'[{path}] {snippet}')
            sources.append(path)
            if len(snippets) >= limit:
                break
        return RagHit(bool(snippets), snippets, sources)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
