"""
Abstração de provider de LLM.

Implementa BEE-0003 — Seção 6.
Permite usar diferentes runtimes (Ollama, vLLM, LM Studio, etc.)
com uma interface unificada.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

import httpx


class ProviderType(Enum):
    """Tipos de providers suportados."""
    OLLAMA = "ollama"
    VLLM = "vllm"
    LMSTUDIO = "lmstudio"
    TGI = "tgi"


class LLMProvider(ABC):
    """
    Interface genérica para providers de LLM.
    
    Esta abstração permite que a Abelha use diferentes runtimes
    de inferência sem acoplamento arquitetural.
    """
    
    @abstractmethod
    async def health(self) -> bool:
        """Verificar se provider está saudável."""
        pass
    
    @abstractmethod
    async def list_models(self) -> list[dict[str, Any]]:
        """Listar modelos disponíveis."""
        pass
    
    @abstractmethod
    async def generate(
        self,
        model: str,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        """
        Gerar resposta usando modelo específico.
        
        Args:
            model: Nome do modelo.
            prompt: Prompt de entrada.
            **kwargs: Parâmetros adicionais (temperature, max_tokens, etc.).
        
        Returns:
            Texto gerado pelo modelo.
        """
        pass
    
    @abstractmethod
    async def get_loaded_models(self) -> list[str]:
        """Obter modelos atualmente carregados na memória/VRAM."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Nome do provider (ex: 'ollama', 'vllm', 'lmstudio')."""
        pass
    
    async def close(self) -> None:
        """Limpar recursos do provider."""
        pass


class OllamaProvider(LLMProvider):
    """
    Implementação para Ollama.
    
    Usa a API HTTP do Ollama para inferência local.
    """
    
    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip('/')
        self._client = httpx.AsyncClient(timeout=120.0)
    
    @property
    def provider_name(self) -> str:
        return "ollama"
    
    async def health(self) -> bool:
        """Verificar se Ollama está respondendo."""
        try:
            resp = await self._client.get(f"{self.base_url}/api/tags")
            return resp.status_code == 200
        except Exception:
            return False
    
    async def list_models(self) -> list[dict[str, Any]]:
        """Listar modelos instalados no Ollama."""
        resp = await self._client.get(f"{self.base_url}/api/tags")
        resp.raise_for_status()
        return resp.json().get("models", [])
    
    async def generate(
        self,
        model: str,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        """
        Gerar resposta usando Ollama.
        
        Parâmetros suportados em kwargs:
        - temperature: Temperatura (default: 0.7)
        - num_ctx: Context window (default: 4096)
        - top_p: Top-p sampling (default: 0.9)
        - top_k: Top-k sampling (default: 40)
        - stream: Stream response (default: False)
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": kwargs.get("stream", False),
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_ctx": kwargs.get("num_ctx", 4096),
                "top_p": kwargs.get("top_p", 0.9),
                "top_k": kwargs.get("top_k", 40),
            },
        }
        
        resp = await self._client.post(
            f"{self.base_url}/api/generate",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    
    async def get_loaded_models(self) -> list[str]:
        """Obter modelos carregados na VRAM."""
        resp = await self._client.get(f"{self.base_url}/api/ps")
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    
    async def close(self) -> None:
        """Fechar cliente HTTP."""
        await self._client.aclose()


# TODO: Implementar outros providers no futuro
# class VLLMProvider(LLMProvider):
#     """Implementação para vLLM."""
#     pass
# 
# class LMStudioProvider(LLMProvider):
#     """Implementação para LM Studio."""
#     pass
# 
# class TGIProvider(LLMProvider):
#     """Implementação para Text Generation Inference."""
#     pass


def create_provider(
    provider_type: ProviderType,
    config: dict[str, Any] | None = None,
) -> LLMProvider:
    """
    Factory para criar provider baseado no tipo.
    
    Args:
        provider_type: Tipo de provider desejado.
        config: Configuração específica do provider.
    
    Returns:
        Instância do provider selecionado.
    
    Raises:
        NotImplementedError: Se provider não estiver implementado.
        ValueError: Se tipo de provider for desconhecido.
    """
    config = config or {}
    
    if provider_type == ProviderType.OLLAMA:
        return OllamaProvider(
            base_url=config.get("base_url", "http://localhost:11434"),
        )
    elif provider_type == ProviderType.VLLM:
        raise NotImplementedError(
            "vLLM provider não implementado ainda. "
            "Esta abstração está pronta para extensão futura."
        )
    elif provider_type == ProviderType.LMSTUDIO:
        raise NotImplementedError(
            "LM Studio provider não implementado ainda. "
            "Esta abstração está pronta para extensão futura."
        )
    elif provider_type == ProviderType.TGI:
        raise NotImplementedError(
            "TGI provider não implementado ainda. "
            "Esta abstração está pronta para extensão futura."
        )
    else:
        raise ValueError(f"Provider type desconhecido: {provider_type}")
