# BEE-0003 — CAPABILITIES E MODEL DISCOVERY

**Versão:** 1.0  
**Status:** Normativo  
**Data:** 2025  
**Autoria:** Arquitetura Enxame  
**Revisão:** Inicial

---

## 1. OBJETIVO

Definir como uma Abelha descobre seus próprios recursos locais e os declara para outras Abelhas através do manifesto.

Esta especificação cobre:

1. Descoberta de hardware (CPU, RAM, GPU, armazenamento)
2. Descoberta de sistema operacional e arquitetura
3. Descoberta de Ollama (disponibilidade, versão, modelos)
4. Descoberta de capacidades (embeddings, OCR, RAG, web)
5. Abstração de provider (não apenas Ollama)
6. Integração com manifesto da Abelha

---

## 2. PRINCÍPIOS NORMATIVOS

### 2.1 Descoberta Automática

A Abelha DEVE descobrir automaticamente o que já existe no sistema.

**NÃO instalar** modelos, drivers ou componentes adicionalmente nesta fase.

### 2.2 Não Fixar Modelo

**NÃO fixar** um modelo específico como requisito arquitetural.

A Abelha deve funcionar com qualquer modelo disponível localmente.

### 2.3 Não Assumir Hermes

**NÃO assumir** Hermes como modelo padrão ou obrigatório.

Hermes é opcional. Outros modelos (Llama, Gemma, etc.) são igualmente válidos.

### 2.4 Não Instalar Automaticamente

**NÃO instalar** modelos automaticamente nesta PR.

**NÃO instalar** múltiplos modelos pequenos sem necessidade.

### 2.5 Funcionamento Sem Ollama

A Abelha DEVE continuar funcionando mesmo sem Ollama.

Sem Ollama, a Abelha:
- Anuncia `ollama_available: false`
- Mantém outras capacidades (OCR, RAG em documentos, ZIM, web)
- Pode atuar como relay ou indexador

### 2.6 Provider Abstraction

DEVE existir abstração de provider para permitir futuros runtimes além de Ollama.

Interface genérica permite adicionar:
- vLLM
- TGI (Text Generation Inference)
- LM Studio
- Outros providers compatíveis

---

## 3. DESCOBERTA DE HARDWARE

### 3.1 Sistema Operacional e Arquitetura

**Fonte:** Módulo `platform` da stdlib Python

**Dados coletados:**
```python
{
    "os": "Linux" | "Windows" | "macOS" | "Other",
    "os_version": "22.04" | "14.1" | "10",
    "architecture": "x86_64" | "arm64" | "aarch64",
    "machine": "x86_64" | "arm64",
}
```

**Implementação:**
```python
import platform

system = platform.system()  # Linux, Windows, Darwin
if system == "Darwin":
    os_name = "macOS"
elif system in ("Linux", "Windows"):
    os_name = system
else:
    os_name = "Other"

os_version = platform.version()
architecture = platform.machine()  # x86_64, arm64, aarch64
```

### 3.2 CPU

**Fonte:** Módulo `psutil` (já existente no projeto)

**Dados coletados:**
```python
{
    "cpu_cores": 8,                    # Núcleos físicos
    "cpu_logical": 16,                 # Threads lógicos
    "cpu_freq_ghz": 3.2,               # Frequência base em GHz
    "cpu_percent": 25.5,               # Uso atual (%)
}
```

**Implementação:**
```python
import psutil

cpu_cores = psutil.cpu_count(logical=False) or 0
cpu_logical = psutil.cpu_count(logical=True) or 0
cpu_freq = psutil.cpu_freq()
cpu_freq_ghz = cpu_freq.base / 1000 if cpu_freq else 0.0
cpu_percent = psutil.cpu_percent(interval=1.0)
```

### 3.3 RAM

**Fonte:** Módulo `psutil`

**Dados coletados:**
```python
{
    "ram_total_gb": 16.0,              # RAM total em GB
    "ram_available_gb": 8.5,           # RAM disponível em GB
    "ram_percent": 47.0,               # Uso atual (%)
}
```

**Implementação:**
```python
ram = psutil.virtual_memory()
ram_total_gb = ram.total / (1024 ** 3)
ram_available_gb = ram.available / (1024 ** 3)
ram_percent = ram.percent
```

### 3.4 GPU (Opcional)

**Fonte:** Detectar via `pynvml` (NVIDIA) ou `platform` (macOS Apple Silicon)

**Dados coletados:**
```python
{
    "gpu_available": true,
    "gpu_name": "NVIDIA GeForce RTX 3080",
    "gpu_vram_gb": 10.0,
    "gpu_driver_version": "535.104.05",
}
```

**Implementação:**
```python
# Tentar NVIDIA primeiro
try:
    import pynvml
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    gpu_name = pynvml.nvmlDeviceGetName(handle)
    gpu_vram = pynvml.nvmlDeviceGetMemoryInfo(handle).total / (1024 ** 3)
    gpu_available = True
except Exception:
    gpu_available = False
    gpu_name = None
    gpu_vram = 0.0

# macOS Apple Silicon
if not gpu_available and platform.system() == "Darwin":
    # Apple Silicon tem GPU unificada
    gpu_available = True
    gpu_name = "Apple Silicon Unified Memory"
    gpu_vram = ram_total_gb * 0.5  # Estimativa conservadora
```

### 3.5 Armazenamento Relevante

**Fonte:** Módulo `psutil` e `os`

**Dados coletados:**
```python
{
    "storage_total_gb": 512.0,         # Total do disco principal
    "storage_free_gb": 128.0,          # Espaço livre em GB
    "enxame_data_path": "/home/user/.enxame",
    "enxame_storage_used_gb": 5.2,     # Espaço usado pelo Enxame
}
```

**Implementação:**
```python
import os
import shutil

# Disco principal
disk = shutil.disk_usage("/")
storage_total_gb = disk.total / (1024 ** 3)
storage_free_gb = disk.free / (1024 ** 3)

# Diretório Enxame
enxame_path = os.path.expanduser("~/.enxame")
if os.path.exists(enxame_path):
    # Calcular tamanho do diretório
    enxame_storage_used_gb = calculate_dir_size(enxame_path) / (1024 ** 3)
else:
    enxame_storage_used_gb = 0.0
```

---

## 4. DESCOBERTA DE OLLAMA

### 4.1 Disponibilidade

**Endpoint:** `GET /api/tags` (existente em `core/ollama/client.py`)

**Implementação:**
```python
async def check_ollama_available(base_url: str = "http://localhost:11434") -> bool:
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{base_url}/api/tags")
            return resp.status_code == 200
        except Exception:
            return False
```

### 4.2 Versão do Ollama

**Endpoint:** `GET /api/version`

**Resposta esperada:**
```json
{
    "version": "0.5.4",
    "commit": "abc123"
}
```

**Implementação:**
```python
async def get_ollama_version(base_url: str) -> str | None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{base_url}/api/version")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("version")
        except Exception:
            pass
    return None
```

### 4.3 Modelos Instalados

**Endpoint:** `GET /api/tags`

**Resposta esperada:**
```json
{
    "models": [
        {
            "name": "llama3:8b",
            "size": 4700000000,
            "modified_at": "2024-12-01T10:00:00Z",
            "details": {
                "format": "gguf",
                "family": "llama",
                "parameter_size": "8B",
                "quantization_level": "Q4_K_M"
            }
        },
        {
            "name": "nomic-embed-text",
            "size": 274000000,
            "modified_at": "2024-11-15T08:30:00Z",
            "details": {
                "format": "gguf",
                "family": "bert",
                "parameter_size": "80M"
            }
        }
    ]
}
```

**Implementação:**
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class OllamaModel:
    name: str
    size_bytes: int
    modified_at: datetime
    parameter_size: str  # "8B", "9B", "80M", etc.
    quantization: str | None  # "Q4_K_M", None se embedding
    is_embedding: bool  # True se modelo de embeddings

async def list_ollama_models(base_url: str) -> list[OllamaModel]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{base_url}/api/tags")
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        models = []
        for m in data.get("models", []):
            details = m.get("details", {})
            param_size = details.get("parameter_size", "unknown")
            quant = details.get("quantization_level")
            
            # Detectar se é modelo de embedding
            is_embedding = "embed" in m["name"].lower() or \
                          details.get("family", "").lower() in ("bert", "embedding")
            
            models.append(OllamaModel(
                name=m["name"],
                size_bytes=m.get("size", 0),
                modified_at=datetime.fromisoformat(m["modified_at"].replace("Z", "+00:00")),
                parameter_size=param_size,
                quantization=quant,
                is_embedding=is_embedding
            ))
        return models
```

### 4.4 Modelos Carregados Atualmente

**Endpoint:** `GET /api/ps` (processos ativos)

**Resposta esperada:**
```json
{
    "models": [
        {
            "name": "llama3:8b",
            "size": 4700000000,
            "digest": "abc123...",
            "expires_at": "2024-12-15T11:00:00Z",
            "size_vram": 4700000000
        }
    ]
}
```

**Implementação:**
```python
async def list_loaded_models(base_url: str) -> list[str]:
    """Retorna lista de nomes de modelos atualmente carregados na VRAM."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{base_url}/api/ps")
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
    return []
```

### 4.5 Capacidades dos Modelos

Para cada modelo descoberto, inferir capacidades:

```python
@dataclass
class ModelCapability:
    model_name: str
    supports_generation: bool      # Gera texto
    supports_chat: bool            # Formato chat
    supports_embedding: bool       # Gera embeddings
    context_length: int            # Tokens de contexto
    parameter_count: str           # "8B", "9B", etc.
    recommended_for: list[str]     # ["general", "code", "math", etc.]

def infer_model_capabilities(model: OllamaModel) -> ModelCapability:
    name_lower = model.name.lower()
    
    # Detectar tipo
    is_embedding = model.is_embedding
    is_chat = "chat" in name_lower or "instruct" in name_lower
    
    # Estimar contexto baseado no nome/quantização
    if "long" in name_lower or "context" in name_lower:
        context_length = 32000
    elif model.quantization and "long" in model.quantization.lower():
        context_length = 16000
    else:
        context_length = 4096  # Padrão conservador
    
    # Recomendações baseadas no nome
    recommended = ["general"]
    if "code" in name_lower or "coder" in name_lower:
        recommended.append("code")
    if "math" in name_lower:
        recommended.append("math")
    if "med" in name_lower or "medical" in name_lower:
        recommended.append("medical")
    
    return ModelCapability(
        model_name=model.name,
        supports_generation=not is_embedding,
        supports_chat=is_chat,
        supports_embedding=is_embedding,
        context_length=context_length,
        parameter_count=model.parameter_size,
        recommended_for=recommended
    )
```

---

## 5. DESCOBERTA DE CAPABILIDADES LOCAIS

### 5.1 Embeddings

**Verificar disponibilidade:**

1. Modelo de embeddings no Ollama (`nomic-embed-text`, `mxbai-embed-large`, etc.)
2. Biblioteca `sentence-transformers` instalada (fallback local)

**Implementação:**
```python
async def check_embeddings_available(ollama_base_url: str) -> tuple[bool, str | None]:
    """Retorna (disponível, modelo_nome)"""
    # Tentar via Ollama
    models = await list_ollama_models(ollama_base_url)
    for m in models:
        if m.is_embedding:
            return (True, m.name)
    
    # Tentar sentence-transformers local
    try:
        from sentence_transformers import SentenceTransformer
        # Teste rápido
        SentenceTransformer('all-MiniLM-L6-v2')
        return (True, "sentence-transformers:all-MiniLM-L6-v2")
    except Exception:
        pass
    
    return (False, None)
```

### 5.2 OCR

**Verificar disponibilidade:**

1. Tesseract OCR instalado no sistema
2. Biblioteca `pytesseract` disponível

**Implementação:**
```python
def check_ocr_available() -> bool:
    try:
        import pytesseract
        # Teste rápido - verificar versão
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False
```

### 5.3 RAG Local

**Verificar disponibilidade:**

1. LanceDB ou Qdrant configurado (já existente em `bibliotecario/`)
2. Documentos indexados presentes

**Implementação:**
```python
import os

def check_rag_available(enxame_data_path: str) -> bool:
    # Verificar se diretório de índices existe
    lancedb_path = os.path.join(enxame_data_path, "lancedb")
    qdrant_path = os.path.join(enxame_data_path, "qdrant")
    
    if os.path.exists(lancedb_path) and os.listdir(lancedb_path):
        return True
    if os.path.exists(qdrant_path) and os.listdir(qdrant_path):
        return True
    
    return False
```

### 5.4 Acesso Web

**Verificar disponibilidade:**

1. Configuração `ALLOW_INTERNET` habilitada
2. Conectividade teste

**Implementação:**
```python
import os
import httpx

def check_web_available() -> bool:
    # Verificar configuração
    allow_internet = os.getenv("ENXAME_ALLOW_INTERNET", "false").lower() == "true"
    if not allow_internet:
        return False
    
    # Testar conectividade
    try:
        resp = httpx.get("https://www.google.com", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False
```

### 5.5 Arquivos ZIM

**Verificar disponibilidade:**

1. Diretório ZIM configurado
2. Arquivos `.zim` presentes

**Implementação:**
```python
def check_zim_available(enxame_data_path: str) -> bool:
    zim_path = os.path.join(enxame_data_path, "zim")
    if not os.path.exists(zim_path):
        return False
    
    # Contar arquivos .zim
    zim_files = [f for f in os.listdir(zim_path) if f.endswith(".zim")]
    return len(zim_files) > 0
```

---

## 6. ABSTRAÇÃO DE PROVIDER

### 6.1 Interface Genérica

```python
from abc import ABC, abstractmethod
from typing import Any

class LLMProvider(ABC):
    """Interface genérica para providers de LLM."""
    
    @abstractmethod
    async def health(self) -> bool:
        """Verificar se provider está saudável."""
        pass
    
    @abstractmethod
    async def list_models(self) -> list[dict[str, Any]]:
        """Listar modelos disponíveis."""
        pass
    
    @abstractmethod
    async def generate(self, model: str, prompt: str, **kwargs) -> str:
        """Gerar resposta usando modelo específico."""
        pass
    
    @abstractmethod
    async def get_loaded_models(self) -> list[str]:
        """Obter modelos atualmente carregados."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Nome do provider (ex: 'ollama', 'vllm', 'lmstudio')."""
        pass
```

### 6.2 Implementação Ollama

```python
class OllamaProvider(LLMProvider):
    """Implementação para Ollama."""
    
    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip('/')
        self._client = httpx.AsyncClient(timeout=120.0)
    
    @property
    def provider_name(self) -> str:
        return "ollama"
    
    async def health(self) -> bool:
        try:
            resp = await self._client.get(f"{self.base_url}/api/tags")
            return resp.status_code == 200
        except Exception:
            return False
    
    async def list_models(self) -> list[dict[str, Any]]:
        resp = await self._client.get(f"{self.base_url}/api/tags")
        resp.raise_for_status()
        return resp.json().get("models", [])
    
    async def generate(self, model: str, prompt: str, **kwargs) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "options": kwargs,
        }
        resp = await self._client.post(
            f"{self.base_url}/api/generate",
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    
    async def get_loaded_models(self) -> list[str]:
        resp = await self._client.get(f"{self.base_url}/api/ps")
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    
    async def close(self) -> None:
        await self._client.aclose()
```

### 6.3 Factory de Providers

```python
from enum import Enum

class ProviderType(Enum):
    OLLAMA = "ollama"
    VLLM = "vllm"
    LMSTUDIO = "lmstudio"
    TGI = "tgi"

def create_provider(provider_type: ProviderType, config: dict) -> LLMProvider:
    """Factory para criar provider baseado no tipo."""
    if provider_type == ProviderType.OLLAMA:
        return OllamaProvider(config.get("base_url", "http://localhost:11434"))
    elif provider_type == ProviderType.VLLM:
        # Implementação futura
        raise NotImplementedError("vLLM provider não implementado ainda")
    elif provider_type == ProviderType.LMSTUDIO:
        # Implementação futura
        raise NotImplementedError("LM Studio provider não implementado ainda")
    elif provider_type == ProviderType.TGI:
        # Implementação futura
        raise NotImplementedError("TGI provider não implementado ainda")
    else:
        raise ValueError(f"Provider type desconhecido: {provider_type}")
```

---

## 7. ESTRUTURA DE CAPABILITIES

### 7.1 Dataclass Principal

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class HardwareCapabilities:
    """Recursos de hardware."""
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
    """Informações de um modelo."""
    name: str
    size_bytes: int
    parameter_size: str
    is_embedding: bool
    is_loaded: bool
    context_length: int
    quantization: str | None
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
    """Capacidades locais da Abelha."""
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
        """Converter para formato do manifesto."""
        manifesto = {
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
        
        return manifesto
```

---

## 8. INTEGRAÇÃO COM MANIFESTO

### 8.1 Atualização do Manifesto

O manifesto da Abelha (definido em BEE-0002) agora inclui:

```json
{
  "identity": {
    "node_id": "uuid-abc",
    "public_key": "base64-pubkey",
    "protocol_version": "1.0"
  },
  "manifesto": {
    "hardware": {
      "os": "Linux",
      "architecture": "x86_64",
      "cpu_cores": 8,
      "ram_gb": 16.0,
      "gpu": "NVIDIA GeForce RTX 3080"
    },
    "capabilities": ["llm_inference", "embeddings", "ocr", "rag", "zim"],
    "models": ["llama3:8b", "gemma2:9b", "nomic-embed-text"],
    "indexes": ["documents", "zim", "memory"],
    "load": 0.3,
    "uptime_seconds": 3600,
    "ollama_version": "0.5.4",
    "bee_version": "1.0.0"
  }
}
```

### 8.2 Decisão de Consulta

Com estas informações, outra Abelha pode decidir:

**Critérios de seleção:**

1. **Tem o modelo necessário?**
   - Precisa de embeddings → Buscar Abelhas com `embeddings` capability
   - Precisa de OCR → Buscar Abelhas com `ocr` capability

2. **Tem conhecimento relevante?**
   - indexes contém `documents` → Tem documentos indexados
   - indexes contém `zim` → Tem arquivos ZIM offline

3. **Está disponível?**
   - load < 0.7 → Disponível
   - load >= 0.7 → Sobrecarregada, evitar

4. **Hardware adequado?**
   - GPU disponível → Melhor para inferência rápida
   - RAM suficiente → Suporta contexto maior

---

## 9. SELEÇÃO DE MODELO RECOMENDADO

### 9.1 Critérios de Seleção

Baseado no hardware disponível, selecionar melhor modelo:

```python
def recommend_model(
    available_models: list[ModelInfo],
    ram_gb: float,
    gpu_vram_gb: float,
    has_gpu: bool
) -> str | None:
    """
    Recomendar melhor modelo baseado em recursos.
    
    Diretrizes:
    - 1B-3B: Mínimo 4GB RAM
    - 4B-7B: Mínimo 8GB RAM
    - 8B-10B: Mínimo 16GB RAM (ou 8GB VRAM com GPU)
    - >10B: Não recomendar nesta fase
    """
    if not available_models:
        return None
    
    candidates = []
    for model in available_models:
        # Pular embeddings para geração
        if model.is_embedding:
            continue
        
        # Extrair tamanho em bilhões
        param_str = model.parameter_size.upper()
        if "B" in param_str:
            billions = float(param_str.replace("B", ""))
        else:
            continue  # Ignorar modelos muito pequenos (<1B)
        
        # Ignorar modelos grandes (>10B) nesta fase
        if billions > 10:
            continue
        
        # Calcular score baseado em adequação ao hardware
        score = 0.0
        
        # RAM adequada?
        min_ram = billions * 1.5  # Regra prática: 1.5GB por bilhão de params
        if ram_gb >= min_ram:
            score += 10
        elif ram_gb >= min_ram * 0.7:
            score += 5  # RAM limitada mas aceitável
        
        # GPU ajuda muito
        if has_gpu and gpu_vram_gb >= billions:
            score += 20  # Modelo cabe inteiro na VRAM
        elif has_gpu and gpu_vram_gb >= billions * 0.5:
            score += 10  # Modelo parcialmente na VRAM
        
        # Preferir modelos já carregados
        if model.is_loaded:
            score += 15
        
        # Preferir modelos de chat para assistente
        if model.supports_chat:
            score += 5
        
        candidates.append((score, model.name, billions))
    
    if not candidates:
        return None
    
    # Ordenar por score (maior primeiro), depois por tamanho (menor primeiro para empate)
    candidates.sort(key=lambda x: (-x[0], x[2]))
    return candidates[0][1]
```

### 9.2 Tabela de Referência

| RAM Total | GPU VRAM | Modelo Recomendado |
|-----------|----------|-------------------|
| 4GB | 0GB | phi3:3.8b, gemma2:2b |
| 8GB | 0GB | llama3:8b, gemma2:9b |
| 8GB | 4GB | llama3:8b (GPU accelerated) |
| 16GB | 8GB | llama3:8b, mixtral:8x7b (quantizado) |
| 32GB+ | 12GB+ | Modelos maiores conforme necessidade |

---

## 10. TESTES

### 10.1 Testes Unitários Obrigatórios

1. **Descoberta de hardware** - Mock de psutil
2. **Descoberta de Ollama** - Mock de HTTP
3. **Lista de modelos** - Parse de resposta API
4. **Detecção de embeddings** - Vários cenários
5. **Detecção de OCR** - Com e sem Tesseract
6. **Seleção de modelo** - Diferentes configs de hardware
7. **Provider factory** - Criar diferentes providers
8. **Integração com manifesto** - Converter para dict

### 10.2 Testes de Integração

1. **Abelha sem Ollama** - Deve funcionar com capacidades limitadas
2. **Abelha com Ollama** - Todas capacidades disponíveis
3. **Abelha com GPU** - Selecionar modelo apropriado
4. **Abelha sem GPU** - Selecionar modelo CPU-friendly

---

## 11. NÃO FUNCIONA NESTA FASE

### 11.1 O Que NÃO Implementar

1. **Instalação automática de modelos** - Usuário decide quais modelos instalar
2. **Download de modelos em background** - Apenas listar existentes
3. **Inferência distribuída** - Modelos rodam localmente em cada Abelha
4. **Fragmentação de modelos grandes** - Não suportar modelos > 10B nesta fase
5. **Especialização forçada** - Todas Abelhas são generalistas

### 11.2 O Que Deixar para Futuro

1. **Suporte a vLLM/TGI** - Provider abstraction prepara terreno
2. **Auto-tuning de modelo** - Seleção automática baseada em uso
3. **Cache de modelos entre Abelhas** - Compartilhamento futuro
4. **Benchmark automático de modelos** - Medição real de performance

---

## 12. RESUMO

Esta especificação define como uma Abelha:

1. ✅ Descobre seu hardware (CPU, RAM, GPU, storage)
2. ✅ Descobre sistema operacional e arquitetura
3. ✅ Descobre Ollama (disponibilidade, versão, modelos)
4. ✅ Descobre capacidades locais (embeddings, OCR, RAG, ZIM, web)
5. ✅ Usa provider abstraction (não apenas Ollama)
6. ✅ Integra informações no manifesto
7. ✅ Recomenda modelo baseado em hardware
8. ✅ Funciona sem Ollama (capacidades limitadas)
9. ✅ NÃO instala modelos automaticamente
10. ✅ NÃO assume Hermes como modelo padrão

---

*Especificação gerada em: 2025*  
*Baseada na auditoria arquitetural do repositório enxamepublic*  
*Alinhada com BEE-0001 e BEE-0002*
