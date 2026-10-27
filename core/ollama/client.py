from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class OllamaError(Exception):
    """Erro de comunicação com Ollama."""


@dataclass(slots=True)
class OllamaGenerateRequest:
    model: str
    prompt: str
    temperature: float = 0.2
    num_ctx: int = 4096
    stream: bool = False


@dataclass(slots=True)
class OllamaModel:
    name: str
    size_mb: float
    digest: str | None = None


# Modelos leves, ordenados do menor para o maior. Cada qualificado para um
# patamar de hardware; o primeiro que cabe na máquina é o recomendado.
LIGHT_MODELS: list[tuple[str, float, float]] = [
    # (nome, ram_min_gb, vram_min_gb)
    ('tinyllama:1.1b', 2.0, 0.0),
    ('qwen2.5:0.5b', 2.0, 0.0),
    ('qwen2.5:1.5b', 4.0, 0.0),
    ('llama3.2:1b', 4.0, 0.0),
    ('qwen2.5:3b', 8.0, 0.0),
    ('llama3.2:3b', 8.0, 0.0),
    ('qwen2.5:7b', 16.0, 0.0),
    ('llama3.1:8b', 16.0, 4.0),
]


class OllamaClient:
    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    # ponytail: nenhuma whitelist. O nó usa o que estiver instalado.
    # Ceiling: não baixa modelos sozinho — apenas recomenda. O auto-download
    # é tratado em ensure_model() com proteção contra re-download desnecessário.

    async def health(self) -> bool:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f'{self.base_url}/api/tags')
            return resp.status_code == 200

    async def list_models(self) -> list[OllamaModel]:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f'{self.base_url}/api/tags')
            if resp.status_code != 200:
                return []
            data: dict[str, Any] = resp.json()
        models: list[OllamaModel] = []
        for m in data.get('models', []):
            name = str(m.get('name', ''))
            size = float(m.get('size', 0)) / (1024 * 1024)
            models.append(OllamaModel(name=name, size_mb=size, digest=m.get('digest')))
        return models

    async def _loaded_models(self) -> list[str]:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f'{self.base_url}/api/ps')
            if resp.status_code != 200:
                return []
            data: dict[str, Any] = resp.json()
            return [str(m.get('name', '')) for m in data.get('models', [])]
        except Exception:
            return []

    async def select_best_model(self) -> str | None:
        """Escolhe o maior modelo já instalado. Não baixa nada."""
        models = await self.list_models()
        if not models:
            return None
        loaded = await self._loaded_models()
        candidates = [m for m in models if m.name in loaded] or models
        best = max(candidates, key=lambda m: m.size_mb)
        return best.name

    def _model_family(self, name: str) -> str:
        n = name.lower().split(':')[0]
        return n

    def _recommend_for_hardware(self, ram_gb: float, vram_gb: float) -> str | None:
        """Escolhe o menor modelo que cabe no hardware (mais capaz que caiba)."""
        candidates = [
            m for m in LIGHT_MODELS
            if m[1] <= ram_gb and m[2] <= vram_gb
        ]
        if not candidates:
            return LIGHT_MODELS[0][0] if LIGHT_MODELS else None
        # Retorna o maior que cabe (mais capaz dentro do limite).
        return max(candidates, key=lambda m: m[1])[0]

    async def ensure_model(self, ram_gb: float, vram_gb: float) -> str | None:
        """Garante que haja um modelo adequado ao hardware.

        - Se já houver modelo instalado igual ou superior ao recomendado, não
          baixa nada (usa o que existe).
        - Se não houver nada adequado, baixa o recomendado para o hardware.
        """
        installed = await self.list_models()
        recommended = self._recommend_for_hardware(ram_gb, vram_gb)
        if not recommended:
            return None

        # Se algum instalado for >= recomendado (mesma família maior ou igual),
        # não baixa nada.
        rec_family = self._model_family(recommended)
        rec_size = next((m[1] for m in LIGHT_MODELS if m[0] == recommended), 0.0)
        for m in installed:
            if self._model_family(m.name) == rec_family and m.size_mb >= rec_size * 0.9:
                return m.name

        # Baixa o recomendado.
        try:
            await self.pull(recommended)
        except OllamaError:
            return None
        return recommended

    async def generate(self, req: OllamaGenerateRequest) -> str:
        import httpx

        payload = {
            'model': req.model,
            'prompt': req.prompt,
            'stream': req.stream,
            'options': {
                'temperature': req.temperature,
                'num_ctx': req.num_ctx,
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f'{self.base_url}/api/generate', json=payload)
            if resp.status_code != 200:
                raise OllamaError(f'Falha Ollama: HTTP {resp.status_code} - {resp.text}')
            data: dict[str, Any] = resp.json()
            return str(data.get('response', '')).strip()

    async def pull(self, model: str) -> dict[str, Any]:
        import httpx

        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.post(f'{self.base_url}/api/pull', json={'model': model})
            if resp.status_code != 200:
                raise OllamaError(f'Falha ao baixar modelo {model}: {resp.text}')
            return resp.json()
