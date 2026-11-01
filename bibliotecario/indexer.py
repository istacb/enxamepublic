from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .embeddings import EmbeddingService
from .universal_reader import UniversalDocumentReader

logger = logging.getLogger(__name__)

# Extensões suportadas (agora gerenciadas pelo UniversalDocumentReader)
SUPPORTED_EXTENSIONS = {
    '.pdf',
    '.docx',
    '.txt',
    '.md',
    '.py',
    '.json',
    '.yaml',
    '.yml',
    '.js',
    '.ts',
    '.csv',
    '.rtf',
    '.html',
    '.htm',
    '.pptx',
    '.xlsx',
    '.xlsm',
    '.odt',
    '.ods',
    '.odp',
    '.jpg',
    '.jpeg',
    '.png',
    '.gif',
    '.bmp',
    '.tiff',
    '.tif',
    '.webp',
    '.mp4',
    '.avi',
    '.mkv',
    '.webm',
    '.mov',
    '.flv',
    '.mp3',
    '.wav',
    '.ogg',
    '.flac',
    '.m4a',
    '.aac',
}

# Diretórios do sistema que nunca são indexados (arquivos do SO, não do usuário).
SYSTEM_DIRS = {
    'system32', 'syswow64', 'windows', 'program files', 'program files (x86)',
    'usr', 'lib', 'lib64', 'bin', 'sbin', 'etc', 'var', 'proc', 'sys',
    'dev', 'run', 'tmp', 'boot', 'root', 'home', 'opt', 'srv', 'mnt', 'media',
    'venv', '.venv', 'env', '__pycache__', '.git', '.github', '.opencode',
}
# Arquivos/temporários ocultos que nunca são indexados.
SYSTEM_PREFIXES = ('~', '.')
MAX_FILE_BYTES = 2_000_000  # 2 MB por arquivo


def _default_user_roots() -> list[str]:
    """Diretórios-raiz padrão com arquivos do usuário (não do sistema)."""
    home = Path.home()
    roots = []
    for name in ('Documents', 'Documentos', 'Desktop', 'Área de Trabalho', 'enxame'):
        p = home / name
        if p.exists() and p.is_dir():
            roots.append(str(p))
    # Sempre inclui o diretório configurável via env, se existir.
    env_dir = os.getenv('BIB_DOCS_DIR')
    if env_dir:
        p = Path(env_dir)
        if p.exists() and p.is_dir() and str(p) not in roots:
            roots.append(str(p))
    if not roots:
        roots.append(str(home / 'enxame' / 'docs'))
    return roots


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
        docs_dir: str | None = None,
        embeddings: EmbeddingService | None = None,
        chunk_size: int = 1200,
        overlap: int = 150,
        enable_ocr: bool = False,
        roots: list[str] | None = None,
    ) -> None:
        # Aceita roots (lista de diretórios do usuário) ou docs_dir único (compatibilidade).
        if roots is not None:
            self.roots = [Path(r) for r in roots if Path(r).exists()]
        elif docs_dir is not None:
            self.roots = [Path(docs_dir)] if Path(docs_dir).exists() else []
        else:
            self.roots = [Path(r) for r in _default_user_roots()]
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

    def _should_index(self, path: Path, root: Path | None = None) -> bool:
        """Retorna True se o arquivo é do usuário (não do sistema) e deve ser indexado."""
        parts = [p.lower() for p in path.parts]
        # Se o caminho está dentro de um root configurado, ignora as partes do root
        # na verificação de diretórios do sistema (evita falso-positivo com 'home', 'tmp', etc.).
        if root is not None:
            try:
                relative = path.relative_to(root)
                parts = [p.lower() for p in relative.parts]
            except ValueError:
                pass
        for part in parts:
            if part in SYSTEM_DIRS:
                return False
        name = path.name.lower()
        if name.startswith(SYSTEM_PREFIXES):
            return False
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return False
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                return False
        except OSError:
            return False
        return True

    def _extract_text(self, path: Path) -> tuple[str, dict]:
        """
        Extrai texto de um arquivo usando o leitor universal.
        Retorna tupla (texto, metadados).
        """
        ext = path.suffix.lower()

        # Usar o leitor universal para todos os formatos
        try:
            text, metadata = self.reader.extract_text(path)
            return text or '', metadata
        except Exception as exc:
            logger.warning('Falha extraindo %s: %s', path, exc)
            return '', {}

    def _split_chunks(self, content: str) -> list[str]:
        text = ' '.join((content or '').split())
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

    def _iter_files(self) -> list[Path]:
        """Lista arquivos do usuário em todos os roots, ignorando arquivos do sistema."""
        files: list[Path] = []
        for root in self.roots:
            try:
                for path in root.rglob('*'):
                    if path.is_file() and self._should_index(path, root):
                        files.append(path)
            except Exception:
                continue
        return sorted(files)

    def _compute_snapshot(self) -> dict[str, float]:
        snap: dict[str, float] = {}
        for path in self._iter_files():
            try:
                snap[str(path)] = path.stat().st_mtime
            except OSError:
                continue
        return snap

    def has_changes(self) -> bool:
        return self._compute_snapshot() != self._snapshot

    def rebuild(self) -> list[IndexedChunk]:
        """
        Reconstrói o índice de documentos usando o leitor universal.
        Varredura em diretórios do usuário, ignorando arquivos do sistema.
        """
        chunks: list[IndexedChunk] = []
        snapshot = self._compute_snapshot()

        for raw_path in sorted(snapshot.keys()):
            path = Path(raw_path)
            text, metadata = self._extract_text(path)

            if not text:
                logger.debug('Nenhum texto extraído de %s', path)
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
        logger.info('Indexador local reconstruído: %s chunks (de %s arquivos, %s roots)', len(chunks), len(snapshot), len(self.roots))
        return chunks

    def index_file(self, file_path: str) -> dict[str, Any]:
        """
        Indexa um único arquivo.
        
        Args:
            file_path: Caminho do arquivo a indexar.
            
        Returns:
            Dict com document_id, chunks, filename.
        """
        path = Path(file_path)
        if not path.exists():
            return {"error": "File not found", "chunks": 0}
        
        if not self._should_index(path):
            return {"error": "File is a system or unsupported file", "chunks": 0}
        
        text, metadata = self._extract_text(path)
        
        if not text:
            return {"error": "No text extracted", "chunks": 0}
        
        doc_chunks = self.reader.split_into_chunks(text, metadata)
        
        new_chunks = []
        for chunk in doc_chunks:
            new_chunks.append(
                IndexedChunk(
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    source_path=chunk.source_path,
                    extension=chunk.extension,
                    metadata=chunk.metadata,
                )
            )
        
        # Adicionar aos chunks existentes
        self.chunks.extend(new_chunks)
        self._snapshot[str(path)] = path.stat().st_mtime
        
        logger.info('Arquivo indexado: %s (%s chunks)', path.name, len(new_chunks))
        
        return {
            "document_id": new_chunks[0].chunk_id if new_chunks else None,
            "chunks": len(new_chunks),
            "filename": path.name,
        }

    async def auto_reindex_loop(self, on_reindex) -> None:
        interval = int(os.getenv('INDEXER_INTERVAL_SECONDS', '120'))
        while True:
            try:
                if self.has_changes():
                    logger.info('Mudança detectada em documentos locais. Reindexando...')
                    chunks = self.rebuild()
                    await on_reindex(chunks)
            except Exception as exc:
                logger.exception('Falha no loop de indexação: %s', exc)
            await asyncio.sleep(interval)
