"""Armazenamento vetorial embedded com LanceDB."""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _has_avx2() -> bool:
    """Verifica se CPU suporta AVX2."""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            content = f.read()
        return 'avx2' in content.lower()
    except Exception:
        return False


_HAS_AVX2 = _has_avx2()


@dataclass(slots=True)
class LanceDBHit:
    """Resultado de busca no LanceDB."""

    score: float
    text: str
    source_path: str
    chunk_id: str
    metadata: dict[str, Any] | None = None


if _HAS_AVX2:
    class LanceDBStore:
        """Armazenamento vetorial embedded usando LanceDB.

        Configura o banco para gravar diretamente em diretório local
        (./data/lancedb por padrão) sem necessidade de servidores externos.
        Requer CPU com AVX2.
        """

        def __init__(
            self,
            embeddings: Any,  # EmbeddingService
            db_path: str | None = None,
            table_name: str = "enxame_docs",
        ) -> None:
            self.embeddings = embeddings
            self.db_path = Path(db_path or os.getenv("LANCEDB_PATH", "./data/lancedb"))
            self.table_name = table_name
            self._db: Any = None
            self._table: Any = None
            self._ready = False

        def _load(self) -> None:
            """Inicializa o banco LanceDB lazy."""
            if self._ready:
                return

            try:
                import lancedb  # type: ignore

                # Cria diretório se não existir
                self.db_path.mkdir(parents=True, exist_ok=True)

                # Conecta ao banco embedded
                self._db = lancedb.connect(str(self.db_path))

                # Verifica se a tabela existe, senão cria
                table_names = self._db.table_names()
                if self.table_name not in table_names:
                    self._create_table()
                else:
                    self._table = self._db.open_table(self.table_name)

                logger.info("LanceDB pronto em %s (tabela: %s)", self.db_path, self.table_name)
            except Exception as exc:
                logger.warning("LanceDB indisponível: %s", exc)
                self._db = None
                self._table = None

            self._ready = True

        def _create_table(self) -> None:
            """Cria a tabela de documentos vetoriais."""
            import pyarrow as pa  # type: ignore

            # Schema da tabela
            schema = pa.schema([
                pa.field("chunk_id", pa.string()),
                pa.field("text", pa.string()),
                pa.field("source_path", pa.string()),
                pa.field("extension", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), self.embeddings.dimension)),
                pa.field("metadata_json", pa.string()),
            ])

            # Cria tabela vazia
            self._table = self._db.create_table(self.table_name, schema=schema)

        @property
        def ready(self) -> bool:
            """Verifica se o banco está pronto."""
            self._load()
            return self._db is not None

        async def index_document(
            self,
            text: str,
            metadata: dict[str, Any],
            chunk_id: str | None = None,
        ) -> str | None:
            """Indexa um documento/texto no LanceDB.

            Args:
                text: Texto do documento ou chunk
                metadata: Metadados (source_path, extension, etc.)
                chunk_id: ID único do chunk (gerado se None)

            Returns:
                chunk_id do documento indexado ou None se falhar
            """
            self._load()
            if self._table is None:
                return None

            try:
                # Gera ID único se não fornecido
                cid = chunk_id or f"chunk_{uuid.uuid4().hex[:12]}"

                # Gera embedding
                vector = self.embeddings.encode(text)

                # Prepara metadados
                meta = metadata.copy()
                meta_json = __import__('json').dumps(meta, ensure_ascii=False)

                # Insere na tabela
                self._table.add([{
                    "chunk_id": cid,
                    "text": text,
                    "source_path": metadata.get("source_path", ""),
                    "extension": metadata.get("extension", ""),
                    "vector": vector,
                    "metadata_json": meta_json,
                }])

                return cid
            except Exception as exc:
                logger.warning("Falha ao indexar no LanceDB: %s", exc)
                return None

        async def index_documents_batch(
            self,
            documents: list[dict[str, Any]],
        ) -> int:
            """Indexa múltiplos documentos em lote.

            Args:
                documents: Lista de dicts com text, metadata, chunk_id opcional

            Returns:
                Número de documentos indexados com sucesso
            """
            self._load()
            if self._table is None:
                return 0

            try:
                rows = []
                for doc in documents:
                    text = doc.get("text", "")
                    metadata = doc.get("metadata", {})
                    cid = doc.get("chunk_id") or f"chunk_{uuid.uuid4().hex[:12]}"
                    vector = self.embeddings.encode(text)
                    meta_json = __import__('json').dumps(metadata, ensure_ascii=False)

                    rows.append({
                        "chunk_id": cid,
                        "text": text,
                        "source_path": metadata.get("source_path", ""),
                        "extension": metadata.get("extension", ""),
                        "vector": vector,
                        "metadata_json": meta_json,
                    })

                if rows:
                    self._table.add(rows)
                return len(rows)
            except Exception as exc:
                logger.warning("Falha ao indexar lote no LanceDB: %s", exc)
                return 0

        async def search_similar(
            self,
            query: str,
            top_k: int = 10,
        ) -> list["LanceDBHit"]:
            """Busca vetorial por similaridade.

            Args:
                query: Texto da query
                top_k: Número máximo de resultados

            Returns:
                Lista de hits ordenados por score
            """
            self._load()
            if self._table is None:
                return []

            try:
                query_vector = self.embeddings.encode(query)
                results = self._table.search(query_vector).limit(top_k).to_list()

                hits = []
                for r in results:
                    hits.append(LanceDBHit(
                        score=r.get("score", 0.0),
                        text=r.get("text", ""),
                        source_path=r.get("source_path", ""),
                        chunk_id=r.get("chunk_id", ""),
                        metadata=r.get("metadata_json"),
                    ))
                return hits
            except Exception as exc:
                logger.warning("Falha na busca LanceDB: %s", exc)
                return []

        async def upsert_chunks(self, chunks: list[Any]) -> int:
            """Faz upsert de chunks no LanceDB.

            Args:
                chunks: Lista de objetos IndexedChunk

            Returns:
                Número de chunks inseridos/atualizados
            """
            self._load()
            if self._table is None:
                return 0

            try:
                rows = []
                for chunk in chunks:
                    cid = chunk.chunk_id or f"chunk_{uuid.uuid4().hex[:12]}"
                    vector = self.embeddings.encode(chunk.text)
                    meta_json = __import__('json').dumps(chunk.metadata or {}, ensure_ascii=False)

                    rows.append({
                        "chunk_id": cid,
                        "text": chunk.text,
                        "source_path": chunk.source_path,
                        "extension": chunk.extension or "",
                        "vector": vector,
                        "metadata_json": meta_json,
                    })

                if rows:
                    self._table.add(rows)
                return len(rows)
            except Exception as exc:
                logger.warning("Falha no upsert LanceDB: %s", exc)
                return 0

else:
    # CPU sem AVX2 - classe dummy que falha graciosamente
    class LanceDBStore:
        """Placeholder para quando LanceDB não está disponível (CPU sem AVX2)."""

        def __init__(self, embeddings: Any, db_path: str | None = None, table_name: str = "enxame_docs") -> None:
            self.embeddings = embeddings
            self._ready = False
            logger.warning("LanceDB não disponível (CPU sem AVX2)")

        def _load(self) -> None:
            self._ready = True

        @property
        def ready(self) -> bool:
            return False

        async def index_document(self, text: str, metadata: dict[str, Any], chunk_id: str | None = None) -> str | None:
            return None

        async def index_documents_batch(self, documents: list[dict[str, Any]]) -> int:
            return 0

        async def search_similar(self, query: str, top_k: int = 10) -> list[Any]:
            return []

        async def upsert_chunks(self, chunks: list[Any]) -> int:
            return 0