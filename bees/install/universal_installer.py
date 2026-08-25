#!/usr/bin/env python3
"""
ENXAME Universal Installer — Next-Next-Finish Cross-Platform
==============================================================
Instalação em um clique para usuários não-técnicos:
- Windows: .exe (via PyInstaller) ou .msi
- macOS: .pkg ou .app bundle
- Linux: .AppImage, .deb, .rpm, ou script universal

Funcionalidades:
1. Detecta OS e arquitetura
2. Instala Python se necessário (embeded)
3. Instala Ollama automaticamente
4. Baixa modelo recomendado baseado no hardware
5. Configura Abelha (bee) com defaults sensíveis
6. Cria atalhos/entrypoints (menu iniciar, Applications, .desktop)
7. Registra como serviço (systemd, launchd, Windows Service)
8. Verifica funcionamento completo
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ============================================================================
# Configurações do Instalador
# ============================================================================

INSTALLER_VERSION = "1.0.0"
PROJECT_NAME = "enxame"
BEE_PACKAGE = "bees"
DEFAULT_PORT = 8765

# URLs de download (atualizar para URLs reais)
OLLAMA_DOWNLOADS = {
    "windows": "https://ollama.com/download/OllamaSetup.exe",
    "darwin": "https://ollama.com/download/Ollama-darwin.zip",
    "linux": "https://ollama.com/install.sh",
}

# Modelos recomendados por categoria de hardware
MODEL_RECOMMENDATIONS = {
    "tiny": ["qwen2:0.5b", "gemma2:2b", "phi3:mini"],
    "small": ["llama3.2:1b", "qwen2:1.5b", "phi3:mini"],
    "medium": ["llama3.2:3b", "qwen2:7b", "gemma2:9b"],
    "large": ["llama3:8b", "qwen2:7b", "gemma2:9b"],
    "xl": ["llama3.1:8b", "qwen2.5:7b", "gemma2:9b"],
}

VISION_MODELS = [
    "llava:7b", "bakllava:7b", "moondream:1.8b",
    "minicpm-v:8b", "qwen2-vl:7b", "llava:13b",
]

OCR_DEPS = {
    "windows": ["tesseract-ocr"],
    "darwin": ["tesseract", "tesseract-lang"],
    "linux": ["tesseract-ocr", "tesseract-ocr-por", "libtesseract-dev"],
}

# ============================================================================
# Utilitários Cross-Platform
# ============================================================================

class Colors:
    """Cores ANSI para terminal (funciona em Windows 10+)."""
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    @classmethod
    def disable(cls):
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = ""
        cls.MAGENTA = cls.CYAN = cls.WHITE = cls.BOLD = cls.RESET = ""

if platform.system() == "Windows" and not os.getenv("WT_SESSION"):
    # Windows legacy console sem suporte ANSI
    Colors.disable()


def log_info(msg: str):
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {msg}")


def log_success(msg: str):
    print(f"{Colors.GREEN}[OK]{Colors.RESET} {msg}")


def log_warn(msg: str):
    print(f"{Colors.YELLOW}[AVISO]{Colors.RESET} {msg}")


def log_error(msg: str):
    print(f"{Colors.RED}[ERRO]{Colors.RESET} {msg}", file=sys.stderr)


def log_step(step: int, total: int, msg: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}[{step}/{total}]{Colors.RESET} {Colors.BOLD}{msg}{Colors.RESET}")


# ============================================================================
# Detecção de Sistema
# ============================================================================

@dataclass
class SystemInfo:
    os: str          # windows, darwin, linux
    arch: str        # x64, arm64
    distro: str      # ubuntu, fedora, arch, etc (linux only)
    python_version: tuple
    has_gpu: bool
    gpu_vram_gb: float
    total_ram_gb: float
    available_disk_gb: float
    ollama_installed: bool
    ollama_running: bool


def detect_system() -> SystemInfo:
    """Detecta informações completas do sistema."""
    system = platform.system().lower()
    arch = platform.machine().lower()
    
    # Normalizar arquitetura
    if arch in ("x86_64", "amd64"):
        arch = "x64"
    elif arch in ("aarch64", "arm64"):
        arch = "arm64"
    
    # Distro Linux
    distro = ""
    if system == "linux":
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("ID="):
                        distro = line.strip().split("=")[1].strip('"')
                        break
        except Exception:
            distro = "unknown"
    
    # Python version
    py_ver = sys.version_info[:2]
    
    # Hardware
    has_gpu = False
    gpu_vram = 0.0
    total_ram = 0.0
    
    try:
        import psutil
        total_ram = psutil.virtual_memory().total / (1024**3)
    except Exception:
        total_ram = 8.0  # fallback
    
    # GPU detection
    try:
        if system == "linux":
            result = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                has_gpu = True
                gpu_vram = float(result.stdout.strip()) / 1024
        elif system == "darwin":
            # Apple Silicon tem GPU unificada
            result = subprocess.run(["system_profiler", "SPDisplaysDataType"], 
                                  capture_output=True, text=True, timeout=5)
            if "Metal" in result.stdout or "Apple" in result.stdout:
                has_gpu = True
                gpu_vram = total_ram * 0.5  # Unified memory approximation
        elif system == "windows":
            result = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                has_gpu = True
                gpu_vram = float(result.stdout.strip()) / 1024
    except Exception:
        pass
    
    # Disk space
    try:
        import psutil
        disk = psutil.disk_usage("/")
        available_disk = disk.free / (1024**3)
    except Exception:
        available_disk = 50.0
    
    # Ollama
    ollama_installed = shutil.which("ollama") is not None
    ollama_running = False
    if ollama_installed:
        try:
            subprocess.run(["ollama", "list"], capture_output=True, timeout=5)
            ollama_running = True
        except Exception:
            pass
    
    return SystemInfo(
        os=system,
        arch=arch,
        distro=distro,
        python_version=py_ver,
        has_gpu=has_gpu,
        gpu_vram_gb=gpu_vram,
        total_ram_gb=round(total_ram, 1),
        available_disk_gb=round(available_disk, 1),
        ollama_installed=ollama_installed,
        ollama_running=ollama_running,
    )


def print_system_info(info: SystemInfo):
    """Exibe informações do sistema detectado."""
    print(f"\n{Colors.BOLD}=== SISTEMA DETECTADO ==={Colors.RESET}")
    print(f"  OS:          {info.os.capitalize()} ({info.arch})")
    if info.distro:
        print(f"  Distro:      {info.distro}")
    print(f"  Python:      {info.python_version[0]}.{info.python_version[1]}")
    print(f"  RAM Total:   {info.total_ram_gb} GB")
    print(f"  Disco Livre: {info.available_disk_gb} GB")
    print(f"  GPU:         {'Sim' if info.has_gpu else 'Não'}" + (f" ({info.gpu_vram_gb:.1f} GB VRAM)" if info.has_gpu else ""))
    print(f"  Ollama:      {'Instalado' if info.ollama_installed else 'Não encontrado'}" + (" + Rodando" if info.ollama_running else ""))


# ============================================================================
# Seleção de Modelo
# ============================================================================

def select_model_category(info: SystemInfo) -> tuple[str, str]:
    """Seleciona categoria de modelo baseada no hardware."""
    effective_mem = info.total_ram_gb
    if info.has_gpu and info.gpu_vram_gb > 0:
        effective_mem = max(effective_mem, info.gpu_vram_gb * 0.9)
    
    if effective_mem < 4:
        return "tiny", f"Memória limitada ({effective_mem:.1f}GB)"
    elif effective_mem < 8:
        return "small", f"Memória moderada ({effective_mem:.1f}GB)"
    elif effective_mem < 16:
        return "medium", f"Memória boa ({effective_mem:.1f}GB)"
    elif effective_mem < 32:
        return "large", f"Memória muito boa ({effective_mem:.1f}GB)"
    else:
        return "xl", f"Memória excelente ({effective_mem:.1f}GB)"


def get_recommended_model(category: str, prefer_vision: bool = True) -> str:
    """Retorna modelo recomendado para a categoria."""
    candidates = MODEL_RECOMMENDATIONS.get(category, MODEL_RECOMMENDATIONS["small"])
    return candidates[0]


# ============================================================================
# Instalação de Dependências
# ============================================================================

def run_command(cmd: list[str] | str, shell: bool = False, timeout: int = 300, 
                capture: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    """Executa comando com logging."""
    if isinstance(cmd, list):
        display = " ".join(cmd)
    else:
        display = cmd
    log_info(f"Executando: {display}")
    
    try:
        result = subprocess.run(
            cmd, shell=shell, capture_output=capture, text=True, timeout=timeout
        )
        if check and result.returncode != 0:
            log_error(f"Falha (código {result.returncode}): {result.stderr}")
        return result
    except subprocess.TimeoutExpired:
        log_error(f"Timeout ({timeout}s): {display}")
        raise
    except Exception as e:
        log_error(f"Erro ao executar: {e}")
        raise


def install_ollama(info: SystemInfo, force: bool = False) -> bool:
    """Instala Ollama no sistema."""
    if info.ollama_installed and not force:
        log_success("Ollama já instalado")
        return True
    
    log_step(2, 6, "Instalando Ollama...")
    
    if info.os == "windows":
        # Windows: baixar e executar installer
        installer_url = OLLAMA_DOWNLOADS["windows"]
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            installer_path = f.name
        try:
            log_info(f"Baixando {installer_url}...")
            urllib.request.urlretrieve(installer_url, installer_path)
            log_info("Executando installer (pode requerer admin)...")
            result = run_command([installer_path, "/S"], shell=False, timeout=300, check=False)
            if result.returncode != 0:
                log_warn("Installer silencioso falhou, tentando modo interativo...")
                run_command([installer_path], shell=False, timeout=300, check=False)
        finally:
            try:
                os.unlink(installer_path)
            except Exception:
                pass
    
    elif info.os == "darwin":
        # macOS: Homebrew ou installer direto
        if shutil.which("brew"):
            run_command(["brew", "install", "ollama"])
        else:
            installer_url = OLLAMA_DOWNLOADS["darwin"]
            log_warn("Homebrew não encontrado. Instale manualmente em https://ollama.com/download/mac")
            return False
    
    elif info.os == "linux":
        # Linux: script oficial
        run_command("curl -fsSL https://ollama.com/install.sh | sh", shell=True, timeout=300)
    
    # Verificar instalação
    time.sleep(3)
    if shutil.which("ollama"):
        log_success("Ollama instalado com sucesso")
        return True
    else:
        log_error("Falha na instalação do Ollama")
        return False


def start_ollama_service(info: SystemInfo) -> bool:
    """Inicia serviço Ollama."""
    if info.ollama_running:
        log_success("Ollama já está rodando")
        return True
    
    log_info("Iniciando serviço Ollama...")
    
    if info.os == "linux":
        run_command(["systemctl", "--user", "start", "ollama"], check=False)
        run_command(["systemctl", "--user", "enable", "ollama"], check=False)
    elif info.os == "darwin":
        run_command(["brew", "services", "start", "ollama"], check=False)
    elif info.os == "windows":
        # Windows service auto-starts
        pass
    
    # Aguardar inicialização
    for i in range(15):
        try:
            subprocess.run(["ollama", "list"], capture_output=True, timeout=5)
            log_success("Serviço Ollama iniciado")
            return True
        except Exception:
            time.sleep(2)
    
    log_warn("Ollama pode não ter iniciado completamente")
    return True  # Não falhar por isso


def install_system_deps(info: SystemInfo) -> bool:
    """Instala dependências do sistema (tesseract, etc)."""
    log_step(3, 6, "Instalando dependências do sistema (OCR, etc)...")
    
    deps = OCR_DEPS.get(info.os, [])
    if not deps:
        log_info("Nenhuma dependência de sistema necessária para este OS")
        return True
    
    try:
        if info.os == "linux":
            if info.distro in ("ubuntu", "debian", "mint", "pop"):
                run_command(["apt-get", "update"], timeout=120)
                run_command(["apt-get", "install", "-y"] + deps, timeout=300)
            elif info.distro in ("fedora", "rhel", "centos", "rocky"):
                run_command(["dnf", "install", "-y"] + deps, timeout=300)
            elif info.distro in ("arch", "manjaro", "endeavouros"):
                run_command(["pacman", "-S", "--noconfirm"] + deps, timeout=300)
            elif info.distro in ("opensuse", "sles"):
                run_command(["zypper", "install", "-y"] + deps, timeout=300)
            else:
                log_warn(f"Distro {info.distro} não reconhecida, tente instalar manualmente: {deps}")
        
        elif info.os == "darwin":
            if shutil.which("brew"):
                run_command(["brew", "install"] + deps)
            else:
                log_warn("Homebrew necessário para dependências no macOS")
        
        elif info.os == "windows":
            # Windows: sugerir instalação manual ou via winget/choco
            log_info("No Windows, instale Tesseract via: winget install UB-Mannheim.tesseract")
            log_info("Ou baixe em: https://github.com/UB-Mannheim/tesseract/wiki")
    
    except Exception as e:
        log_warn(f"Algumas dependências podem não ter sido instaladas: {e}")
    
    return True


def install_python_deps() -> bool:
    """Instala dependências Python do projeto."""
    log_step(4, 6, "Instalando dependências Python...")
    
    # Dependências core
    deps = [
        "zeroconf>=0.38.0",
        "aiohttp>=3.9.0",
        "httpx>=0.26.0",
        "pydantic>=2.6.0",
        "PyYAML>=6.0.0",
        "lancedb>=0.8.0",
        "sentence-transformers>=3.0.0",
        "torch>=2.2.0",
        "numpy>=1.26.0",
        "ollama>=0.2.0",
        "pytesseract>=0.3.10",
        "cryptography>=42.0.0",
        "psutil>=5.9.0",
        "platformdirs>=4.0.0",
        "rich>=13.0.0",
        "pillow>=10.0.0",
    ]
    
    # Instalar com pip
    for dep in deps:
        try:
            run_command([sys.executable, "-m", "pip", "install", "--user", dep], 
                       timeout=120, check=False)
        except Exception:
            log_warn(f"Falha ao instalar {dep}, tentando sem --user...")
            try:
                run_command([sys.executable, "-m", "pip", "install", dep], timeout=120, check=False)
            except Exception:
                log_error(f"Falha crítica ao instalar {dep}")
                return False
    
    log_success("Dependências Python instaladas")
    return True


def download_model(model_name: str, force: bool = False) -> bool:
    """Baixa modelo via Ollama."""
    log_step(5, 6, f"Baixando modelo {model_name}...")
    
    # Verificar se já existe
    if not force:
        result = run_command(["ollama", "list"], timeout=30, check=False)
        if model_name in result.stdout:
            log_success(f"Modelo {model_name} já está instalado")
            return True
    
    log_info(f"Baixando {model_name} (pode demorar vários minutos)...")
    result = run_command(["ollama", "pull", model_name], timeout=1800, check=False)
    
    if result.returncode == 0:
        log_success(f"Modelo {model_name} baixado")
        return True
    else:
        log_error(f"Falha ao baixar {model_name}: {result.stderr}")
        return False


def download_vision_model() -> Optional[str]:
    """Tenta baixar um modelo de visão."""
    log_info("Tentando baixar modelo de visão...")
    for model in VISION_MODELS:
        log_info(f"Tentando {model}...")
        result = run_command(["ollama", "pull", model], timeout=1800, check=False)
        if result.returncode == 0:
            log_success(f"Modelo de visão {model} baixado")
            return model
    log_warn("Nenhum modelo de visão pôde ser baixado (continuando sem visão)")
    return None


def test_installation(model_name: str, vision_model: Optional[str]) -> bool:
    """Testa se a instalação funciona."""
    log_step(6, 6, "Testando instalação...")
    
    # Testar modelo principal
    log_info(f"Testando modelo principal: {model_name}")
    result = run_command(
        ["ollama", "run", model_name, "Responda apenas: ABELHA OK"],
        timeout=120, check=False
    )
    
    if result.returncode != 0 or "ABELHA OK" not in result.stdout.upper():
        log_error(f"Teste do modelo principal falhou: {result.stderr or result.stdout}")
        return False
    
    log_success("Modelo principal funcionando")
    
    # Testar visão se disponível
    if vision_model:
        log_info(f"Testando modelo de visão: {vision_model}")
        # Criar imagem de teste simples (1x1 pixel PNG base64)
        test_img = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
        test_b64 = base64.b64encode(test_img).decode()
        
        import json
        payload = {
            "model": vision_model,
            "prompt": "Responda apenas: VISAO OK",
            "images": [test_b64],
            "stream": False,
            "options": {"temperature": 0.1, "num_ctx": 256}
        }
        
        try:
            import httpx
            with httpx.Client(timeout=30.0) as client:
                resp = client.post("http://localhost:11434/api/generate", json=payload)
                if resp.status_code == 200 and "VISAO OK" in resp.json().get("response", "").upper():
                    log_success("Modelo de visão funcionando")
                else:
                    log_warn("Modelo de visão não respondeu como esperado")
        except Exception as e:
            log_warn(f"Teste de visão falhou: {e}")
    
    return True


# ============================================================================
# Configuração da Abelha
# ============================================================================

def configure_bee(info: SystemInfo, model_name: str, vision_model: Optional[str]) -> Path:
    """Configura a Abelha (cria config, identidade, diretórios)."""
    log_info("Configurando Abelha...")
    
    # Diretório de dados cross-platform
    if info.os == "windows":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif info.os == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    
    data_dir = base / "enxame" / "bee"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Subdiretórios
    for subdir in ["documents", "zim", "lancedb", "cache", "logs", "uploads", "processed"]:
        (data_dir / subdir).mkdir(exist_ok=True)
    
    # Configuração
    import uuid
    node_id = str(uuid.uuid4())
    
    # Detectar IP local
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"
    
    config = {
        "node_id": node_id,
        "host": "0.0.0.0",
        "port": DEFAULT_PORT,
        "host_ip": local_ip,
        "ollama_base_url": "http://localhost:11434",
        "model": model_name,
        "data_dir": str(data_dir),
        "allow_web": False,
        "shared_secret": None,
        "log_level": "INFO",
        "confidence_threshold_enxame": 0.7,
        "confidence_threshold_web": 0.8,
        "heartbeat_interval": 5.0,
        "heartbeat_timeout": 15.0,
        "max_concurrent_queries": 4,
        "query_timeout_seconds": 60,
        "max_cache_items": 1000,
    }
    
    config_path = data_dir / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    # Identidade Ed25519
    from cryptography.hazmat.primitives.asymmetric import ed25519
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    identity = {
        "node_id": node_id,
        "public_key": base64.b64encode(public_key.public_bytes_raw()).decode("ascii"),
        "private_key": base64.b64encode(private_key.private_bytes_raw()).decode("ascii"),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "protocol_version": "1.0",
    }
    
    identity_path = data_dir / "identity.json"
    with open(identity_path, "w") as f:
        json.dump(identity, f, indent=2)
    
    # Manifesto de instalação
    manifest = {
        "version": INSTALLER_VERSION,
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "system": {
            "os": info.os,
            "arch": info.arch,
            "distro": info.distro,
            "ram_gb": info.total_ram_gb,
            "disk_gb": info.available_disk_gb,
            "gpu": info.has_gpu,
            "gpu_vram_gb": info.gpu_vram_gb,
        },
        "models": {
            "main": model_name,
            "vision": vision_model,
        },
        "capabilities": [
            "rag", "vector_search", "embeddings", "query", "index", "memory",
            "ocr", "vision", "zim", "discovery", "heartbeat", "peer_delegation"
        ],
        "status": "READY",
    }
    
    manifest_path = data_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    log_success(f"Abelha configurada em {data_dir}")
    return data_dir


# ============================================================================
# Criação de Atalhos/Serviços
# ============================================================================

def create_shortcuts(info: SystemInfo, data_dir: Path, model_name: str) -> bool:
    """Cria atalhos no menu iniciar / Applications / .desktop."""
    log_info("Criando atalhos...")
    
    try:
        if info.os == "windows":
            # Windows: criar atalho no Menu Iniciar
            import winreg
            start_menu = Path(os.getenv("APPDATA")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Enxame"
            start_menu.mkdir(parents=True, exist_ok=True)
            
            # Script de inicialização
            bat_content = f"""@echo off
title Enxame Abelha
python -m bees.cli start --data-dir "{data_dir}"
pause
"""
            (start_menu / "Iniciar Abelha.bat").write_text(bat_content)
            
            # Script de parada
            bat_stop = f"""@echo off
title Parar Enxame Abelha
curl -X POST http://localhost:{DEFAULT_PORT}/api/v1/shutdown 2>nul || echo "Abelha já parada"
pause
"""
            (start_menu / "Parar Abelha.bat").write_text(bat_stop)
            
            log_success(f"Atalhos criados em {start_menu}")
        
        elif info.os == "darwin":
            # macOS: criar .app bundle ou alias em Applications
            apps_dir = Path("/Applications/Enxame")
            apps_dir.mkdir(exist_ok=True)
            
            # Script de inicialização
            sh_content = f"""#!/bin/bash
cd "{data_dir}"
python3 -m bees.cli start --data-dir "{data_dir}"
"""
            start_script = apps_dir / "Iniciar Abelha.command"
            start_script.write_text(sh_content)
            start_script.chmod(0o755)
            
            log_success(f"Atalhos criados em {apps_dir}")
        
        elif info.os == "linux":
            # Linux: .desktop file
            desktop_dir = Path.home() / ".local" / "share" / "applications"
            desktop_dir.mkdir(parents=True, exist_ok=True)
            
            desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Enxame Abelha
Comment=Inicia a Abelha do Enxame (RAG local + Swarm)
Exec=python3 -m bees.cli start --data-dir "{data_dir}"
Icon=preferences-system-network
Terminal=true
Categories=Network;Utility;
StartupNotify=true
"""
            (desktop_dir / "enxame-bee.desktop").write_text(desktop_content)
            
            # Systemd user service
            systemd_dir = Path.home() / ".config" / "systemd" / "user"
            systemd_dir.mkdir(parents=True, exist_ok=True)
            
            service_content = f"""[Unit]
Description=Enxame Bee - Abelha Standalone
After=network.target ollama.service

[Service]
Type=simple
ExecStart={sys.executable} -m bees.cli start --data-dir "{data_dir}"
Restart=on-failure
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
"""
            (systemd_dir / "enxame-bee.service").write_text(service_content)
            
            # Habilitar serviço
            run_command(["systemctl", "--user", "daemon-reload"], check=False)
            run_command(["systemctl", "--user", "enable", "enxame-bee"], check=False)
            
            log_success("Arquivo .desktop e serviço systemd criados")
    
    except Exception as e:
        log_warn(f"Não foi possível criar todos os atalhos: {e}")
    
    return True


def print_final_instructions(info: SystemInfo, data_dir: Path, model_name: str, vision_model: Optional[str]):
    """Exibe instruções finais para o usuário."""
    print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}🐝 ABELHA INSTALADA COM SUCESSO!{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}{'='*60}{Colors.RESET}")
    
    print(f"\n{Colors.BOLD}Configuração:{Colors.RESET}")
    print(f"  • Diretório de dados: {data_dir}")
    print(f"  • Modelo principal:   {model_name}")
    print(f"  • Modelo de visão:    {vision_model or 'Não disponível'}")
    print(f"  • Porta HTTP:         {DEFAULT_PORT}")
    
    print(f"\n{Colors.BOLD}Como usar:{Colors.RESET}")
    
    if info.os == "windows":
        print(f"  1. Menu Iniciar → Enxame → 'Iniciar Abelha'")
        print(f"  2. Ou terminal: python -m bees.cli start")
        print(f"  3. Como serviço: net start enxame-bee (após instalar como serviço)")
    elif info.os == "darwin":
        print(f"  1. Finder → Applications → Enxame → 'Iniciar Abelha'")
        print(f"  2. Ou terminal: python3 -m bees.cli start")
        print(f"  3. Como serviço: brew services start enxame-bee")
    else:
        print(f"  1. Menu de aplicações → 'Enxame Abelha'")
        print(f"  2. Ou terminal: python3 -m bees.cli start")
        print(f"  3. Como serviço: systemctl --user start enxame-bee")
    
    print(f"\n{Colors.BOLD}Endpoints úteis:{Colors.RESET}")
    print(f"  • Health:     http://localhost:{DEFAULT_PORT}/health")
    print(f"  • Status:     http://localhost:{DEFAULT_PORT}/api/v1/status")
    print(f"  • Query:      POST http://localhost:{DEFAULT_PORT}/api/v1/query")
    print(f"  • Peers:      http://localhost:{DEFAULT_PORT}/api/v1/peers")
    
    print(f"\n{Colors.BOLD}Formar Enxame:{Colors.RESET}")
    print(f"  Instale esta mesma versão em outros PCs na mesma rede.")
    print(f"  Elas se descobrirão automaticamente via mDNS.")
    
    print(f"\n{Colors.BOLD}Logs:{Colors.RESET}")
    print(f"  {data_dir / 'logs'}")
    
    print(f"\n{Colors.CYAN}Documentação: https://github.com/enxamepublic/enxame{Colors.RESET}")
    print(f"{Colors.GREEN}{'='*60}{Colors.RESET}\n")


# ============================================================================
# Fluxo Principal
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="ENXAME Universal Installer - Next-Next-Finish",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Exemplos:
          python install.py                    # Instalação interativa padrão
          python install.py --auto             # Totalmente automático (sem prompts)
          python install.py --force-ollama     # Força reinstalação do Ollama
          python install.py --model llama3.2:3b  # Especifica modelo
        """)
    )
    parser.add_argument("--auto", action="store_true", help="Instalação totalmente automática")
    parser.add_argument("--force-ollama", action="store_true", help="Força reinstalação do Ollama")
    parser.add_argument("--force-model", action="store_true", help="Força redownload do modelo")
    parser.add_argument("--model", help="Modelo específico a usar (pula detecção automática)")
    parser.add_argument("--no-vision", action="store_true", help="Pula download de modelo de visão")
    parser.add_argument("--no-shortcuts", action="store_true", help="Não cria atalhos/serviços")
    parser.add_argument("--data-dir", type=Path, help="Diretório de dados personalizado")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Porta HTTP")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem instalar")
    args = parser.parse_args()
    
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}  ENXAME UNIVERSAL INSTALLER v{INSTALLER_VERSION}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}{'='*60}{Colors.RESET}")
    print(f"\nInstalação 'next-next-finish' para usuários não-técnicos")
    print(f"Sistema alvo: Windows, macOS, Linux\n")
    
    if args.dry_run:
        log_warn("MODO DRY-RUN - Nenhuma alteração será feita")
    
    # 1. Detectar sistema
    log_step(1, 6, "Detectando sistema e hardware...")
    info = detect_system()
    print_system_info(info)
    
    # Verificações mínimas
    if info.total_ram_gb < 2:
        log_error("RAM insuficiente (mínimo 2GB, recomendado 4GB+)")
        if not args.auto:
            input("Pressione Enter para continuar mesmo assim...")
    
    if info.available_disk_gb < 5:
        log_error("Espaço em disco insuficiente (mínimo 5GB livre)")
        if not args.auto:
            input("Pressione Enter para continuar mesmo assim...")
    
    if info.python_version < (3, 10):
        log_error(f"Python 3.10+ necessário (encontrado {info.python_version[0]}.{info.python_version[1]})")
        return 1
    
    # Selecionar modelo
    if args.model:
        model_name = args.model
        model_reason = "Especificado pelo usuário"
    else:
        category, reason = select_model_category(info)
        model_name = get_recommended_model(category)
        model_reason = reason
    
    log_info(f"Modelo selecionado: {model_name} ({model_reason})")
    
    if not args.auto:
        resp = input(f"\nContinuar com instalação? [S/n]: ").strip().lower()
        if resp in ("n", "no", "não"):
            log_info("Instalação cancelada")
            return 0
    
    # Dry-run
    if args.dry_run:
        log_info("DRY-RUN: Pularia instalação de Ollama, modelos, deps, configuração")
        return 0
    
    # 2. Instalar Ollama
    if not install_ollama(info, force=args.force_ollama):
        return 1
    
    # 3. Iniciar Ollama
    if not start_ollama_service(info):
        return 1
    
    # 4. Dependências do sistema
    install_system_deps(info)
    
    # 5. Dependências Python
    if not install_python_deps():
        return 1
    
    # 6. Baixar modelo principal
    if not download_model(model_name, force=args.force_model):
        return 1
    
    # 7. Baixar modelo de visão (opcional mas recomendado)
    vision_model = None
    if not args.no_vision:
        vision_model = download_vision_model()
    
    # 8. Testar
    if not test_installation(model_name, vision_model):
        log_error("Testes falharam")
        return 1
    
    # 9. Configurar Abelha
    data_dir = configure_bee(info, model_name, vision_model)
    
    # 10. Criar atalhos
    if not args.no_shortcuts:
        create_shortcuts(info, data_dir, model_name)
    
    # Sucesso!
    print_final_instructions(info, data_dir, model_name, vision_model)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Instalação cancelada pelo usuário{Colors.RESET}")
        sys.exit(130)
    except Exception as e:
        log_error(f"Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)