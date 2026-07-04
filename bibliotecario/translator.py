from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


_PT_HINTS = {
    "de",
    "para",
    "com",
    "não",
    "que",
    "uma",
    "sobre",
    "dados",
    "arquivo",
    "pesquisa",
}


@dataclass(slots=True)
class PTBRTranslator:
    """Tradutor para português brasileiro com fallback seguro."""

    enabled: bool = True
    model_name: str = field(default_factory=lambda: os.getenv("TRANSLATION_MODEL", "Helsinki-NLP/opus-mt-en-pt"))
    _pipeline: object | None = field(default=None, init=False, repr=False)
    _ready: bool = field(default=False, init=False)

    def _looks_portuguese(self, text: str) -> bool:
        words = {w.lower() for w in re.findall(r"[\wÀ-ÿ]+", text)}
        return len(words.intersection(_PT_HINTS)) >= 2

    def _load(self) -> None:
        if self._ready or not self.enabled:
            return
        try:
            from transformers import pipeline  # type: ignore

            self._pipeline = pipeline("translation", model=self.model_name)
            logger.info("Tradutor carregado: %s", self.model_name)
        except Exception as exc:  # pragma: no cover - depende de runtime
            logger.warning("Tradutor indisponível, fallback sem tradução: %s", exc)
            self._pipeline = None
        self._ready = True

    def to_pt_br(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        if self._looks_portuguese(text):
            return text

        self._load()
        if self._pipeline is None:
            return text

        try:
            translated = self._pipeline(text, max_length=768)
            if translated and isinstance(translated, list):
                out = str(translated[0].get("translation_text", "")).strip()
                if out:
                    return out
        except Exception as exc:  # pragma: no cover - depende de runtime
            logger.warning("Falha na tradução, retornando original: %s", exc)
        return text
