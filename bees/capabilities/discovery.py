"""
Descoberta de capacidades de hardware, Ollama e capacidades locais.

Implementa BEE-0003 — Seções 3, 4, 5 e 7.
"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

try:
    import psutil
except Exception:
    psutil = None


@dataclass
class HardwareCapabilities:
    """Recursos de hardware da máquina."""
    os: str
    os_version: str
    architecture: str
    cpu_cores: int
    cpu_logical: int
    cpu_freq_ghz: float
    ram_total_gb: float
    ram_available_gb: float
    gpu_available: bool
    gpu_name: str | None
    gpu_vram_gb: float
    storage_total_gb: float
    storage_free_gb: float


@dataclass
class ModelInfo:
    """Informações de um modelo descoberto."""
    name: str
    size_bytes: int
    parameter_size: str
    is_embedding: bool
    is_loaded: bool
    context_length: int
    quantization: str | None
    supports_generation: bool = True
    supports_chat: bool = False
    recommended_for: list[str] = field(default_factory=list)


@dataclass
class OllamaCapabilities:
    """Recursos do Ollama."""
    available: bool
    version: str | None
    base_url: str
    models: list[ModelInfo] = field(default_factory=list)
    loaded_models: list[str] = field(default_factory=list)


@dataclass
class LocalCapabilities:
    """Capacidades locais independentes de Ollama."""
    embeddings_available: bool
    embeddings_model: str | None
    ocr_available: bool
    rag_available: bool
    zim_available: bool
    zim_file_count: int
    web_available: bool


@dataclass
class BeeCapabilities:
    """Capacidades completas da Abelha."""
    hardware: HardwareCapabilities
    ollama: OllamaCapabilities | None
    local: LocalCapabilities
    
    def to_manifesto_dict(self) -> dict[str, Any]:
        """Converter para formato do manifesto (BEE-0002)."""
        manifesto: dict[str, Any] = {
            "hardware": {
                "os": self.hardware.os,
                "architecture": self.hardware.architecture,
                "cpu_cores": self.hardware.cpu_cores,
                "ram_gb": round(self.hardware.ram_total_gb, 1),
                "gpu": self.hardware.gpu_name,
            },
            "capabilities": [],
            "models": [],
        }
        
        # Construir lista de capabilities
        caps = []
        if self.ollama and self.ollama.available:
            caps.append("llm_inference")
            if any(m.is_embedding for m in self.ollama.models):
                caps.append("embeddings")
        if self.local.embeddings_available:
            caps.append("embeddings_local")
        if self.local.ocr_available:
            caps.append("ocr")
        if self.local.rag_available:
            caps.append("rag")
        if self.local.zim_available:
            caps.append("zim")
        if self.local.web_available:
            caps.append("web_fallback")
        
        manifesto["capabilities"] = caps
        
        # Lista de modelos (apenas nomes para manifesto)
        if self.ollama and self.ollama.available:
            manifesto["models"] = [m.name for m in self.ollama.models]
            manifesto["ollama_version"] = self.ollama.version or ""
        
        return manifesto


def _detect_os() -> tuple[str, str]:
    """Detectar sistema operacional e versão."""
    system = platform.system()
    
    if system == "Darwin":
        os_name = "macOS"
        try:
            # macOS version via sw_vers
            import subprocess
            result = subprocess.run(
                ["sw_vers", "-productVersion"],
                capture_output=True,
                text=True,
                timeout=5
            )
            os_version = result.stdout.strip()
        except Exception:
            os_version = platform.version()
    elif system == "Linux":
        os_name = "Linux"
        try:
            # Tentar obter versão amigável
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("VERSION="):
                        os_version = line.split("=")[1].strip().strip('"')
                        break
                else:
                    os_version = platform.version()
        except Exception:
            os_version = platform.version()
    elif system == "Windows":
        os_name = "Windows"
        os_version = platform.version()
    else:
        os_name = "Other"
        os_version = platform.version()
    
    return os_name, os_version


def _detect_gpu() -> tuple[bool, str | None, float]:
    """Detectar GPU disponível."""
    # Tentar NVIDIA primeiro
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        gpu_name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(gpu_name, bytes):
            gpu_name = gpu_name.decode("utf-8")
        gpu_vram = pynvml.nvmlDeviceGetMemoryInfo(handle).total / (1024 ** 3)
        return True, gpu_name, gpu_vram
    except Exception:
        pass
    
    # macOS Apple Silicon
    if platform.system() == "Darwin":
        # Apple Silicon tem GPU unificada
        arch = platform.machine()
        if arch in ("arm64", "aarch64"):
            # Estimativa conservadora: 50% da RAM como VRAM
            if psutil:
                ram = psutil.virtual_memory()
                ram_total_gb = ram.total / (1024 ** 3)
                return True, "Apple Silicon Unified Memory", ram_total_gb * 0.5
    
    return False, None, 0.0


def scan_hardware(enxame_data_path: str | None = None) -> HardwareCapabilities:
    """
    Escanear hardware da máquina.
    
    Args:
        enxame_data_path: Caminho do diretório de dados do Enxame.
    
    Returns:
        HardwareCapabilities com informações do hardware.
    """
    # OS e arquitetura
    os_name, os_version = _detect_os()
    architecture = platform.machine()
    
    # CPU
    cpu_cores = 0
    cpu_logical = 0
    cpu_freq_ghz = 0.0
    
    if psutil:
        cpu_cores = psutil.cpu_count(logical=False) or 0
        cpu_logical = psutil.cpu_count(logical=True) or 0
        cpu_freq = psutil.cpu_freq()
        if cpu_freq:
            # psutil.cpu_freq() pode retornar diferentes atributos dependendo da plataforma
            cpu_freq_ghz = getattr(cpu_freq, 'base', getattr(cpu_freq, 'current', 0)) / 1000.0
    
    # RAM
    ram_total_gb = 0.0
    ram_available_gb = 0.0
    
    if psutil:
        ram = psutil.virtual_memory()
        ram_total_gb = ram.total / (1024 ** 3)
        ram_available_gb = ram.available / (1024 ** 3)
    
    # GPU
    gpu_available, gpu_name, gpu_vram_gb = _detect_gpu()
    
    # Armazenamento
    storage_total_gb = 0.0
    storage_free_gb = 0.0
    
    try:
        disk = shutil.disk_usage("/")
        storage_total_gb = disk.total / (1024 ** 3)
        storage_free_gb = disk.free / (1024 ** 3)
    except Exception:
        pass
    
    return HardwareCapabilities(
        os=os_name,
        os_version=os_version,
        architecture=architecture,
        cpu_cores=cpu_cores,
        cpu_logical=cpu_logical,
        cpu_freq_ghz=cpu_freq_ghz,
        ram_total_gb=ram_total_gb,
        ram_available_gb=ram_available_gb,
        gpu_available=gpu_available,
        gpu_name=gpu_name,
        gpu_vram_gb=gpu_vram_gb,
        storage_total_gb=storage_total_gb,
        storage_free_gb=storage_free_gb,
    )


async def _fetch_ollama_tags(base_url: str) -> list[dict[str, Any]]:
    """Buscar lista de modelos do Ollama."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{base_url}/api/tags")
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data.get("models", [])


async def _fetch_ollama_version(base_url: str) -> str | None:
    """Buscar versão do Ollama."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{base_url}/api/version")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("version")
        except Exception:
            pass
    return None


async def _fetch_loaded_models(base_url: str) -> list[str]:
    """Buscar modelos atualmente carregados."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{base_url}/api/ps")
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
    return []


def _parse_model_info(raw: dict[str, Any], loaded_models: list[str]) -> ModelInfo:
    """Parse de informações de modelo da API do Ollama."""
    details = raw.get("details", {})
    name = raw.get("name", "unknown")
    param_size = details.get("parameter_size", "unknown")
    quant = details.get("quantization_level")
    
    # Detectar se é modelo de embedding
    name_lower = name.lower()
    family = details.get("family", "").lower()
    is_embedding = (
        "embed" in name_lower or
        family in ("bert", "embedding") or
        "nomic" in name_lower or
        "mxbai" in name_lower
    )
    
    # Estimar contexto
    if "long" in name_lower or "context" in name_lower:
        context_length = 32000
    elif quant and "long" in quant.lower():
        context_length = 16000
    else:
        context_length = 4096
    
    # Detectar se suporta chat
    supports_chat = "chat" in name_lower or "instruct" in name_lower
    
    # Recomendações baseadas no nome
    recommended = ["general"]
    if "code" in name_lower or "coder" in name_lower:
        recommended.append("code")
    if "math" in name_lower:
        recommended.append("math")
    if "med" in name_lower or "medical" in name_lower:
        recommended.append("medical")
    
    return ModelInfo(
        name=name,
        size_bytes=raw.get("size", 0),
        parameter_size=param_size,
        is_embedding=is_embedding,
        is_loaded=name in loaded_models,
        context_length=context_length,
        quantization=quant,
        supports_generation=not is_embedding,
        supports_chat=supports_chat,
        recommended_for=recommended,
    )


async def scan_ollama(base_url: str = "http://localhost:11434") -> OllamaCapabilities:
    """
    Escanear Ollama local.
    
    Args:
        base_url: URL base do Ollama.
    
    Returns:
        OllamaCapabilities com informações do Ollama.
    """
    # Verificar disponibilidade
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{base_url}/api/tags")
            available = resp.status_code == 200
        except Exception:
            return OllamaCapabilities(
                available=False,
                version=None,
                base_url=base_url,
            )
    
    if not available:
        return OllamaCapabilities(
            available=False,
            version=None,
            base_url=base_url,
        )
    
    # Buscar versão, modelos e modelos carregados em paralelo
    version_task = _fetch_ollama_version(base_url)
    tags_task = _fetch_ollama_tags(base_url)
    loaded_task = _fetch_loaded_models(base_url)
    
    version, tags, loaded = await asyncio.gather(version_task, tags_task, loaded_task)
    
    # Parse dos modelos
    models = [_parse_model_info(t, loaded) for t in tags]
    
    return OllamaCapabilities(
        available=True,
        version=version,
        base_url=base_url,
        models=models,
        loaded_models=loaded,
    )


def scan_local_capabilities(enxame_data_path: str) -> LocalCapabilities:
    """
    Escanear capacidades locais independentes de Ollama.
    
    Args:
        enxame_data_path: Caminho do diretório de dados do Enxame.
    
    Returns:
        LocalCapabilities com capacidades locais.
    """
    # Embeddings (sentence-transformers fallback)
    embeddings_available = False
    embeddings_model = None
    
    try:
        from sentence_transformers import SentenceTransformer
        # Teste rápido - não carregar modelo, apenas verificar disponibilidade
        embeddings_available = True
        embeddings_model = "sentence-transformers:all-MiniLM-L6-v2"
    except Exception:
        pass
    
    # OCR (Tesseract)
    ocr_available = False
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        ocr_available = True
    except Exception:
        pass
    
    # RAG (LanceDB/Qdrant)
    rag_available = False
    lancedb_path = os.path.join(enxame_data_path, "lancedb")
    qdrant_path = os.path.join(enxame_data_path, "qdrant")
    
    if os.path.exists(lancedb_path) and os.listdir(lancedb_path):
        rag_available = True
    elif os.path.exists(qdrant_path) and os.listdir(qdrant_path):
        rag_available = True
    
    # ZIM files
    zim_available = False
    zim_file_count = 0
    zim_path = os.path.join(enxame_data_path, "zim")
    
    if os.path.exists(zim_path):
        zim_files = [f for f in os.listdir(zim_path) if f.endswith(".zim")]
        zim_file_count = len(zim_files)
        zim_available = zim_file_count > 0
    
    # Web access
    web_available = False
    allow_internet = os.getenv("ENXAME_ALLOW_INTERNET", "false").lower() == "true"
    
    if allow_internet:
        try:
            resp = httpx.get("https://www.google.com", timeout=5.0)
            web_available = resp.status_code == 200
        except Exception:
            pass
    
    return LocalCapabilities(
        embeddings_available=embeddings_available,
        embeddings_model=embeddings_model,
        ocr_available=ocr_available,
        rag_available=rag_available,
        zim_available=zim_available,
        zim_file_count=zim_file_count,
        web_available=web_available,
    )


async def discover_capabilities(
    enxame_data_path: str | None = None,
    ollama_base_url: str = "http://localhost:11434",
) -> BeeCapabilities:
    """
    Descobrir todas as capacidades da Abelha.
    
    Esta é a função principal que agrega todas as descobertas.
    
    Args:
        enxame_data_path: Caminho do diretório de dados do Enxame.
                         Default: ~/.enxame
        ollama_base_url: URL base do Ollama.
    
    Returns:
        BeeCapabilities com todas as capacidades descobertas.
    """
    # Path padrão
    if enxame_data_path is None:
        enxame_data_path = os.path.expanduser("~/.enxame")
    
    # Scan de hardware (síncrono)
    hardware = scan_hardware(enxame_data_path)
    
    # Scan de Ollama (assíncrono)
    ollama = await scan_ollama(ollama_base_url)
    
    # Scan de capacidades locais (síncrono)
    local = scan_local_capabilities(enxame_data_path)
    
    return BeeCapabilities(
        hardware=hardware,
        ollama=ollama,
        local=local,
    )


# Import necessário para funções async
import asyncio
