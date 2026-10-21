#!/usr/bin/env python3
"""
BEE - Instalador Inteligente Cross-Platform
============================================

Instala o BEE (ENXAME Bee) standalone com detecção automática:
- Verifica Python: se já existir, pula instalação
- Verifica Ollama: se já existir e tiver modelos, pula download
- Instala tudo o que for necessário
- Funciona em Windows, macOS, Debian, Arch Linux
- Gera a configuração da abelha (config.json) e um dashboard de diagnóstico
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
import time
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


def _find_repo_root() -> Path:
    """Raiz do repositório (onde vivem bees/, core/, web/).

    Este instalador é a implementação ÚNICA e mora em <repo>/bees/install/,
    então a raiz normalmente é SCRIPT_DIR.parents[1]. Mas ele também roda
    empacotado (AppImage, .app, .deb), onde não existe repositório algum; aí
    sobe a árvore procurando bees/service.py e, não achando, usa o diretório
    de onde foi invocado. Assim os caminhos de .venv/dashboard/config continuam
    resolvendo em vez de apontar para lugares inexistentes — que era o bug
    original deste bloco quando o arquivo vivia na raiz.
    """
    candidatos = []
    if len(SCRIPT_DIR.parents) > 1:
        candidatos.append(SCRIPT_DIR.parents[1])
    candidatos.extend(SCRIPT_DIR.parents)
    candidatos.append(Path.cwd())
    for candidato in candidatos:
        if (candidato / "bees" / "service.py").exists():
            return candidato
    return Path.cwd()


REPO_ROOT = _find_repo_root()


def _dry(acao: str, valor=None):
    """Em --dry-run anuncia a ação que seria executada e devolve um valor seguro.

    O valor de retorno precisa ser o mesmo "formato" do caminho real, senão o
    main() interpreta o dry-run como falha e aborta (sys.exit) — o que tornaria
    o --dry-run inútil justamente para diagnosticar máquinas.
    """
    cprint(f"  [dry-run] pularia: {acao}", Colors.WARNING)
    return valor
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
    # O serviço BEE é aiohttp (bees/service.py) e a identidade usa cryptography
    # (bees/config.py). Nenhum dos dois estava aqui, então mesmo com o
    # instalador "concluindo com sucesso" o serviço não subia: ModuleNotFoundError.
    "aiohttp>=3.9.0",
    "cryptography>=42.0.0",
    "platformdirs>=4.0.0",
    "PyYAML>=6.0.0",
]

# Modelos recomendados por hardware
# Tags precisam existir em ollama.com/library. `phi3:2.7b` NÃO existe: a
# família phi3 publica só 3.8b (mini) e 14b (medium); 2.7B é o phi2, cuja tag
# é `phi:2.7b`. Como GPUtil nunca estava instalado (não estava nas
# dependências), gpu_available era sempre False e o ramo "cpu_only" era o
# escolhido para praticamente todo mundo -> quase todo usuário recebia uma tag
# inexistente e o `ollama pull` falhava, deixando o bee sem modelo.
# (`phi3:3.8b`, `llama3:8b` e `mistral:7b` são válidas; trocadas mesmo assim
# para manter coerência com LIGHT_MODELS de core/ollama/client.py.)
RECOMMENDED_MODELS = {
    "high_gpu": "llama3.1:8b",        # GPU 16GB+ VRAM
    "medium_gpu": "qwen2.5:7b",       # GPU 8GB VRAM
    "low_gpu_ram_heavy": "qwen2.5:3b",  # Muita RAM, pouca GPU
    "cpu_only": "llama3.2:3b",        # Apenas CPU
}


# Template puro (sem f-string): CSS e JS usam {} à vontade, sem precisar de
# {{}}. Os pontos dinâmicos são tokens __ASSIM__ substituídos em runtime.
DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BEE - Assistente Inteligente</title>
    <style>
        :root {
            --bg: #0a0e17;
            --bg-secondary: #111827;
            --card: #1a2230;
            --accent: #00d4aa;
            --accent-dim: #00a080;
            --text: #e8e8e8;
            --muted: #6b7a8c;
            --error: #e74c3c;
            --success: #27ae60;
            --warning: #f39c12;
        }

        * { box-sizing: border-box; }

        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        header {
            background: var(--bg-secondary);
            padding: 1rem 1.5rem;
            border-bottom: 1px solid #333;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }

        .header-content {
            max-width: 1000px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
        }

        .bee-title {
            font-size: 1.3rem;
            font-weight: bold;
            color: var(--accent);
        }

        .status-line { display: flex; align-items: center; gap: 0.5rem; font-size: 0.8rem; color: var(--muted); }

        .status-indicator {
            width: 10px;
            height: 10px;
            background: var(--warning);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }

        main {
            max-width: 1000px;
            margin: 0 auto;
            flex: 1;
            padding: 1.5rem;
            width: 100%;
        }

        .section {
            background: var(--card);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
            border: 1px solid #333;
        }

        .section h2 { margin: 0 0 0.5rem 0; font-size: 1rem; color: var(--accent); }

        .prompt-area {
            background: var(--bg-secondary);
            border: 1px solid #333;
            border-radius: 20px;
            padding: 0.75rem;
            margin: 0.5rem 0;
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }

        .prompt-input {
            flex: 1;
            min-width: 200px;
            background: var(--bg);
            border: none;
            padding: 0.5rem 0.75rem;
            color: var(--text);
            font-size: 0.9rem;
            border-radius: 15px;
            outline: none;
        }

        .prompt-input:focus { box-shadow: 0 0 0 2px var(--accent); }

        .btn-send {
            background: var(--accent);
            border: none;
            padding: 0 1rem;
            color: var(--bg);
            font-weight: bold;
            border-radius: 15px;
            cursor: pointer;
            font-size: 0.85rem;
        }

        .btn-send:hover { background: var(--accent-dim); }
        .btn-send:disabled { opacity: 0.5; cursor: not-allowed; background: var(--muted); }

        .responses-area { flex: 1; min-height: 200px; max-height: 50vh; overflow-y: auto; padding: 0.5rem; }

        .response-item {
            background: var(--bg-secondary);
            border-radius: 6px;
            padding: 0.5rem;
            margin: 0.25rem 0;
            border-left: 3px solid var(--accent);
        }

        .response-item.user { border-left-color: #3498db; }
        .response-item.err { border-left-color: var(--error); }

        .response-meta {
            font-size: 0.65rem;
            color: var(--muted);
            margin-top: 0.25rem;
            display: flex;
            justify-content: space-between;
        }

        .response-text { font-size: 0.85rem; line-height: 1.4; margin-top: 0.25rem; white-space: pre-wrap; }
        .response-text code { background: #2d3748; padding: 0 2px; border-radius: 3px; font-size: 0.7rem; }

        .model-info { background: var(--bg-secondary); border-radius: 6px; padding: 0.75rem; text-align: center; }
        .model-name { color: var(--accent); font-weight: bold; font-size: 1.1rem; }

        .model-status {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--warning);
            margin-right: 0.35rem;
        }

        .kv { font-size: 0.8rem; color: var(--muted); margin: 0.15rem 0; }
        .kv b { color: var(--text); }

        .peer-item { background: var(--bg-secondary); border-radius: 6px; padding: 0.5rem; font-size: 0.75rem; margin: 0.25rem 0; }

        .hint { font-size: 0.72rem; color: var(--muted); margin-top: 0.5rem; line-height: 1.5; }

        @media (max-width: 480px) {
            .header-content { flex-direction: column; align-items: flex-start; }
            .prompt-area { flex-direction: column; }
        }
    </style>
</head>
<body>
    <header>
        <div class="header-content">
            <div class="bee-title">BEE &mdash; ENXAME</div>
            <div class="status-line">
                <span class="status-indicator" id="statusDot" title="status"></span>
                <span id="statusText">verificando&hellip;</span>
            </div>
        </div>
    </header>

    <main>
        <section class="section" id="modelSection">
            <h2>Modelo ativo</h2>
            <div class="model-info">
                <span class="model-status" id="modelStatus" title="estado do modelo"></span>
                <span class="model-name" id="modelName">__MODEL_NAME__</span>
            </div>
            <p class="kv" id="ollamaLine">Ollama: <b>__OLLAMA_URL__</b></p>
            <p class="kv" id="beeLine">BEE: <b>__BEE_URL__</b></p>
        </section>

        <section class="section">
            <h2>Fazer uma pergunta</h2>
            <div class="prompt-area">
                <input type="text" class="prompt-input" id="promptInput"
                    placeholder="Digite sua pergunta aqui..." maxlength="300">
                <button class="btn-send" id="sendBtn">Enviar</button>
            </div>
            <p class="hint">
                A resposta vem de <code>POST __BEE_URL__/api/v1/query</code>.
                Se o BEE estiver offline, nada aqui funciona &mdash; inicie-o com
                <code>python -m bees.service</code> na raiz do reposit&oacute;rio.
            </p>
        </section>

        <section class="section">
            <h2>Respostas</h2>
            <div class="responses-area" id="responsesArea">
                <div class="response-item bee" id="welcomeResponse">
                    <div class="response-text">Olá! Painel gerado pelo instalador BEE em __GENERATED_AT__.</div>
                    <div class="response-meta"><span>BEE</span><span>agora</span></div>
                </div>
            </div>
        </section>

        <section class="section" id="hardwareSection">
            <h2>Hardware detectado na instala&ccedil;&atilde;o</h2>
            <p class="kv">RAM: <b>__RAM_GB__ GB</b></p>
            <p class="kv">GPU: <b>__GPU_DISPLAY__</b></p>
            <p class="kv">Modelos Ollama presentes: <b id="modelsList">&mdash;</b></p>
        </section>

        <section class="section" id="peerSection">
            <h2>Peers na rede</h2>
            <div id="peerList"><p class="kv">nenhum peer consultado ainda</p></div>
        </section>
    </main>

    <script>
        var BEE_URL = "__BEE_URL__";
        var OLLAMA_URL = "__OLLAMA_URL__";
        var INSTALLED_MODELS = __MODELS_JSON__;

        function el(id) { return document.getElementById(id); }

        function now() {
            return new Date().toLocaleTimeString();
        }

        function addItem(text, who, kind) {
            var item = document.createElement('div');
            item.className = 'response-item ' + (kind || who);
            var body = document.createElement('div');
            body.className = 'response-text';
            body.textContent = text;
            var meta = document.createElement('div');
            meta.className = 'response-meta';
            meta.innerHTML = '<span>' + who + '</span><span>' + now() + '</span>';
            item.appendChild(body);
            item.appendChild(meta);
            el('responsesArea').prepend(item);
            return item;
        }

        async function checkStatus() {
            var dot = el('statusDot');
            try {
                var res = await fetch(BEE_URL + '/health');
                if (!res.ok) throw new Error('HTTP ' + res.status);
                var data = await res.json();
                dot.style.background = 'var(--success)';
                el('statusText').textContent = 'BEE online · ' + (data.state || 'ok') +
                    ' · ' + (data.peers || 0) + ' peer(s)';

                var st = await fetch(BEE_URL + '/api/v1/status');
                if (st.ok) {
                    var s = await st.json();
                    var ollamaUp = s.ollama === 'online';
                    el('modelStatus').style.background = ollamaUp ? 'var(--success)' : 'var(--error)';
                    el('modelStatus').title = ollamaUp ? 'Ollama online' : 'Ollama offline';
                }

                var pr = await fetch(BEE_URL + '/api/v1/peers');
                if (pr.ok) {
                    var pd = await pr.json();
                    var peers = pd.peers || [];
                    el('peerList').innerHTML = peers.length
                        ? peers.map(function (p) {
                            return '<div class="peer-item">' + (p.node_id || '?') + ' &middot; ' +
                                (p.host || '') + ':' + (p.port || '') + ' &middot; ' + (p.role || '') + '</div>';
                          }).join('')
                        : '<p class="kv">nenhum peer descoberto</p>';
                }
            } catch (e) {
                dot.style.background = 'var(--error)';
                el('statusText').textContent = 'BEE offline (' + e.message + ')';
                el('modelStatus').style.background = 'var(--error)';
            }
        }

        async function sendPrompt() {
            var input = el('promptInput');
            var query = input.value.trim();
            if (!query) return;

            var btn = el('sendBtn');
            btn.disabled = true;
            input.value = '';
            addItem(query, 'Você', 'user');
            var pending = addItem('processando…', 'BEE', 'bee');

            try {
                var res = await fetch(BEE_URL + '/api/v1/query', {
                    method: 'POST',
                    headers: { 'content-type': 'application/json' },
                    body: JSON.stringify({ query: query })
                });
                var data = await res.json();
                if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
                pending.remove();
                var answer = data.answer || '(sem resposta)';
                if (data.fallback) answer += '  [fallback: nenhuma fonte local relevante]';
                addItem(answer, 'BEE', 'bee');
            } catch (e) {
                pending.remove();
                addItem('Erro: ' + e.message, 'BEE', 'err');
            } finally {
                btn.disabled = false;
                input.focus();
            }
        }

        document.addEventListener('DOMContentLoaded', function () {
            el('modelsList').textContent = INSTALLED_MODELS.length ? INSTALLED_MODELS.join(', ') : 'nenhum';
            el('sendBtn').addEventListener('click', sendPrompt);
            el('promptInput').addEventListener('keypress', function (e) {
                if (e.key === 'Enter') sendPrompt();
            });
            checkStatus();
            setInterval(checkStatus, 5000);
        });
    </script>
</body>
</html>
"""




# Modo "next > next > finish": quando True, nenhuma pergunta é feita e as
# respostas padrão são assumidas. O instalador existe justamente para o usuário
# não se perder, então ele não pode parar no meio esperando digitação.
AUTO = False
DRY_RUN = False  # quando True, detecta e planeja, mas não altera a máquina


def confirm(prompt, default_yes=True):
    """Pergunta s/n, mas nunca trava em modo --auto."""
    if AUTO:
        return default_yes
    suffix = " (Y/n): " if default_yes else " (s/N): "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default_yes
    if not answer:
        return default_yes
    return answer in ("s", "sim", "y", "yes")


def is_root():
    """True se o processo tem privilégios administrativos."""
    if os.name == "nt":
        try:
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return os.geteuid() == 0


def sudo_prefix():
    """Prefixo para comandos de pacote: sudo quando não somos root."""
    if os.name == "nt" or is_root():
        return []
    if shutil.which("sudo"):
        return ["sudo"]
    return []


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
    cprint(f"[PASSO {step_num}/{total}] {text}", Colors.OKBLUE)


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
                    # /api/tags devolve OBJETOS ({"name": ..., "size": ...}),
                    # enquanto o ramo `ollama list` acima appendava STRINGS.
                    # A mistura quebrava "', '.join(models)" (TypeError) e fazia
                    # recommend_model() devolver um dict, que ia parar na configuração gerada.
                    result["models"] = [
                        str(m.get("name", ""))
                        for m in data.get("models", [])
                        if isinstance(m, dict) and m.get("name")
                    ]
                except Exception:
                    pass
    except Exception:
        pass

    return result


def detect_hardware():
    """Detecta hardware da máquina (GPU, RAM) e recomenda um patamar de modelo.

    Correções em relação à versão anterior:

    * Havia um terceiro SyntaxError aqui (o ``try`` interno do fallback de RAM
      não tinha ``except``/``finally`` correspondente). Ele ficava escondido
      porque o parser para no primeiro erro — o da f-string da linha 141.
    * O fallback de RAM era um stub (``pass``): sem psutil a RAM ficava 0 e a
      recomendação caía sempre no patamar mais fraco. Agora lê de fontes nativas
      do SO, sem dependência extra.
    * A GPU era detectada só via ``GPUtil``, que NÃO está em PYTHON_REQUIREMENTS
      e portanto nunca estava instalado — na prática ``gpu_available`` era sempre
      False e todo mundo recebia o modelo "cpu_only". Agora usa ``nvidia-smi``
      (presente junto com o driver NVIDIA) e só então GPUtil/pynvml.
    """
    hw = {
        "ram_gb": 0,
        "gpu_available": False,
        "gpu_vram_gb": 0,
        "model_recommendation": "cpu_only",
    }

    hw["ram_gb"] = _detect_ram_gb()
    hw["gpu_available"], hw["gpu_vram_gb"] = _detect_gpu()

    if hw["gpu_available"]:
        if hw["gpu_vram_gb"] >= 16:
            hw["model_recommendation"] = "high_gpu"
        elif hw["gpu_vram_gb"] >= 8:
            hw["model_recommendation"] = "medium_gpu"
        else:
            hw["model_recommendation"] = "low_gpu_ram_heavy"
    else:
        hw["model_recommendation"] = "cpu_only"

    return hw


def _detect_ram_gb():
    """RAM total em GB, sem depender de psutil estar instalado."""
    # 1) psutil (multiplataforma, se disponível)
    try:
        import psutil

        return round(psutil.virtual_memory().total / (1024 ** 3), 2)
    except Exception:
        pass

    os_type = detect_os()

    # 2) Linux: /proc/meminfo (MemTotal em kB)
    if os_type in ("debian", "arch", "linux_generic"):
        try:
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return round(kb / (1024 ** 2), 2)
        except Exception:
            pass

    # 3) macOS: sysctl hw.memsize (bytes)
    if os_type == "macos":
        try:
            out = subprocess.run(
                ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5
            )
            if out.returncode == 0 and out.stdout.strip().isdigit():
                return round(int(out.stdout.strip()) / (1024 ** 3), 2)
        except Exception:
            pass

    # 4) Windows: CIM via PowerShell (bytes). 'systeminfo' era o caminho antigo,
    #    mas a saída é localizada e o parse estava incompleto (era um `pass`).
    if os_type == "windows":
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"],
                capture_output=True, text=True, timeout=30,
            )
            value = out.stdout.strip()
            if out.returncode == 0 and value.isdigit():
                return round(int(value) / (1024 ** 3), 2)
        except Exception:
            pass

    return 0


def _detect_gpu():
    """Retorna (gpu_available, vram_gb) para a primeira GPU encontrada."""
    # 1) nvidia-smi: vem com o driver NVIDIA, sem instalar nada em Python.
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0:
            first = out.stdout.strip().splitlines()[0].strip() if out.stdout.strip() else ""
            if first.isdigit():
                return True, int(first) // 1024  # MiB -> GiB
    except Exception:
        pass

    # 2) GPUtil, se por acaso estiver instalado (memoryTotal é em MB)
    try:
        import GPUtil

        gpus = GPUtil.getGPUs()
        if gpus:
            return True, gpus[0].memoryTotal // 1024
    except Exception:
        pass

    # 3) pynvml (VRAM em bytes)
    try:
        import pynvml

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        pynvml.nvmlShutdown()
        return True, int(mem.total // (1024 ** 3))
    except Exception:
        pass

    return False, 0


def check_tesseract():
    """Verifica se Tesseract OCR está disponível."""
    try:
        result = subprocess.run(
            ["tesseract", "--version"], capture_output=True, text=True, timeout=3
        )
        return result.returncode == 0
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return False


def install_python_if_needed():
    """Verifica Python e instala se necessário."""
    if DRY_RUN:
        return _dry("instalar/atualizar o Python", True)
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
            # Sem sudo (quando não se é root) o apt-get falha com
            # "Permission denied" e o instalador seguia dizendo "instalado".
            prefix = sudo_prefix()
            subprocess.run([*prefix, "apt-get", "update"], timeout=300)
            proc = subprocess.run(
                [*prefix, "apt-get", "install", "-y", "python3", "python3-venv"],
                timeout=900,
            )
            if proc.returncode != 0:
                print_error("apt-get falhou ao instalar python3/python3-venv")
                return False
            print_success("Python instalado via apt")
            return True

        elif os_type == "arch":
            proc = subprocess.run(
                [*sudo_prefix(), "pacman", "-Sy", "--noconfirm", "python"], timeout=600
            )
            if proc.returncode != 0:
                print_error("pacman falhou ao instalar python")
                return False
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


def _windows_refresh_ollama_path():
    """Adiciona o diretório padrão do Ollama ao PATH desta sessão (Windows).

    Após `winget install Ollama.Ollama`, o PATH do processo atual continua sem o
    executável, então todo `subprocess.run(["ollama", ...])` seguinte falhava com
    FileNotFoundError mesmo com o Ollama instalado corretamente.
    """
    if os.name != "nt":
        return
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    candidates = [
        Path(local) / "Programs" / "Ollama",
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Ollama",
    ]
    for c in candidates:
        if (c / "ollama.exe").exists() and str(c) not in os.environ.get("PATH", ""):
            os.environ["PATH"] = str(c) + os.pathsep + os.environ.get("PATH", "")
            return


def start_ollama_daemon():
    """Inicia o servidor Ollama em background sem bloquear o instalador.

    Antes havia quatro chamadas síncronas de `ollama serve` com
    `subprocess.run(..., capture_output=True)`. Esse comando NUNCA termina,
    então o instalador congelava ali para sempre (sem timeout) - o classico
    "instalacao travada" que parece sucesso parcial e nao entrega nada.
    """
    if DRY_RUN:
        return _dry("iniciar o daemon do Ollama", True)
    if is_ollama_running():
        return True
    try:
        if os.name == "nt":
            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            subprocess.Popen(
                ["ollama", "serve"],
                creationflags=0x00000008 | 0x00000200,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
    except FileNotFoundError:
        print_error("Comando 'ollama' nao encontrado no PATH")
        return False
    except Exception as e:
        print_error(f"Nao foi possivel iniciar o Ollama: {e}")
        return False

    for _ in range(20):
        time.sleep(0.5)
        if is_ollama_running():
            return True
    print_warning("Ollama nao respondeu em 10s; verifique manualmente")
    return False


def is_ollama_running(url="http://localhost:11434"):
    """True se a API HTTP do Ollama responde."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def install_ollama_if_needed():
    """Verifica Ollama e instala se necessário. Retorna URL base."""
    if DRY_RUN:
        det = detect_ollama()
        return _dry(f"instalar/iniciar o Ollama (usaria {det['url']})",
                    (det["url"], det["models"]))
    cprint("Verificando Ollama...", Colors.OKCYAN)

    detection = detect_ollama()

    if detection["running"]:
        print_success(f"Ollama já rodando em {detection['url']} com {len(detection['models'])} modelo(s)")
        print(f"   Modelos: {', '.join(detection['models'])}")
        return detection["url"], detection["models"]

    if detection["installed"] and not detection["running"]:
        print_warning("Ollama instalado mas não está rodando")
        if confirm("Deseja iniciar o Ollama agora?", default_yes=True):
            start_ollama_daemon()
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
                winget = shutil.which("winget")
                if winget:
                    cprint("Instalando Ollama via winget...", Colors.OKCYAN)
                    proc = subprocess.run(
                        [winget, "install", "--id", "Ollama.Ollama", "-e",
                         "--accept-source-agreements", "--accept-package-agreements"],
                        timeout=1800,
                    )
                    if proc.returncode != 0:
                        print_error("winget falhou ao instalar o Ollama")
                        return None, []
                    # O instalador do Windows registra o app mas o PATH desta
                    # sessão não foi atualizado; tenta o caminho padrão.
                    _windows_refresh_ollama_path()
                    start_ollama_daemon()
                    return "http://localhost:11434", []

                cprint(
                    "winget não encontrado. Baixe o instalador em "
                    "https://ollama.com/download, execute-o e rode este "
                    "script novamente.",
                    Colors.WARNING,
                )
                return None, []

            elif os_type == "macos":
                # Homebrew
                result = subprocess.run(
                    ["which", "brew"], capture_output=True, text=True
                )
                if result.returncode == 0:
                    cprint("Instalando Ollama via Homebrew...", Colors.OKCYAN)
                    proc = subprocess.run(["brew", "install", "ollama"], timeout=1800)
                    if proc.returncode != 0:
                        print_error("Homebrew falhou ao instalar o Ollama")
                        return None, []
                    start_ollama_daemon()
                    return "http://localhost:11434", []
                else:
                    cprint("Homebrew não encontrado", Colors.WARNING)
                    return None, []

            elif os_type == "debian":
                cprint("Instalando Ollama via curl...", Colors.OKCYAN)
                # Add repo and install
                # Dois problemas resolvidos aqui:
                #  a) com lista de argumentos, "|" e "sh" viravam URLs extras do
                #     curl (não um pipe do shell) e nada era instalado;
                #  b) mesmo usando shell, `curl ... | sh` devolve o status do
                #     ÚLTIMO comando (sh), que sai 0 com stdin vazio — então uma
                #     falha de download/rede passava como sucesso.
                # Por isso: baixa para um arquivo temporário, verifica, executa.
                script_fd, script_path = tempfile.mkstemp(suffix=".sh", prefix="ollama-install-")
                os.close(script_fd)
                try:
                    dl = subprocess.run(
                        ["curl", "-fsSL", "-o", script_path,
                         "https://ollama.com/install.sh"],
                        timeout=300,
                    )
                    if dl.returncode != 0 or Path(script_path).stat().st_size == 0:
                        print_error(
                            "Não foi possível baixar https://ollama.com/install.sh "
                            f"(curl retornou {dl.returncode}). Verifique sua conexão "
                            "ou instale o Ollama manualmente."
                        )
                        return None, []
                    proc = subprocess.run(["sh", script_path], timeout=1800)
                    if proc.returncode != 0:
                        print_error("O instalador oficial do Ollama falhou (veja a saída acima)")
                        return None, []
                finally:
                    Path(script_path).unlink(missing_ok=True)
                start_ollama_daemon()
                import time
                time.sleep(3)
                url = "http://localhost:11434"
                return url, []

            elif os_type == "arch":
                proc = subprocess.run(
                    [*sudo_prefix(), "pacman", "-Sy", "--noconfirm", "ollama"], timeout=900
                )
                if proc.returncode != 0:
                    print_error("pacman falhou ao instalar o Ollama")
                    return None, []
                start_ollama_daemon()
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


def venv_python(venv_path):
    """Caminho do interpretador dentro do venv (Windows e POSIX)."""
    if os.name == "nt":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def install_python_dependencies():
    """Instala as dependências Python em um venv e RETORNA o python do venv.

    Retorna Path do interpretador do venv em caso de sucesso, ou None em falha.

    A versão anterior tinha quatro defeitos que, somados, produziam exatamente o
    sintoma "instalou mas nada funciona":

    1. ``pip_cmd = f"{sys.executable} -m pip"`` era uma STRING ÚNICA usada como
       ``argv[0]`` em ``subprocess.run([pip_cmd, "install", ...])``. O SO tentava
       executar um programa literalmente chamado "python -m pip" ->
       FileNotFoundError em 100% dos pacotes.
    2. ``returncode`` nunca era verificado: cada pacote imprimia "✓ instalado"
       mesmo quando o pip falhava.
    3. Em Debian 12+/Ubuntu 24.04+/Arch o pip fora de venv é bloqueado pela
       PEP 668 ("externally-managed-environment"). Como a criação do venv tinha
       ``timeout=30`` (curto demais; no Windows passa fácil disso) e a falha era
       apenas um aviso, o instalador caía no pip do sistema e falhava em tudo —
       reportando sucesso.
    4. A lista de pacotes não incluía aiohttp/cryptography, sem os quais
       ``python -m bees.service`` nem sequer importa.
    """
    if DRY_RUN:
        return _dry("criar .venv-bee e instalar as dependências",
                    venv_python(REPO_ROOT / ".venv-bee"))
    cprint("Instalando dependências Python...", Colors.OKCYAN)

    venv_path = REPO_ROOT / ".venv-bee"
    py = venv_python(venv_path)

    if not py.exists():
        cprint("Criando ambiente virtual...", Colors.OKCYAN)
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "venv", str(venv_path)],
                capture_output=True, text=True, timeout=600,
            )
        except subprocess.TimeoutExpired:
            print_error("Tempo esgotado criando o ambiente virtual")
            return None
        except Exception as e:
            print_error(f"Não foi possível criar o venv: {e}")
            return None

        if proc.returncode != 0 or not py.exists():
            print_error("Falha ao criar o ambiente virtual:")
            print((proc.stderr or proc.stdout or "").strip()[:800])
            os_type = detect_os()
            if os_type == "debian":
                print_error("Provavelmente falta o pacote 'python3-venv': sudo apt install python3-venv")
            elif os_type == "arch":
                print_error("Verifique se 'python' e o módulo venv estão instalados")
            return None
        print_success(f"Ambiente virtual criado em {venv_path}")
    else:
        print_success(f"Ambiente virtual já existe em {venv_path}")

    cprint(
        f"Instalando {len(PYTHON_REQUIREMENTS)} pacotes (pode levar alguns minutos)...",
        Colors.OKCYAN,
    )
    try:
        proc = subprocess.run(
            [str(py), "-m", "pip", "install", "--upgrade", "--disable-pip-version-check",
             *PYTHON_REQUIREMENTS],
            capture_output=True, text=True, timeout=3600,
        )
    except subprocess.TimeoutExpired:
        print_error("Tempo esgotado instalando dependências")
        return None
    except Exception as e:
        print_error(f"Falha ao executar o pip: {e}")
        return None

    if proc.returncode != 0:
        print_error("O pip falhou. Últimas linhas da saída:")
        print((proc.stderr or proc.stdout or "").strip()[-2000:])
        return None

    print_success("Dependências instaladas")
    return py


def generate_html_dashboard(hw_detection, ollama_url, model_name, installed_models, bee_port=8765):
    """Gera dashboard HTML interativo.

    Notas sobre a reescrita (a versão anterior não produzia arquivo nenhum):

    * ``open(html, "w")`` abria o CONTEÚDO do HTML como se fosse o NOME do
      arquivo — OSError e nenhum dashboard gerado. Agora grava em ``report_path``.
    * O HTML era montado com f-string, então todo ``{``/``}`` de CSS e JS
      precisava de ``{{``/``}}``. Duas places escaparam: o ``${query}`` do
      template literal JS virava expressão Python (NameError: 'query') e o
      atributo ``style`` saía com aspas quebradas, corrompendo o resto do HTML.
      Agora é template puro + substituição de tokens: nenhum brace precisa
      escapar e é impossível reintroduzir esse tipo de bug.
    * O JS consultava ``{ollama_url}/health`` e ``{ollama_url}/api/v1/peers``.
      Ollama não tem essas rotas (só ``/api/tags``, ``/api/version``), então o
      status dava sempre "Sem conexão". Agora aponta para o serviço BEE, que é
      quem de fato expõe ``/health``, ``/api/v1/status`` e ``/api/v1/query``.
    * ``sendPrompt()`` só fingia responder com um ``setTimeout`` ("BEE:
      Processando..."). Agora faz POST real em ``/api/v1/query``.
    """
    if DRY_RUN:
        return _dry("gravar bee-dashboard.html", True)
    has_gpu = hw_detection.get("gpu_available", False)
    gpu_display = "{} GB VRAM".format(hw_detection.get("gpu_vram_gb", 0)) if has_gpu else "Não detectada"
    models_json = json.dumps([str(m) for m in (installed_models or [])])

    replacements = {
        "__MODEL_NAME__": str(model_name),
        "__RAM_GB__": str(hw_detection.get("ram_gb", 0)),
        "__GPU_DISPLAY__": gpu_display,
        "__OLLAMA_URL__": str(ollama_url or "http://localhost:11434"),
        "__BEE_URL__": "http://127.0.0.1:{}".format(bee_port),
        "__MODELS_JSON__": models_json,
        "__GENERATED_AT__": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    html = DASHBOARD_TEMPLATE
    for token, value in replacements.items():
        html = html.replace(token, value)

    report_path = REPO_ROOT / "bee-dashboard.html"
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html)
        print_success("Dashboard HTML gerado em {}".format(report_path))
        return True
    except Exception as e:
        print_error("Erro ao gerar dashboard: {}".format(e))
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

    if AUTO:
        choice = "1"
    else:
        try:
            choice = input("\nEscolha (1-3, padrão: 1): ").strip() or "1"
        except (EOFError, KeyboardInterrupt):
            choice = "1"

    os_type = detect_os()
    bee_dir = REPO_ROOT  # Diretório onde o Bee foi instalado
    env_path = bee_dir / ".env"

    # Remover .env deixado por versões antigas do instalador.
    # O instalador atual não gera mais .env: a configuração da abelha vive em
    # <data-dir>/config.json. Isto fica aqui só para limpar instalações antigas.
    if choice in ("1", "3") and env_path.exists():
        env_path.unlink()
        print_success("Arquivo .env de versão anterior removido")

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
            if confirm("\nDeseja desinstalar o Ollama do Windows?", default_yes=False):
                # Parar serviço primeiro
                subprocess.run(["taskkill", "/F", "/IM", "ollama.exe"], capture_output=True)
                # O instalador oficial do Windows coloca o programa em
                # %LOCALAPPDATA%\Programs\Ollama e os modelos em
                # %USERPROFILE%\.ollama — não em C:/ProgramData/Ollama, que era
                # o único caminho removido antes (ou seja, nada era removido).
                _windows_refresh_ollama_path()
                subprocess.run(
                    [shutil.which("ollama") or "ollama", "stop"], capture_output=True
                )
                local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
                for target in [
                    Path(local) / "Programs" / "Ollama",
                    Path("C:/ProgramData/Ollama"),
                    Path.home() / ".ollama",
                ]:
                    if target.exists():
                        shutil.rmtree(target, ignore_errors=True)
                        print_success(f"Removido: {target}")
                # Remover atalho do menu iniciar
                print_success("Ollama desinstalado (Windows)")

        elif os_type == "macos":
            if confirm("\nDeseja desinstalar o Ollama do macOS?", default_yes=False):
                subprocess.run(
                    ["brew", "uninstall", "ollama"], capture_output=True
                )
                print_success("Ollama desinstalado (macOS)")

        elif os_type == "debian":
            if confirm("\nDeseja desinstalar o Ollama? (apt remove ollama)", default_yes=False):
                prefix = sudo_prefix()
                subprocess.run([*prefix, "apt", "remove", "-y", "ollama"])
                subprocess.run([*prefix, "apt", "autoremove", "-y", "ollama"])
                print_success("Ollama desinstalado (Debian)")

        elif os_type == "arch":
            if confirm("\nDeseja desinstalar o Ollama? (pacman -Rns ollama)", default_yes=False):
                subprocess.run(
                    [*sudo_prefix(), "pacman", "-Rns", "--noconfirm", "ollama"]
                )
                print_success("Ollama desinstalado (Arch)")

    cprint("\n=== Desinstalação Concluída ===", Colors.HEADER)
    cprint("Só restaram os arquivos originais do enxamepublic.", Colors.OKCYAN)


def pull_model(model_name, existing_models):
    """Baixa o modelo recomendado se ele ainda não estiver presente.

    O instalador antigo escolhia um modelo e NUNCA o baixava: não havia nenhum
    `ollama pull` em lugar nenhum. Resultado: bee sem modelo => toda query
    devolve "não encontrei informação" e o usuário conclui que nada funciona.
    """
    if DRY_RUN:
        return _dry(f"baixar o modelo (ollama pull)", True)
    if not model_name:
        return False

    if model_name in (existing_models or []):
        print_success(f"Modelo '{model_name}' já está presente - pulando download")
        return True

    cprint(f"Baixando modelo '{model_name}' (pode levar vários minutos)...", Colors.OKCYAN)
    try:
        proc = subprocess.run(
            ["ollama", "pull", model_name],
            timeout=7200,
        )
    except FileNotFoundError:
        print_error("Comando 'ollama' não encontrado no PATH")
        return False
    except subprocess.TimeoutExpired:
        print_error("Tempo esgotado baixando o modelo")
        return False

    if proc.returncode != 0:
        print_error(
            f"Não foi possível baixar '{model_name}'. "
            "Verifique se a tag existe em https://ollama.com/library"
        )
        return False

    print_success(f"Modelo '{model_name}' baixado")
    return True


def parse_args():
    """Linha de comando do instalador.

    Antes `argparse` era importado mas nunca usado: nenhum flag existia e
    `uninstall_bee()` era código morto (nunca chamado), apesar do docstring do
    módulo anunciar "Possui desinstalador para cada SO".
    """
    parser = argparse.ArgumentParser(
        description="Instalador inteligente do BEE/ENXAME (Windows, macOS, Debian, Arch)",
    )
    parser.add_argument(
        "--auto", action="store_true",
        help="Modo next>next>finish: não faz nenhuma pergunta e assume os padrões",
    )
    parser.add_argument(
        "--uninstall", action="store_true",
        help="Remove dashboard, venv e arquivos deixados por versões anteriores",
    )
    parser.add_argument(
        "--bee-port", type=int, default=8765,
        help="Porta do bee standalone (aiohttp) referenciada no dashboard (default: 8765)",
    )
    parser.add_argument(
        "--ollama-url", default=None,
        help="URL do Ollama (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--skip-model", action="store_true",
        help="Não baixa modelo nenhum (útil se você já gerencia os modelos)",
    )
    parser.add_argument(
        "--model", default=None,
        help="Força um modelo específico em vez do recomendado pelo hardware",
    )
    # --- flags da abelha (o caminho único e documentado) ---
    parser.add_argument(
        "--data-dir", default=None,
        help="Diretório de dados da abelha (default: ~/enxame/data). "
             "Uma abelha por diretório: é nele que ficam identity.json, config.json, "
             "documentos/ e o índice RAG.",
    )
    parser.add_argument(
        "--node-id", default=None,
        help="Nome desta abelha (default: gerado a partir do hostname)",
    )
    parser.add_argument(
        "--cluster", dest="cluster", action="store_true", default=None,
        help="Participa do enxame sem perguntar (grava cluster.enabled=true)",
    )
    parser.add_argument(
        "--no-cluster", dest="cluster", action="store_false",
        help="Abelha isolada sem perguntar (grava cluster.enabled=false)",
    )
    parser.add_argument(
        "--no-shortcuts", action="store_true",
        help="Não cria atalhos nem serviço de inicialização automática",
    )
    parser.add_argument(
        "--install-service", action="store_true",
        help="Instala a abelha como serviço (systemd --user no Linux, LaunchAgent no macOS, "
             "tarefa de logon no Windows)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Detecta tudo e mostra o plano, sem instalar nem gravar nada",
    )
    return parser.parse_args()


def main():
    """Função principal do instalador."""
    global AUTO, DRY_RUN
    args = parse_args()
    AUTO = bool(args.auto)
    DRY_RUN = bool(args.dry_run)
    if AUTO:
        cprint("Modo automático: nenhuma pergunta será feita.", Colors.OKCYAN)
    if DRY_RUN:
        cprint("DRY-RUN: vou detectar tudo e mostrar o plano sem alterar a máquina.",
               Colors.WARNING)

    if args.uninstall:
        uninstall_bee()
        return

    print_header()

    total_steps = 7

    # 1. Verificar Python
    cprint("PASSO 1: Verificação do Python", Colors.OKBLUE)
    ok, version = python_version_ok()
    if ok:
        print_success(f"Python {version[0]}.{version[1]} encontrado - pulando instalação")
    else:
        print_step(1, total_steps, "Python adequado não encontrado - tentando instalar")
        # check_python() NÃO EXISTIA neste módulo: qualquer máquina com Python
        # antigo caía em NameError. O nome certo é install_python_if_needed().
        if not install_python_if_needed():
            print_error("Python é obrigatório para o BEE. Encerrando.")
            sys.exit(1)

    # 2. Verificar Ollama
    cprint("PASSO 2: Verificação do Ollama", Colors.OKBLUE)
    # detect_ollama() devolve UM DICT. O código antigo fazia
    # `ollama_url, existing_models = detect_ollama()`, que estoura
    # ValueError ("too many values to unpack") e matava o instalador no passo 2.
    detection = detect_ollama()
    if args.ollama_url:
        detection["url"] = args.ollama_url
        detection["running"] = is_ollama_running(args.ollama_url)

    # O que importa para o ENXAME é a API HTTP (o bee e o juiz falam HTTP, não o
    # binário). Exigir `installed` fazia o instalador tentar reinstalar o Ollama
    # mesmo com o servidor respondendo na porta 11434.
    if detection["running"]:
        ollama_url = detection["url"]
        existing_models = detection["models"]
        print_success(f"Ollama detectado em {ollama_url}")
        if existing_models:
            print_warning(f"{len(existing_models)} modelo(s) já presente(s)")
            for m in existing_models:
                print(f"    - {m}")
        else:
            print_warning("Ollama está rodando, mas nenhum modelo está instalado")
    else:
        print_step(2, total_steps, "Ollama ausente/parado - instalando ou iniciando")
        ollama_url, existing_models = install_ollama_if_needed()
        if not ollama_url:
            print_error("Não foi possível instalar/verificar o Ollama. Encerrando.")
            sys.exit(1)

    # 3. Detectar hardware
    cprint("PASSO 3: Detecção de Hardware", Colors.OKBLUE)
    hw_detection = detect_hardware()
    print_success(f"RAM: {hw_detection['ram_gb']} GB")
    if hw_detection["gpu_available"]:
        print_success(f"GPU detectada: {hw_detection['gpu_vram_gb']} GB VRAM")
    else:
        print_warning("GPU não detectada - será usado o patamar de CPU")

    # 4. Recomendar (e baixar) modelo
    cprint("PASSO 4: Seleção de Modelo", Colors.OKBLUE)
    if args.model:
        recommended_model = args.model
    else:
        recommended_model = recommend_model(hw_detection, existing_models)
    print_success(f"Modelo escolhido: {recommended_model}")

    if args.skip_model:
        print_warning("--skip-model informado: nenhum modelo será baixado")
    else:
        if pull_model(recommended_model, existing_models):
            existing_models = list(dict.fromkeys([*(existing_models or []), recommended_model]))

    # 5. Instalar dependências Python
    cprint("PASSO 5: Dependências Python", Colors.OKBLUE)
    venv_py = install_python_dependencies()
    if venv_py is None:
        print_error(
            "Não foi possível instalar as dependências. Sem elas o serviço não "
            "sobe (ModuleNotFoundError) - veja a saída do pip acima."
        )
        sys.exit(1)

    # 6. Configurar a abelha (config.json, cluster, atalhos, serviço)
    cprint("PASSO 6: Configuração da Abelha", Colors.OKBLUE)
    try:
        from . import bee_setup, cluster_setup
    except ImportError:
        try:
            from bees.install import bee_setup, cluster_setup  # type: ignore[no-redef]
        except ImportError:
            # Rodando como script solto / empacotado, sem o pacote no sys.path.
            if str(SCRIPT_DIR) not in sys.path:
                sys.path.insert(0, str(SCRIPT_DIR))
            import bee_setup  # type: ignore[no-redef]
            import cluster_setup  # type: ignore[no-redef]

    data_dir = cluster_setup.resolve_data_dir(args.data_dir)
    print(f"  data-dir: {data_dir}")

    resumo = bee_setup.configure_bee(
        data_dir=data_dir,
        port=args.bee_port,
        ollama_url=ollama_url,
        model=recommended_model,
        node_id=args.node_id,
        cluster=args.cluster,
        auto=AUTO,
        venv_py=venv_py,
        repo_root=REPO_ROOT,
        dry_run=DRY_RUN,
        log_info=lambda m: cprint(m, Colors.OKCYAN),
        log_warn=lambda m: cprint(m, Colors.WARNING),
    )

    atalhos = []
    if not args.no_shortcuts:
        atalhos = bee_setup.create_bee_shortcuts(
            venv_py=venv_py, data_dir=data_dir, port=args.bee_port,
            ollama_url=ollama_url, model=recommended_model, repo_root=REPO_ROOT,
            dry_run=DRY_RUN,
            log_info=lambda m: cprint(m, Colors.OKCYAN),
            log_warn=lambda m: cprint(m, Colors.WARNING),
        )

    servico = None
    if args.install_service:
        servico = bee_setup.install_bee_service(
            venv_py=venv_py, data_dir=data_dir, port=args.bee_port,
            ollama_url=ollama_url, model=recommended_model, repo_root=REPO_ROOT,
            dry_run=DRY_RUN,
            log_info=lambda m: cprint(m, Colors.OKCYAN),
            log_warn=lambda m: cprint(m, Colors.WARNING),
        )

    generate_html_dashboard(
        hw_detection, ollama_url, recommended_model, existing_models,
        bee_port=args.bee_port,
    )

    # 7. Resumo final
    cprint("PASSO 7: Resumo Final", Colors.OKBLUE)
    if DRY_RUN:
        print_warning("DRY-RUN: nada foi instalado nem gravado.")
    else:
        print_success("Abelha instalada e configurada!")
    print()
    print("O que ficou pronto:")
    print(f"  nome da abelha : {resumo['node_id']}")
    print(f"  data-dir       : {resumo['data_dir']}")
    print(f"  porta          : {resumo['port']}")
    print(f"  modelo         : {resumo['model']}")
    print(f"  ollama         : {resumo['ollama_url']}")
    if resumo["cluster"] is True:
        print("  enxame         : participa (cluster.enabled=true)")
    elif resumo["cluster"] is False:
        print("  enxame         : NÃO participa (cluster.enabled=false)")
    else:
        print("  enxame         : padrão - forma enxame se achar 3+ abelhas na rede")
    print(f"  busca na web   : {'permitida' if resumo['allow_web'] else 'bloqueada'}")
    print(f"  venv           : {venv_py}")
    for atalho in atalhos:
        print(f"  atalho         : {atalho}")
    if servico and servico.get("criado"):
        estado = "ativo" if servico.get("ativo") else "criado, mas não ativado"
        print(f"  serviço        : {servico['criado']} ({estado})")
    print()
    print("COMO USAR (é só isto - um comando e o navegador):")
    print(f"  cd {REPO_ROOT}")
    print(f"  {venv_py} -m bees.service \\")
    print(f"      --host 0.0.0.0 --port {resumo['port']} --data-dir {resumo['data_dir']}")
    print()
    print(f"  depois abra  http://localhost:{resumo['port']}/")
    print()
    print("Por que abrir a raiz:")
    print("  A abelha serve a interface de web/ em '/' e a MESMA API do enxame")
    print("  (/api/session, /api/chat, /api/status, /api/cluster/discover,")
    print("  /api/guardian). Ou seja: sozinha ela já faz tudo - responde, guarda")
    print("  o próprio RAG, aplica a Guarda e mostra o painel. Não existe")
    print("  segundo produto a instalar.")
    print()
    print("Para parar: Ctrl+C no terminal", end="")
    if servico and servico.get("ativo") and servico.get("comando_parar"):
        print(f", ou `{servico['comando_parar']}`")
    else:
        print()
    print()
    print("Formar um enxame (opcional):")
    print("  Rode este mesmo instalador em 3+ máquinas na mesma rede local.")
    print("  Elas se descobrem por mDNS e elegem os papéis entre si: Juiz,")
    print("  Bibliotecária, Guarda e Workers. O Juiz recebe a pergunta,")
    print("  descobre qual abelha tem o conhecimento offline, delega, e faz a")
    print("  curadoria da resposta antes de devolver. Cada abelha mantém o")
    print("  próprio RAG.")
    print("  Obs.: mDNS é link-local - as máquinas precisam estar no mesmo")
    print("  segmento de rede (VPN/sub-rede diferente não descobre).")
    print()
    print("Se algo falhar, o diagnóstico mínimo é:")
    print(f"  1) {venv_py} -c \"import bees, core; print('pacotes ok')\"  (a partir de {REPO_ROOT})")
    print(f"  2) curl {ollama_url}/api/tags   (o Ollama precisa responder)")
    print(f"  3) abrir {REPO_ROOT / 'bee-dashboard.html'} no navegador: mostra o estado")
    print("     desta máquina mesmo com a abelha parada.")
    print()
    print("Uma abelha por máquina: para rodar outra nesta mesma máquina, repita a")
    print("instalação com --data-dir e --bee-port diferentes. Cada data-dir tem")
    print("identity.json, config.json, documentos/ e o próprio índice RAG.")

if __name__ == "__main__":
    main()
