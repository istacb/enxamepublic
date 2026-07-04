from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

SUPPORTED_MODELS = {
    "llama3",
    "llama3:8b",
    "gemma2:2b-it-qat",
    "gemma2:9b",
}


class OllamaError(Exception):
    """Erro de comunicação com Ollama."""


@dataclass(slots=True)
class OllamaGenerateRequest:
    model: str
    prompt: str
    temperature: float = 0.2
    num_ctx: int = 4096
    stream: bool = False


class OllamaClient:
    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _validate_model(self, model: str) -> None:
        if model not in SUPPORTED_MODELS:
            raise OllamaError(
                f"Modelo não suportado pelo núcleo ENXAME: {model}. "
                f"Suportados: {', '.join(sorted(SUPPORTED_MODELS))}"
            )

    async def health(self) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self.base_url}/api/tags")
            return resp.status_code == 200

    async def generate(self, req: OllamaGenerateRequest) -> str:
        self._validate_model(req.model)
        payload = {
            "model": req.model,
            "prompt": req.prompt,
            "stream": req.stream,
            "options": {
                "temperature": req.temperature,
                "num_ctx": req.num_ctx,
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            if resp.status_code != 200:
                raise OllamaError(f"Falha Ollama: HTTP {resp.status_code} - {resp.text}")
            data: dict[str, Any] = resp.json()
            return str(data.get("response", "")).strip()

    async def pull(self, model: str) -> dict[str, Any]:
        self._validate_model(model)
        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.post(f"{self.base_url}/api/pull", json={"model": model})
            if resp.status_code != 200:
                raise OllamaError(f"Falha ao baixar modelo {model}: {resp.text}")
            return resp.json()
