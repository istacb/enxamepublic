from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from .embeddings import EmbeddingService
from .indexer import IndexedChunk

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class QdrantHit:
    score: float
    text: str
    source_path: str
    chunk_id: str


class QdrantStore:
    def __init__(self, embeddings: EmbeddingService) -> None:
        self.embeddings = embeddings
        self.collection = os.getenv("QDRANT_COLLECTION", "enxame_docs")
        self._client = None
        self._ready = False

    def _load(self) -> None:
        if self._ready:
            return
        try:
            from qdrant_client import QdrantClient  # type: ignore
            from qdrant_client.models import Distance, VectorParams  # type: ignore

            qdrant_url = os.getenv("QDRANT_URL", "").strip()
            if qdrant_url:
                self._client = QdrantClient(url=qdrant_url)
            else:
                local_path = os.getenv("QDRANT_LOCAL_PATH", "/data/qdrant")
                self._client = QdrantClient(path=local_path)

            collections = {c.name for c in self._client.get_collections().collections}
            if self.collection not in collections:
                self._client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(size=self.embeddings.dimension, distance=Distance.COSINE),
                )
            logger.info("Qdrant pronto na coleção %s", self.collection)
        except Exception as exc:  # pragma: no cover - depende de runtime
            logger.warning("Qdrant indisponível: %s", exc)
            self._client = None
        self._ready = True

    @property
    def ready(self) -> bool:
        self._load()
        return self._client is not None

    async def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        self._load()
        if self._client is None or not chunks:
            return
        try:
            from qdrant_client.models import PointStruct  # type: ignore

            points: list[PointStruct] = []
            for idx, chunk in enumerate(chunks):
                vector = self.embeddings.encode(chunk.text)
                int_id = int(chunk.chunk_id[:12], 16) + idx
                points.append(
                    PointStruct(
                        id=int_id,
                        vector=vector,
                        payload={
                            "chunk_id": chunk.chunk_id,
                            "text": chunk.text,
                            "source_path": chunk.source_path,
                            "extension": chunk.extension,
                        },
                    )
                )
            self._client.upsert(collection_name=self.collection, points=points)
            logger.info("Qdrant indexado com %s chunks", len(points))
        except Exception as exc:  # pragma: no cover
            logger.warning("Falha no upsert Qdrant: %s", exc)

    async def search(self, query: str, limit: int = 5) -> list[QdrantHit]:
        self._load()
        if self._client is None:
            return []
        try:
            vector = self.embeddings.encode(query)
            results = self._client.search(collection_name=self.collection, query_vector=vector, limit=limit)
            hits: list[QdrantHit] = []
            for row in results:
                payload: dict[str, Any] = row.payload or {}
                hits.append(
                    QdrantHit(
                        score=float(row.score),
                        text=str(payload.get("text", "")),
                        source_path=str(payload.get("source_path", "")),
                        chunk_id=str(payload.get("chunk_id", "")),
                    )
                )
            return hits
        except Exception as exc:  # pragma: no cover
            logger.warning("Falha na busca Qdrant: %s", exc)
            return []
