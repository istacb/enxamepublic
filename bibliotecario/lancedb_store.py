"""Armazenamento vetorial embedded com LanceDB."""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LanceDBHit:
    """Resultado de busca no LanceDB."""

    score: float
    text: str
    source_path: str
    chunk_id: str
    metadata: dict[str, Any] | None = None


class LanceDBStore:
    """Armazenamento vetorial embedded usando LanceDB.

    Configura o banco para gravar diretamente em diretório local
    (./data/lancedb por padrão) sem necessidade de servidores externos.
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

            # Prepara dados para inserção
            import pyarrow as pa

            data = {
                "chunk_id": [cid],
                "text": [text],
                "source_path": [metadata.get("source_path", "")],
                "extension": [metadata.get("extension", "")],
                "vector": [vector],
                "metadata_json": [str(metadata)],
            }

            table_data = pa.table(data)
            self._table.add(table_data)

            logger.debug("LanceDB indexou chunk %s", cid)
            return cid

        except Exception as exc:
            logger.warning("Falha no index_document LanceDB: %s", exc)
            return None

    async def index_documents_batch(
        self,
        documents: list[tuple[str, dict[str, Any]]],
    ) -> int:
        """Indexa múltiplos documentos em batch.

        Args:
            documents: Lista de tuplas (text, metadata)

        Returns:
            Número de documentos indexados com sucesso
        """
        self._load()
        if self._table is None or not documents:
            return 0

        try:
            import pyarrow as pa

            chunk_ids = []
            texts = []
            source_paths = []
            extensions = []
            vectors = []
            metadata_jsons = []

            for text, metadata in documents:
                cid = f"chunk_{uuid.uuid4().hex[:12]}"
                vector = self.embeddings.encode(text)

                chunk_ids.append(cid)
                texts.append(text)
                source_paths.append(metadata.get("source_path", ""))
                extensions.append(metadata.get("extension", ""))
                vectors.append(vector)
                metadata_jsons.append(str(metadata))

            data = {
                "chunk_id": chunk_ids,
                "text": texts,
                "source_path": source_paths,
                "extension": extensions,
                "vector": vectors,
                "metadata_json": metadata_jsons,
            }

            table_data = pa.table(data)
            self._table.add(table_data)

            logger.info("LanceDB indexou %d documentos em batch", len(documents))
            return len(documents)

        except Exception as exc:
            logger.warning("Falha no index_documents_batch LanceDB: %s", exc)
            return 0

    async def search_similar(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[LanceDBHit]:
        """Busca documentos similares à query.

        Args:
            query: Texto da query de busca
            top_k: Número de resultados a retornar

        Returns:
            Lista de LanceDBHit ordenados por relevância
        """
        self._load()
        if self._table is None:
            return []

        try:
            # Gera embedding da query
            query_vector = self.embeddings.encode(query)

            # Busca vetorial
            results = self._table.search(query_vector).limit(top_k).to_pandas()

            hits: list[LanceDBHit] = []
            for _, row in results.iterrows():
                import json

                try:
                    meta = json.loads(row["metadata_json"])
                except Exception:
                    meta = {}

                hits.append(
                    LanceDBHit(
                        score=float(row.get("_distance", 0.0)),
                        text=str(row["text"]),
                        source_path=str(row["source_path"]),
                        chunk_id=str(row["chunk_id"]),
                        metadata=meta,
                    )
                )

            return hits

        except Exception as exc:
            logger.warning("Falha na busca LanceDB: %s", exc)
            return []

    async def upsert_chunks(self, chunks: list[Any]) -> int:
        """Compatibilidade com interface QdrantStore.

        Args:
            chunks: Lista de IndexedChunk

        Returns:
            Número de chunks indexados
        """
        if not chunks:
            return 0

        documents = []
        for chunk in chunks:
            metadata = {
                "source_path": getattr(chunk, "source_path", ""),
                "extension": getattr(chunk, "extension", ""),
                "chunk_id": getattr(chunk, "chunk_id", ""),
            }
            if hasattr(chunk, "metadata") and chunk.metadata:
                metadata.update(chunk.metadata)

            documents.append((chunk.text, metadata))

        return await self.index_documents_batch(documents)
