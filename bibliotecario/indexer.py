from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from .embeddings import EmbeddingService
from .universal_reader import UniversalDocumentReader, DocumentChunk

logger = logging.getLogger(__name__)

# Extensões suportadas (agora gerenciadas pelo UniversalDocumentReader)
SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".txt", ".md", ".py", ".json", ".yaml", ".yml", ".js", ".ts",
    ".csv", ".rtf", ".html", ".htm", ".pptx", ".xlsx", ".xlsm", ".odt", ".ods", ".odp",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp",
    ".mp4", ".avi", ".mkv", ".webm", ".mov", ".flv",
    ".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac",
}


@dataclass(slots=True)
class IndexedChunk:
    chunk_id: str
    text: str
    source_path: str
    extension: str
    metadata: dict | None = None  # Metadados adicionais do documento


class LocalDocumentIndexer:
    def __init__(
        self, 
        docs_dir: str, 
        embeddings: EmbeddingService, 
        chunk_size: int = 1200, 
        overlap: int = 150,
        enable_ocr: bool = False,
    ) -> None:
        self.docs_dir = Path(docs_dir)
        self.embeddings = embeddings
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunks: list[IndexedChunk] = []
        self._snapshot: dict[str, float] = {}
        
        # Inicializa o leitor universal com suporte a múltiplos formatos
        self.reader = UniversalDocumentReader(
            chunk_size=chunk_size,
            overlap=overlap,
            enable_ocr=enable_ocr,
            enable_transcription=False,  # Pode ser habilitado no futuro
        )

    def _extract_text(self, path: Path) -> tuple[str, dict]:
        """
        Extrai texto de um arquivo usando o leitor universal.
        Retorna tupla (texto, metadados).
        """
        ext = path.suffix.lower()
        
        # Usar o leitor universal para todos os formatos
        try:
            text, metadata = self.reader.extract_text(path)
            return text or "", metadata
        except Exception as exc:
            logger.warning("Falha extraindo %s: %s", path, exc)
            return "", {}

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
        """
        Reconstrói o índice de documentos usando o leitor universal.
        Agora suporta múltiplos formatos de arquivo automaticamente.
        """
        chunks: list[IndexedChunk] = []
        snapshot = self._compute_snapshot()
        
        for raw_path in sorted(snapshot.keys()):
            path = Path(raw_path)
            text, metadata = self._extract_text(path)
            
            if not text:
                logger.debug("Nenhum texto extraído de %s", path)
                continue
            
            # Usar o método de chunking do leitor universal para consistência
            doc_chunks = self.reader.split_into_chunks(text, metadata)
            
            for chunk in doc_chunks:
                chunks.append(
                    IndexedChunk(
                        chunk_id=chunk.chunk_id,
                        text=chunk.text,
                        source_path=chunk.source_path,
                        extension=chunk.extension,
                        metadata=chunk.metadata,
                    )
                )
        
        self._snapshot = snapshot
        self.chunks = chunks
        logger.info("Indexador local reconstruído: %s chunks (de %s arquivos)", len(chunks), len(snapshot))
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
