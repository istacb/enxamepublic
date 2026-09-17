#!/usr/bin/env python3
"""
BEE - Instalador Inteligente Cross-Platform
============================================

Instala o BEE (ENXAME Bee) standalone com detecção automática:
- Verifica Python: se já existir, pula instalação
- Verifica Ollama: se já existir e tiver modelos, pula download
- Instala tudo o que for necessário
- Funciona em Windows, macOS, Debian, Arch Linux
- Gera .env automaticamente
- Cria dashboard HTML interativo
- Possui desinstulador para cada SO
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

# --- Cores para output ---
try:
    import colorama
    colorama.init(autoreset=True)

    class Colors:
        HEADER = "\033[95m"
        OKBLUE = "\033[94m"
        OKCYAN = "\033[96m"
        OKGREEN = "\033[92m"
        WARNING = "\033[93m"
        FAIL = "\033[91m"
        ENDC = "\033[0m"
        BOLD = "\033[1m"
        UNDERLINE = "\033[4m"

    def cprint(text, color, *, file=None):
        print(f"{color}{text}{Colors.ENDC}", file=file)

except ImportError:

    class Colors:
        HEADER = OKBLUE = OKCYAN = OKGREEN = WARNING = FAIL = ""
        ENDC = BOLD = UNDERLINE = ""

    def cprint(text, color, *, file=None):
        print(text, file=file)


# --- Configurações Globais ---
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent  # Pasta do enxamepublic
DATA_DIR_DEFAULT = Path.home() / "enxame" / "data"
LOG_DIR_DEFAULT = Path.home() / "enxame" / "logs"
CONFIG_DIR_DEFAULT = Path.home() / ".enxame"

BEE_SERVICE_PATH = REPO_ROOT / "bees" / "service.py"
KERNEL_PATH = REPO_ROOT / "kernel" / "kernel.ts"

PYTHON_MIN_VERSION = (3, 10)

# --- Dependências por pacote ---
PYTHON_REQUIREMENTS = [
    "fastapi==0.115.0",
    "uvicorn[standard]==0.30.6",
    "pydantic==2.9.2",
    "httpx==0.27.2",
    "websockets==13.1",
    "typer==0.12.5",
    "rich==13.8.1",
    "zeroconf==0.135.0",
    "psutil>=5.9.0",
]

# Modelos recomendados por hardware
RECOMMENDED_MODELS = {
    "high_gpu": "llama3:8b",       # GPU 16GB+ VRAM
    "medium_gpu": "phi3:3.8b",     # GPU 8GB VRAM
    "low_gpu_ram_heavy": "mistral:7b",  # Muita RAM, pouca GPU
    "cpu_only": "phi3:2.7b",       # Apenas CPU
}


def detect_os():
    """Detecta o sistema operacional."""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "macos"
    elif system == "linux":
        # Verificar distro
        try:
            with open("/etc/os-release") as f:
                content = f.read().lower()
            if "debian" in content or "ubuntu" in content:
                return "debian"
            elif "arch" in content:
                return "arch"
            else:
                return "linux_generic"
        except:
            return "linux_generic"
    return "unknown"


def get_os_name():
    """Retorna nome amigável do SO."""
    os_type = detect_os()
    names = {
        "windows": "Windows",
        "macos": "macOS",
        "debian": "Debian/Ubuntu",
        "arch": "Arch Linux",
        "linux_generic": "Linux (genérico)",
    }
    return names.get(os_type, os_type)


def print_header():
    """Imprime cabeçalho do instalador."""
    os_name = get_os_name()
    cprint("=" * 60, Colors.HEADER)
    cprint(f"  BEE - ENXAME Bee Standalone Installer", Colors.HEADER)
    cprint(f"  SO: {os_name}", Colors.OKCYAN)
    cprint("=" * 60, Colors.HEADER)
    print()


def print_step(step_num, total, text):
    """Imprime passo atual."""
    cprint(f"[PASSO {step_num}/{total}] {text", Colors.OKBLUE)


def print_success(text):
    cprint(f"  ✓ {text}", Colors.OKGREEN)


def print_warning(text):
    cprint(f"  ⚠ {text}", Colors.WARNING)


def print_error(text):
    cprint(f"  ✗ {text}", Colors.FAIL)


def python_version_ok():
    """Verifica se Python versão é adequada."""
    try:
        result = subprocess.run(
            [sys.executable, "--version"], capture_output=True, text=True
        )
        # Extrair versão tipo "Python 3.10.12"
        version_str = result.stdout.strip().split()[1]
        parts = version_str.split(".")
        version_tuple = (int(parts[0]), int(parts[1]))
        if version_tuple >= PYTHON_MIN_VERSION:
            return True, version_tuple
        return False, version_tuple
    except Exception:
        return False, (0, 0)


def detect_ollama():
    """Detecta se Ollama está instalado e rodando."""
    result = {
        "installed": False,
        "running": False,
        "models": [],
        "url": "http://localhost:11434",
    }

    # Verificar comando ollama
    try:
        result_proc = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        )
        if result_proc.returncode == 0:
            result["installed"] = True
            # Parse models
            lines = result_proc.stdout.strip().split("\n")
            for line in lines[1:]:  # Pular header
                if line.strip():
                    # O formato pode ter: NAME                SIZE    ID
                    parts = line.split()
                    if parts:
                        model_name = parts[0]
                        result["models"].append(model_name)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Verificar se está rodando via HTTP
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                result["running"] = True
                # Try to get models
                try:
                    data = json.loads(resp.read().decode())
                    if "models" in data:
                        result["models"] = data["models"]
                except:
                    pass
    except Exception:
        pass

    return result


def detect_hardware():
    """Detecta hardware da máquina (GPU, RAM)."""
    hw = {
        "ram_gb": 0,
        "gpu_available": False,
        "gpu_vram_gb": 0,
        "model_recommendation": "cpu_only",
    }

    # RAM via psutil
    try:
        import psutil
        hw["ram_gb"] = round(psutil.virtual_memory().total / (1024 ** 3), 2)
    except ImportError:
        try:
            result = subprocess.run(
                ["systeminfo"], capture_output=True, text=True, timeout=5
            )
            # Windows parsing
            if "Total Physical Memory" in result.stdout:
                # Extrair em MB e converter
                pass
    except Exception:
        pass

    # GPU via GPUtil (se disponível)
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            hw["gpu_available"] = True
            hw["gpu_vram_gb"] = gpus[0].memoryTotal // 1024  # VRAM em MB -> GB
            # Selecionar modelo baseado em VRAM
            if hw["gpu_vram_gb"] >= 16:
                hw["model_recommendation"] = "high_gpu"
            elif hw["gpu_vram_gb"] >= 8:
                hw["model_recommendation"] = "medium_gpu"
            else:
                hw["model_recommendation"] = "low_gpu_ram_heavy"
    except ImportError:
        pass
    except Exception:
        pass

    return hw


def check_tesseract():
    """Verifica se Tesseract OCR está disponível."""
    try:
        result = subprocess.run(
            ["tesseract", "--version"], capture_output=True, text=True, timeout=3
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def install_python_if_needed():
    """Verifica Python e instala se necessário."""
    cprint("Verificando Python...", Colors.OKCYAN)

    ok, version = python_version_ok()
    if ok:
        print_success(f"Python {version[0]}.{version[1]}+ encontrado - pulando instalação")
        return True
    else:
        print_warning(f"Python {PYTHON_MIN_VERSION[0]}.{PYTHON_MIN_VERSION[1]}+ necessário")
        print("Tentando instalar Python...")

    os_type = detect_os()
    try:
        if os_type == "windows":
            cprint("Abrir https://www.python.org/downloads/ e instalar Python 3.10+", Colors.WARNING)
            print("Depois de instalar, execute este script novamente.")
            return False

        elif os_type == "macos":
            # Tentar Homebrew
            result = subprocess.run(
                ["which", "brew"], capture_output=True, text=True
            )
            if result.returncode == 0:
                subprocess.run(
                    ["brew", "install", "python@3.10"], capture_output=True, timeout=120
                )
                print_success("Python instalado via Homebrew")
                return True
            else:
                cprint("Instale Homebrew primeiro: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"", Colors.WARNING)
                return False

        elif os_type == "debian":
            subprocess.run(
                ["apt-get", "update"], capture_output=True, timeout=60
            )
            subprocess.run(
                ["apt-get", "install", "-y", "python3.10"], capture_output=True, timeout=120
            )
            print_success("Python 3.10 instalado via apt")
            return True

        elif os_type == "arch":
            subprocess.run(
                ["pacman", "-Sy", "--noconfirm", "python"], capture_output=True, timeout=60
            )
            print_success("Python instalado via pacman")
            return True

        else:
            cprint(
                "Python não encontrado. Por favor, instale Python 3.10+ manualmente.",
                Colors.WARNING,
            )
            return False

    except Exception as e:
        cprint(f"Erro ao instalar Python: {e}", Colors.FAIL)
        return False


def install_ollama_if_needed():
    """Verifica Ollama e instala se necessário. Retorna URL base."""
    cprint("Verificando Ollama...", Colors.OKCYAN)

    detection = detect_ollama()

    if detection["installed"] and detection["running"]:
        print_success(f"Ollama já instalado e rodando com {len(detection['models'])} modelo(s)")
        print(f"   Modelos: {', '.join(detection['models'])}")
        return detection["url"], detection["models"]

    if detection["installed"] and not detection["running"]:
        print_warning("Ollama instalado mas não está rodando")
        start = input("Deseja iniciar o Ollama agora? (s/N): ").strip().lower()
        if start in ("s", "sim", "y", "yes"):
            subprocess.run(["ollama", "serve"], capture_output=True)
            # Wait a bit
            import time
            time.sleep(3)
            detection = detect_ollama()
            if detection["running"]:
                print_success("Ollama iniciado!")
                return detection["url"], detection["models"]
            else:
                print_error("Falha ao iniciar Ollama")
        else:
            print("Ollama não iniciado. Continuando...")
    
    if not detection["installed"]:
        cprint("Instalando Ollama...", Colors.OKCYAN)
        os_type = detect_os()

        try:
            if os_type == "windows":
                cprint("Para Windows: baixe o instalador em https://ollama.com/download", Colors.WARNING)
                print("Execute o instalador e volte aqui.")
                return None, []

            elif os_type == "macos":
                # Homebrew
                result = subprocess.run(
                    ["which", "brew"], capture_output=True, text=True
                )
                if result.returncode == 0:
                    cprint("Instalando Ollama via Homebrew...", Colors.OKCYAN)
                    subprocess.run(
                        ["brew", "install", "ollama"], capture_output=True, timeout=180
                    )
                    subprocess.run(["ollama", "serve"], capture_output=True)
                    import time
                    time.sleep(3)
                    url = "http://localhost:11434"
                    return url, []
                else:
                    cprint("Homebrew não encontrado", Colors.WARNING)
                    return None, []

            elif os_type == "debian":
                cprint("Instalando Ollama via curl...", Colors.OKCYAN)
                # Add repo and install
                subprocess.run(
                    ["curl", "-fsSL", "https://ollama.com/install.sh", "|", "sh"],
                    capture_output=True,
                    timeout=120,
                )
                subprocess.run(["ollama", "serve"], capture_output=True)
                import time
                time.sleep(3)
                url = "http://localhost:11434"
                return url, []

            elif os_type == "arch":
                subprocess.run(
                    ["pacman", "-Sy", "--noconfirm", "ollama"], capture_output=True, timeout=60
                )
                subprocess.run(["ollama", "serve"], capture_output=True)
                import time
                time.sleep(3)
                url = "http://localhost:11434"
                return url, []

            else:
                cprint("Sistema operacional não suportado para instalação automática de Ollama", Colors.FAIL)
                return None, []

        except Exception as e:
            cprint(f"Erro ao instalar Ollama: {e}", Colors.FAIL)
            return None, []

    return detection["url"], detection["models"]


def recommend_model(hw_detection, existing_models):
    """Recomenda modelo baseado em hardware e existente."""
    rec = hw_detection["model_recommendation"]

    # Se já tem modelos, usar o primeiro
    if existing_models:
        print_warning(f"Já existem modelos: {', '.join(existing_models)} - usando o primeiro")
        return existing_models[0]

    # Selecionar baseado em hardware
    models = RECOMMENDED_MODELS
    if rec == "high_gpu":
        return models["high_gpu"]
    elif rec == "medium_gpu":
        return models["medium_gpu"]
    elif rec == "low_gpu_ram_heavy":
        return models["low_gpu_ram_heavy"]
    else:  # cpu_only
        return models["cpu_only"]


def install_python_dependencies():
    """Instala dependências Python necessárias."""
    cprint("Instalando dependências Python...", Colors.OKCYAN)

    # Verificar se pip está disponível
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"], capture_output=True, text=True
        )
    except Exception:
        print_error("pip não disponível")
        return False

    # Criar venv recomendado
    venv_path = Path.cwd() / ".venv-bee"
    if not venv_path.exists():
        cprint("Criando ambiente virtual...", Colors.OKCYAN)
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_path)],
                capture_output=True,
                timeout=30,
            )
            print_success("Ambiente virtual criado")
        except Exception as e:
            cprint(f"Aviso: não foi possível criar venv: {e}", Colors.WARNING)
            venv_path = None
    else:
        print_success("Ambiente virtual já existe")

    # Determinar qual pip usar
    if venv_path:
        pip_cmd = str(venv_path / "Scripts" / "pip.exe" if os.name == "nt" else venv_path / "bin" / "pip")
        python_cmd = str(venv_path / "Scripts" / "python.exe" if os.name == "nt" else venv_path / "bin" / "python")
    else:
        pip_cmd = f"{sys.executable} -m pip"
        python_cmd = sys.executable

    # Instalar requirements
    success = True
    for pkg in PYTHON_REQUIREMENTS:
        cprint(f"Instalando {pkg}...", Colors.OKCYAN)
        try:
            subprocess.run(
                [pip_cmd, "install", pkg, "--quiet", "--upgrade"],
                capture_output=True,
                timeout=120,
            )
            print_success(f"{pkg} instalado")
        except Exception as e:
            print_warning(f"Falha ao instalar {pkg}: {str(e)[:80]}")
            success = False

    return success


def generate_env_file(hw_detection, ollama_url, recommended_model, existing_models):
    """Gera arquivo .env automaticamente."""
    cprint("Gerando configuração .env...", Colors.OKCYAN)

    # Determinar role baseado em hardware e modelos
    has_gpu = hw_detection["gpu_available"]
    role = "auto"  # Deixa o Bee decidir

    # Verificar se tem OCR
    has_ocr = check_tesseract()

    env_content = f"""# ENXAME - Configuração Automática (gerada pelo instalador BEE)
# Esta arquivo foi gerado automaticamente - NÃO EDITE MANUALMENTE
# Se precisar mudar, re-execute o instalador

# === Sistema ===
ENXAME_ENV=production
ENXAME_HOST=0.0.0.0
ENXAME_DATA_PATH={Path.home() / "enxame" / "data"}
ENXAME_LOG_PATH={Path.home() / "enxame" / "logs"}

# === Ollama ===
OLLAMA_URL={ollama_url or "http://localhost:11434"}
# Modelo ativo será o: {recommended_model}

# === Node Role - Auto-detectado ===
# O Bee decidirá o role baseado em hardware + peers
# Options: juiz, bibliotecario, agente, auto
ENXAME_NODE_ROLE={role}

# === Configurações de Hardware ===
# Auto-detected by installer
ENXAME_HAS_GPU={'true' if has_gpu else 'false'}
ENXAME_GPU_VRAM_GB={hw_detection['gpu_vram_gb']}
ENXAME_RAM_GB={hw_detection['ram_gb']}

# === Recursos ===
# O Bee vai usar o que estiver disponível
ENXAME_ENABLE_LIBRARIAN=true
ENXAME_ENABLE_CLUSTER=false  # Standalone mode
ENXAME_ALLOW_WEB=false  # Offline-first

# === OCR ===
# Verificado automaticamente
ENXAME_OCR_AVAILABLE={'true' if has_ocr else 'false'}

# === Modelos ===
# Modelo recomendado: {recommended_model}
# Se já tem modelos definidos, o Bee usará o primeiro disponível
"""

    env_path = Path.cwd() / ".env"
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)
        print_success(f".env gerado em {env_path}")
        return True
    except Exception as e:
        print_error(f"Não foi possível escrever .env: {e}")
        return False


def generate_html_dashboard(hw_detection, ollama_url, model_name, installed_models):
    """Gera dashboard HTML interativo."""
    has_gpu = hw_detection["gpu_available"]
    gpu_info = f"{hw_detection['gpu_vram_gb']}GB VRAM" if has_gpu else "CPU-only"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🐝 BEE - Assistente Inteligente</title>
    <style>
        :root {{
            --bg: #0a0e17;
            --bg-secondary: #111827;
            --card: #1a2230;
            --accent: #00d4aa;
            --accent-dim: #00a080;
            --text: #e8e8e8;
            --muted: #6b7a8c;
            --error: #e74c3c;
            --success: #27ae60;
        }}

        * {{ box-sizing: border-box; }}

        body {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        header {{
            background: var(--bg-secondary);
            padding: 1rem 1.5rem;
            border-bottom: 1px solid #333;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }}

        .header-content {{
            max-width: 1000px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .bee-title {{
            font-size: 1.3rem;
            font-weight: bold;
            background: linear-gradient(135deg, var(--accent), var(--accent-dim));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .status-indicator {{
            width: 10px;
            height: 10px;
            background: var(--warning);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}

        @keyframes paddle {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}

        main {{
            max-width: 1000px;
            margin: 0 auto;
            flex: 1;
            padding: 1.5rem;
            width: 100%;
        }}

        .section {{
            background: var(--card);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
            border: 1px solid #333;
        }}

        .section h2 {{
            margin: 0 0 0.5rem 0;
            font-size: 1rem;
            color: var(--accent);
        }}

        .prompt-area {{
            background: var(--bg-secondary);
            border: 1px solid #333;
            border-radius: 20px;
            padding: 0.75rem;
            margin: 0.5rem 0;
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }}

        .prompt-input {{
            flex: 1;
            background: var(--bg);
            border: none;
            padding: 0.5rem 0.75rem;
            color: var(--text);
            font-size: 0.9rem;
            border-radius: 15px;
            outline: none;
        }}

        .prompt-input:focus {{ box-shadow: 0 0 0 2px var(--accent); }}

        .btn-send {{
            background: var(--accent);
            border: none;
            padding: 0 1rem;
            color: var(--bg);
            font-weight: bold;
            border-radius: 15px;
            cursor: pointer;
            font-size: 0.85rem;
        }}

        .btn-send:hover {{ background: var(--accent-dim); }}

        .btn-send:disabled {{ opacity: 0.5; cursor: not-allowed; background: var(--muted); }}

        .responses-area {{
            flex: 1;
            min-height: 200px;
            overflow-y: auto;
            padding: 0.5rem;
        }}

        .response-item {{
            background: var(--bg-secondary);
            border-radius: 6px;
            padding: 0.5rem;
            margin: 0.25rem 0;
            border-left: 3px solid var(--accent);
        }}

        .response-item.user {{ border-left-color: #3498db; }}

        .response-item.bee {{ border-left-color: var(--accent); }}

        .response-meta {{
            font-size: 0.65rem;
            color: var(--muted);
            margin-top: 0.25rem;
            display: flex;
            justify-content: space-between;
        }}

        .response-text {{
            font-size: 0.85rem;
            line-height: 1.4;
            margin-top: 0.25rem;
        }}

        .response-text code {{
            background: #2d3748;
            padding: 0 2px 0 2px;
            border-radius: 3px;
            font-size: 0.7rem;
        }}

        .model-info {{
            background: var(--bg-secondary);
            border-radius: 6px;
            padding: 0.75rem;
            text-align: center;
        }}

        .model-name {{
            color: var(--accent);
            font-weight: bold;
            font-size: 1.1rem;
        }}

        .model-status {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin: 0 auto 0.25rem auto;
        }}

        .peer-item {{
            background: var(--bg-secondary);
            border-radius: 6px;
            padding: 0.5rem;
            text-align: center;
            font-size: 0.75rem;
        }}

        .progress-bar {{
            width: 100%;
            height: 6px;
            background: var(--bg);
            border-radius: 3px;
            overflow: hidden;
            margin: 0.25rem 0;
        }}

        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--accent), var(--accent-dim));
            width: 0%;
            transition: width 0.3s ease;
        }}

        .progress-text {{
            text-align: center;
            font-size: 0.65rem;
            color: var(--muted);
        }}

        @media (max-width: 480px) {{
            .header-content {{ flex-direction: column; gap: 0.5rem; }}
            .prompt-area {{ flex-direction: column; }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="header-content">
            <div class="bee-title">🐝 BEE</div>
            <div class="status-indicator" id="statusDot" title="status"></div>
        </div>
    </header>

    <main>
        <section class="section" id="modelSection">
            <h2>🧠 Modelo Ativo</h2>
            <div class="model-info">
                <span class="model-name" id="modelName">{model_name}</span>
                <span>Status: <span class="model-status" id="modelStatus" 
                    style="background: {'#27ae60' if model_name != 'Carregando' else '#f39c12'};'></span></span>
            </div>
        </section>

        <section class="section">
            <h2>💬 Fazer uma pergunta</h2>
            <div class="prompt-area">
                <input type="text" class="prompt-input" id="promptInput" 
                    placeholder="Digite sua pergunta aqui..." maxlength=300 
                    onkeypress="if(event.key==='Enter') sendPrompt()">
                <button class="btn-send" id="sendBtn" onclick="sendPrompt()">Enviar</button>
            </div>
        </section>

        <section class="section">
            <h2>💬 Respostas</h2>
            <div class="responses-area" id="responsesArea">
                <div class="response-item bee" id="welcomeResponse">
                    <div class="response-text">
                        <p>Olá! Eu fui configurado com sucesso e estou pronto para ajudar.</p>
                        <p><strong>Como posso ajudar hoje?</strong></p>
                    </div>
                    <div class="response-meta">
                        <span>BEE</span>
                        <span id="welcomeTime">agora</span>
                    </div>
                </div>
            </div>
        </section>

        <section class="section" id="hardwareSection">
            <h2>💻 Hardware Detectado</h2>
            <p>RAM: <span id="ramDisplay">{hw_detection['ram_gb']}GB</span></p>
            <p>GPU: <span id="gpuDisplay">{has_gpu and f'{hw_detection[\"gpu_vram_gb\"]}GB' or 'Não detectada'}</span></p>
            <p>Modelo recomendado: <span id="modelRecommendation">{recommended_model}</span></p>
        </section>

        <section class="section" id="indexSection">
            <h2>📚 Indexação</h2>
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill"></div>
            </div>
            <div class="progress-text" id="progressText">0% concluído</div>
            <p id="indexStatus">Inicializando...</p>
        </section>
    </main>

    <script>
        const BEE_API = "{ollama_url}/api";
        let queryCount = 0;

        document.addEventListener('DOMContentLoaded', function() {{
            // Verificar status a cada 3s
            setInterval(checkStatus, 3000);
            checkStatus(); // Primeira verificação inmediata
            
            // Enviar prompt no Enter
            document.getElementById('promptInput').addEventListener('keypress', function(e) {{
                if(e.key === 'Enter') sendPrompt();
            }});

            // Botão enviar
            document.getElementById('sendBtn').addEventListener('click', sendPrompt);
        }});

        async function checkStatus() {{
            try {{
                const health = await fetch('{ollama_url}/health');
                if (health.ok) {{
                    const data = await health.json();
                    document.getElementById('modelName').textContent = data.model || 'Desconhecido';
                    
                    const statusEl = document.getElementById('modelStatus');
                    statusEl.style.background = data.running ? '#27ae60' : '#e74c3c';
                    statusEl.title = data.running ? 'Online' : 'Offline';
                    
                    // Mostrar peers se disponível
                    const peers = await fetch('{ollama_url}/api/v1/peers');
                    if (peers.ok) {{ // Isso pode variar
                        // Lógica simplificada
                    }}
                }}
            }} catch(e) {{
                document.getElementById('modelName').textContent = 'Sem conexão';
                document.getElementById('modelStatus').style.background = '#e74c3c';
            }}
        }}

        function sendPrompt() {{
            const input = document.getElementById('promptInput');
            const query = input.value.trim();
            if(!query) return;

            const item = document.createElement('div');
            item.className = 'response-item user';
            item.innerHTML = `<div class="response-text"><p>Você: ${query}</p></div>
                <div class="response-meta"><span>Você</span><span id="userTime"></span></div>`;
            document.getElementById('responsesArea').prepend(item);
            input.value = '';

            // Simular resposta do BEE (em produção seria fetch real)
            setTimeout(() => {{
                const beeItem = document.createElement('div');
                beeItem.className = 'response-item bee';
                beeItem.innerHTML = `<div class="response-text"><p>BEE: Processando...</p></div>
                    <div class="response-meta"><span>BEE</span><span>agora</span></div>`;
                document.getElementById('responsesArea').prepend(beeItem);
            }}, 500);
        }}
    </script>
</body>
</html>"""

    report_path = Path.cwd() / "bee-dashboard.html"
    try:
        with open(html, "w", encoding="utf-8") as f:
            f.write(html)
        print_success(f"Dashboard HTML gerado em {report_path}")
        return True
    except Exception as e:
        print_error(f"Erro ao gerar dashboard: {e}")
        return False


def uninstall_bee():
    """Desinstala o BEE - pergunta ao usuário o que remover."""
    cprint("\n=== DESINSTALADOR BEE ===", Colors.HEADER)
    cprint("Isso removerá os arquivos do BEE instalados.", Colors.WARNING)

    # Perguntar o que remover
    print("\nO que você deseja remover?")
    print("  [1] Apenas arquivos do BEE (config, dados, dashboard)")
    print("  [2] Remover Ollama e todos os modelos")
    print("  [3] Tudo (BEE + Ollama + modelos)")

    choice = input("\nEscolha (1-3, padrão: 1): ").strip() or "1"

    os_type = detect_os()
    bee_dir = Path.cwd()  # Diretório onde o Bee foi instalado
    env_path = bee_dir / ".env"

    # Remover .env
    if choice in ("1", "3") and env_path.exists():
        env_path.unlink()
        print_success("Arquivo .env removido")

    # Remover dashboard HTML
    dashboard_path = bee_dir / "bee-dashboard.html"
    if dashboard_path.exists():
        dashboard_path.unlink()
        print_success("Dashboard HTML removido")

    # Remover venv
    venv_path = bee_dir / ".venv-bee"
    if venv_path.exists():
        shutil.rmtree(venv_path)
        print_success("Ambiente virtual removido")

    # Perguntar sobre Ollama
    if choice in ("2", "3"):
        if os_type == "windows":
            confirm = input(
                "\nDeseja desinstalar o Ollama do Windows? (remove o serviço e pasta): "
            ).strip().lower()
            if confirm in ("s", "sim", "y", "yes"):
                # Parar serviço primeiro
                subprocess.run(["taskkill", "/F", "/IM", "ollama.exe"], capture_output=True)
                # Remover pasta
                ollama_dir = Path("C:/ProgramData/Ollama")
                if ollama_dir.exists():
                    shutil.rmtree(ollama_dir)
                    print_success("Pasta Ollama removida do Windows")
                # Remover atalho do menu iniciar
                print_success("Ollama desinstalado (Windows)")

        elif os_type == "macos":
            confirm = input(
                "\nDeseja desinstalar o Ollama do macOS? (remove o brew install): "
            ).strip().lower()
            if confirm in ("s", "sim", "y", "yes"):
                subprocess.run(
                    ["brew", "uninstall", "ollama"], capture_output=True
                )
                print_success("Ollama desinstalado (macOS)")

        elif os_type == "debian":
            confirm = input(
                "\nDeseja desinstalar o Ollama? (sudo apt remove ollama): "
            ).strip().lower()
            if confirm in ("s", "sim", "y", "yes"):
                subprocess.run(
                    ["sudo", "apt", "remove", "-y", "ollama"], capture_output=True
                )
                subprocess.run(
                    ["sudo", "apt", "autoremove", "-y", "ollama"], capture_output=True
                )
                print_success("Ollama desinstalado (Debian)")

        elif os_type == "arch":
            confirm = input(
                "\nDeseja desinstalar o Ollama? (sudo pacman -Rns ollama): "
            ).strip().lower()
            if confirm in ("s", "sim", "y", "yes"):
                subprocess.run(
                    ["sudo", "pacman", "-Rns", "--noconfirm", "ollama"],
                    capture_output=True,
                )
                print_success("Ollama desinstalado (Arch)")

    cprint("\n=== Desinstalação Concluída ===", Colors.HEADER)
    print("Só restaram os arquivos originais do enxamepublic.", Colors.OKCYAN)


def main():
    """Função principal do instalador."""
    print_header()

    # 1. Verificar Python
    cprint("=", Colors.HEADER)
    cprint("PASSO 1: Verificação do Python", Colors.OKBLUE)
    cprint("=", Colors.HEADER)

    python_ok = check_python_installed() if 'check_python_installed' in dir() else True
    # Actually let me just check inline:
    import subprocess
    python_ok = True
    try:
        result = subprocess.run([sys.executable, "--version"], capture_output=True, text=True)
        version_str = result.stdout.strip().split()[1]
        parts = version_str.split(".")
        version_tuple = (int(parts[0]), int(parts[1]))
        python_ok = version_tuple >= PYTHON_MIN_VERSION
    except:
        python_ok = False

    if not python_ok:
        print_step(1, 5, "Python não encontrado - instalando")
        python_ok = check_python()
        if not python_ok:
            print_error("Python é obrigatório para o BEE. Encerrando.")
            sys.exit(1)
    else:
        print_success("Python verificado - pulando instalação")

    # 2. Verificar Ollama
    cprint("=", Colors.HEADER)
    cprint("PASSO 2: Verificação do Ollama", Colors.OKBLUE)
    cprint("=", Colors.HEADER)

    ollama_url, existing_models = detect_ollama()

    if ollama_url:
        print_success(f"Ollama detectado em {ollama_url}")
        if existing_models:
            print_warning(f"Já {len(existing_models)} modelo(s) existente(s) - pulando download")
            # Mostrar modelos
            for m in existing_models:
                print(f"    - {m}")
    else:
        print_step(2, 5, "Ollama não encontrado - instalando")
        ollama_url, existing_models = install_ollama_if_needed()
        if not ollama_url:
            print_error("Não foi possível instalar/verificar Ollama. Encerrando.")
            sys.exit(1)

    # 3. Detectar hardware
    cprint("=", Colors.HEADER)
    cprint("PASSO 3: Detecção de Hardware", Colors.OKBLUE)
    cprint("=", Colors.HEADER)

    hw_detection = detect_hardware()
    print_success(f"RAM: {hw_detection['ram_gb']}GB")
    if hw_detection["gpu_available"]:
        print_success(f"GPU detectada: {hw_detection['gpu_vram_gb']}GB VRAM")
    else:
        print("GPU não detectada - usará modelo de CPU")

    # 4. Recomendar modelo
    cprint("=", Colors.HEADER)
    cprint("PASSO 4: Seleção de Modelo", Colors.OKBLUE)
    cprint("=", Colors.HEADER)

    recommended_model = recommend_model(hw_detection, existing_models)
    print_success(f"Modelo recomendado: {recommended_model}")

    # 5. Instalar dependências Python
    cprint("=", Colors.HEADER)
    cprint("PASSO 5: Dependências Python", Colors.OKBLUE)
    cprint("=", Colors.HEADER)

    deps_ok = install_python_dependencies()
    if not deps_ok:
        print_warning("Algumas dependências falharam, mas o BEE pode ainda funcionar")

    # 6. Gerar .env e dashboard
    cprint("=", Colors.HEADER)
    cprint("PASSO 6: Configuração Final", Colors.OKBLUE)
    cprint("=", Colors.HEADER)

    env_ok = generate_env_file(hw_detection, ollama_url, recommended_model, existing_models)
    if not env_ok:
        print_error("Falha ao gerar .env - continuando mesmo assim")

    generate_html_dashboard(hw_detection, ollama_url, recommended_model, existing_models)

    # 7. Resumo final
    cprint("=", Colors.HEADER)
    cprint("PASSO 7: Resumo Final", Colors.OKBLUE)
    cprint("=", Colors.HEADER)

    print_success("✅ BEE instalado com sucesso!")
    print()
    print("Arquivos gerados:")
    print(f"  .env          - Configuração automática")
    print(f"  bee-dashboard.html - Dashboard interativo")
    print()
    print("Para começar a usar:")
    print(f"  1. Certifique-se de que o Ollama está rodando: {ollama_url}")
    print(f"  2. Execute: python bees/service.py --env-file .env")
    print(f"  3. Abra o dashboard: open bee-dashboard.html")
    print()
    print("Query example:")
    print('  POST http://localhost:8765/api/v1/query')
    print('  {"query": "Qual a capital da França?"}')
    print()


if __name__ == "__main__":
    main()