"""Armazenamento vetorial com LanceDB para ENXAME Bibliotecário.

Substitui Qdrant por solução embedded mais leve sem servidor dedicado.
Mantém compatibilidade com interface existente do QdrantStore.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .embeddings import EmbeddingService
from .indexer import IndexedChunk

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LanceDBHit:
    score: float
    text: str
    source_path: str
    chunk_id: str


class LanceDBStore:
    """Armazenamento vetorial com LanceDB embedded.
    
    - Sem servidor dedicado (arquivos locais)
    - Compatível com interface QdrantStore
    - Menor consumo de memória que Qdrant + Redis
    """

    def __init__(self, embeddings: EmbeddingService) -> None:
        self.embeddings = embeddings
        self.collection_name = os.getenv('LANCEDB_COLLECTION', 'enxame_docs')
        self.db_path = os.getenv('LANCEDB_PATH', '/data/lancedb')
        self._db = None
        self._table = None
        self._ready = False

    def _load(self) -> None:
        if self._ready:
            return
        
        try:
            import lancedb  # type: ignore
            
            # Criar diretório se não existir
            db_path = Path(self.db_path)
            db_path.mkdir(parents=True, exist_ok=True)
            
            # Conectar ao banco
            self._db = lancedb.connect(str(db_path))
            
            # Verificar se tabela existe, senão criar
            table_names = self._db.table_names()
            if self.collection_name not in table_names:
                # Esquema da tabela
                schema_data = {
                    'chunk_id': str(),
                    'text': str(),
                    'source_path': str(),
                    'extension': str(),
                    'vector': [0.0] * self.embeddings.dimension,
                }
                self._table = self._db.create_table(self.collection_name, schema=[schema_data])
            else:
                self._table = self._db.open_table(self.collection_name)
            
            logger.info('LanceDB pronto na coleção %s (path=%s)', self.collection_name, self.db_path)
        except Exception as exc:  # pragma: no cover - depende de runtime
            logger.warning('LanceDB indisponível: %s', exc)
            self._db = None
            self._table = None
        self._ready = True

    @property
    def ready(self) -> bool:
        self._load()
        return self._table is not None

    async def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        """Inseri chunks no índice vetorial."""
        self._load()
        if self._table is None or not chunks:
            return
        
        try:
            # Preparar dados para inserção
            data = []
            for idx, chunk in enumerate(chunks):
                vector = self.embeddings.encode(chunk.text)
                data.append({
                    'chunk_id': chunk.chunk_id,
                    'text': chunk.text,
                    'source_path': chunk.source_path,
                    'extension': chunk.extension,
                    'vector': vector,
                })
                
                # Inserir em lotes de 100 para performance
                if len(data) >= 100:
                    self._table.add(data)
                    logger.debug('Lote de %d chunks inserido', len(data))
                    data = []
            
            # Inserir restante
            if data:
                self._table.add(data)
            
            logger.info('LanceDB indexado com %d chunks', len(chunks))
        except Exception as exc:  # pragma: no cover
            logger.warning('Falha no upsert LanceDB: %s', exc)

    async def search(self, query: str, limit: int = 5) -> list[LanceDBHit]:
        """Busca vetorial por similaridade."""
        self._load()
        if self._table is None:
            return []
        
        try:
            # Codificar query
            query_vector = self.embeddings.encode(query)
            
            # Buscar similares
            results = self._table.search(query_vector).limit(limit).to_pandas()
            
            hits: list[LanceDBHit] = []
            for _, row in results.iterrows():
                hits.append(
                    LanceDBHit(
                        score=float(row.get('_distance', 0.0)),
                        text=str(row.get('text', '')),
                        source_path=str(row.get('source_path', '')),
                        chunk_id=str(row.get('chunk_id', '')),
                    )
                )
            return hits
        except Exception as exc:  # pragma: no cover
            logger.warning('Falha na busca LanceDB: %s', exc)
            return []
