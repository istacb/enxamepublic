from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from .embeddings import EmbeddingService

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".py", ".json", ".yaml", ".yml", ".js", ".ts"}


@dataclass(slots=True)
class IndexedChunk:
    chunk_id: str
    text: str
    source_path: str
    extension: str


class LocalDocumentIndexer:
    def __init__(self, docs_dir: str, embeddings: EmbeddingService, chunk_size: int = 1200, overlap: int = 150) -> None:
        self.docs_dir = Path(docs_dir)
        self.embeddings = embeddings
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunks: list[IndexedChunk] = []
        self._snapshot: dict[str, float] = {}

    def _extract_text(self, path: Path) -> str:
        ext = path.suffix.lower()
        try:
            if ext in {".txt", ".md", ".py", ".json", ".yaml", ".yml", ".js", ".ts"}:
                return path.read_text(encoding="utf-8", errors="ignore")
            if ext == ".pdf":
                try:
                    import fitz  # type: ignore

                    doc = fitz.open(path)
                    return "\n".join(page.get_text("text") for page in doc)
                except Exception:
                    return ""
            if ext == ".docx":
                try:
                    from docx import Document  # type: ignore

                    document = Document(path)
                    return "\n".join(p.text for p in document.paragraphs)
                except Exception:
                    return ""
        except Exception as exc:
            logger.warning("Falha extraindo %s: %s", path, exc)
        return ""

    def _split_chunks(self, content: str) -> list[str]:
        text = " ".join((content or "").split())
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]
        out: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            out.append(text[start:end])
            if end == len(text):
                break
            start = max(0, end - self.overlap)
        return out

    def _compute_snapshot(self) -> dict[str, float]:
        snap: dict[str, float] = {}
        if not self.docs_dir.exists():
            return snap
        for path in self.docs_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                snap[str(path)] = path.stat().st_mtime
        return snap

    def has_changes(self) -> bool:
        return self._compute_snapshot() != self._snapshot

    def rebuild(self) -> list[IndexedChunk]:
        chunks: list[IndexedChunk] = []
        snapshot = self._compute_snapshot()
        for raw_path in sorted(snapshot.keys()):
            path = Path(raw_path)
            content = self._extract_text(path)
            for i, part in enumerate(self._split_chunks(content)):
                digest = hashlib.sha1(f"{path}:{i}:{part[:80]}".encode("utf-8")).hexdigest()
                chunks.append(
                    IndexedChunk(
                        chunk_id=digest,
                        text=part,
                        source_path=str(path),
                        extension=path.suffix.lower(),
                    )
                )
        self._snapshot = snapshot
        self.chunks = chunks
        logger.info("Indexador local reconstruído: %s chunks", len(self.chunks))
        return chunks

    async def auto_reindex_loop(self, on_reindex) -> None:
        interval = int(os.getenv("INDEXER_INTERVAL_SECONDS", "120"))
        while True:
            try:
                if self.has_changes():
                    logger.info("Mudança detectada em documentos locais. Reindexando...")
                    chunks = self.rebuild()
                    await on_reindex(chunks)
            except Exception as exc:
                logger.exception("Falha no loop de indexação: %s", exc)
            await asyncio.sleep(interval)
