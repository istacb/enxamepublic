from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EmbeddingService:
    """Embeddings multilíngues com fallback determinístico.
    
    Prioridade:
    1. ONNX Runtime (all-MiniLM-L6-v2) - leve, CPU, ~90MB
    2. Sentence Transformers - fallback se ONNX indisponível
    3. Hash SHA256 - último recurso determinístico
    """

    model_name: str = field(
        default_factory=lambda: os.getenv(
            'EMBEDDING_MODEL', 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
        )
    )
    onnx_model_path: str = field(
        default_factory=lambda: os.getenv('ONNX_MODEL_PATH', '/data/models/all-MiniLM-L6-v2.onnx')
    )
    dimension: int = 384
    _model: object | None = field(default=None, init=False, repr=False)
    _onnx_session: object | None = field(default=None, init=False, repr=False)
    _tokenizer: object | None = field(default=None, init=False, repr=False)
    _ready: bool = field(default=False, init=False)

    def _load(self) -> None:
        if self._ready:
            return
        
        # Tentar ONNX Runtime primeiro (mais leve)
        try:
            import onnxruntime as ort  # type: ignore
            from tokenizers import Tokenizer  # type: ignore
            
            # Carregar tokenizer
            tokenizer_path = os.path.join(os.path.dirname(self.onnx_model_path), 'tokenizer.json')
            if os.path.exists(tokenizer_path):
                self._tokenizer = Tokenizer.from_file(tokenizer_path)
            else:
                # Fallback para tokenizer Hugging Face
                from transformers import AutoTokenizer  # type: ignore
                self._tokenizer = AutoTokenizer.from_pretrained('sentence-transformers/all-MiniLM-L6-v2')
            
            # Carregar modelo ONNX
            self._onnx_session = ort.InferenceSession(self.onnx_model_path)
            
            # Inferir dimensão do vetor
            test_vec = self.encode('ok')
            self.dimension = len(test_vec)
            
            logger.info('ONNX Runtime carregado: all-MiniLM-L6-v2 (dim=%d)', self.dimension)
            self._ready = True
            return
        except Exception as exc:
            logger.debug('ONNX indisponível, tentando sentence-transformers: %s', exc)
        
        # Fallback para Sentence Transformers
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

        # Prioridade 1: ONNX Runtime
        if self._onnx_session is not None and self._tokenizer is not None:
            try:
                # Tokenizar
                encoded = self._tokenizer.encode(raw, padding=True, truncation=True, max_length=512)
                
                # Extrair inputs
                input_ids = encoded.input_ids
                attention_mask = encoded.attention_mask
                
                # Executar inferência
                outputs = self._onnx_session.run(
                    None,
                    {
                        'input_ids': [input_ids],
                        'attention_mask': [attention_mask],
                    }
                )
                
                # Mean pooling e normalização
                embedding = outputs[0][0]
                norm = sum(x * x for x in embedding) ** 0.5
                if norm > 0:
                    embedding = [x / norm for x in embedding]
                
                return [float(x) for x in embedding]
            except Exception as exc:
                logger.warning('Falha ONNX, fallback: %s', exc)

        # Prioridade 2: Sentence Transformers
        if self._model is not None:
            vec = self._model.encode([raw])[0]
            return [float(x) for x in vec]

        # Prioridade 3: Fallback hash determinístico
        digest = hashlib.sha256(raw.encode('utf-8')).digest()
        values = [((digest[i % len(digest)] / 255.0) * 2.0) - 1.0 for i in range(self.dimension)]
        return values
