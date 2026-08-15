"""
BEE-0003 — CAPABILITIES E MODEL DISCOVERY

Módulo de descoberta de capacidades e modelos da Abelha.
"""

from .discovery import (
    BeeCapabilities,
    HardwareCapabilities,
    LocalCapabilities,
    OllamaCapabilities,
    ModelInfo,
    discover_capabilities,
    scan_hardware,
    scan_ollama,
    scan_local_capabilities,
)
from .provider import (
    LLMProvider,
    OllamaProvider,
    ProviderType,
    create_provider,
)
from .selector import recommend_model

__all__ = [
    # Dataclasses
    "BeeCapabilities",
    "HardwareCapabilities",
    "LocalCapabilities",
    "OllamaCapabilities",
    "ModelInfo",
    # Discovery functions
    "discover_capabilities",
    "scan_hardware",
    "scan_ollama",
    "scan_local_capabilities",
    # Provider abstraction
    "LLMProvider",
    "OllamaProvider",
    "ProviderType",
    "create_provider",
    # Model selection
    "recommend_model",
]
