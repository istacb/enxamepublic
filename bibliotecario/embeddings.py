from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _has_avx2() -> bool:
    """Verifica se CPU suporta AVX2."""
    try:
        # Verifica flags do CPU
        with open('/proc/cpuinfo', 'r') as f:
            content = f.read()
        return 'avx2' in content.lower()
    except Exception:
        return False


_HAS_AVX2 = _has_avx2()


@dataclass(slots=True)
class EmbeddingService:
    """Embeddings multilíngues com fallback determinístico.
    
    Prioridade: modelo local (sentence-transformers) -> fallback hash.
    Modelo padrão: all-MiniLM-L6-v2 (384 dim, rápido, bom para PT-BR/EN).
    """
    
    model_name: str = field(
        default_factory=lambda: os.getenv(
            'EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2'
        )
    )
    dimension: int = 384
    _model: object | None = field(default=None, init=False, repr=False)
    _ready: bool = field(default=False, init=False)
    
    def _load(self) -> None:
        if self._ready:
            return
        
        # Não tenta carregar sentence-transformers se CPU não tem AVX2
        if not _HAS_AVX2:
            logger.warning('CPU sem AVX2, pulando sentence-transformers, usando fallback hash')
            self._model = None
            self._ready = True
            return
        
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            
            self._model = SentenceTransformer(self.model_name)
            test_vec = self._model.encode(['ok'])[0]
            self.dimension = int(len(test_vec))
            logger.info('Modelo de embeddings carregado: %s (dim=%s)', self.model_name, self.dimension)
        except Exception as exc:  # pragma: no cover - depende de runtime
            logger.warning('Modelo de embeddings indisponível, usando fallback hash: %s', exc)
            self._model = None
        self._ready = True
    
    def encode(self, text: str) -> list[float]:
        self._load()
        raw = (text or '').strip()
        if not raw:
            return [0.0] * self.dimension
        
        if self._model is not None:
            vec = self._model.encode([raw])[0]
            return [float(x) for x in vec]
        
        digest = hashlib.sha256(raw.encode('utf-8')).digest()
        values = [((digest[i % len(digest)] / 255.0) * 2.0) - 1.0 for i in range(self.dimension)]
        return values
