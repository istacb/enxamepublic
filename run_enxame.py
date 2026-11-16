#!/usr/bin/env python3
"""
ENXAME Launcher — Inicializador do Enxame com abertura automática do navegador
==============================================================================
Este script pode ser executado com duplo clique (Windows/macOS/Linux) ou via terminal.
Inicia o Enxame Kernel em background e abre o navegador em http://localhost:8765

Uso:
    python3 run_enxame.py              # Inicia e abre navegador
    python3 run_enxame.py --no-browser # Inicia sem abrir navegador
    python3 run_enxame.py --help       # Mostra ajuda
"""

from __future__ import annotations

import argparse
import asyncio
import os
import platform
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Add project root to path
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

# Import after path setup
from enxame_evolved.kernel import main as kernel_main
from bees.config import BeeConfig, load_config

# Hosts de escuta "bind-all" que o navegador não consegue abrir diretamente
WILDCARD_HOSTS = ("", "0.0.0.0", "::", "*")


def browser_url_for(host: str | None, port: int) -> str:
    """Monta a URL navegável da WebUI a partir do host de escuta.

    `0.0.0.0`/`::` (bind-all) viram `localhost`, que o navegador alcança.
    """
    h = (host or "").strip()
    if h in WILDCARD_HOSTS:
        h = "localhost"
    elif ":" in h and not h.startswith("["):
        h = f"[{h}]"  # literal IPv6 precisa de colchetes na URL
    return f"http://{h}:{port}"


def probe_host_for(host: str | None) -> str:
    """Host para sondar localmente o servidor (bind-all -> loopback)."""
    h = (host or "").strip()
    if h in WILDCARD_HOSTS:
        return "127.0.0.1"
    return h.strip("[]")


def is_enxame_running(port: int, host: str = "127.0.0.1", timeout: float = 2.0) -> bool:
    """Detecta um Enxame (abelha standalone ou kernel) via `GET /health`.

    Só usa stdlib para o caminho rápido do atalho não depender de nada.
    """
    import json
    import urllib.request

    try:
        req = urllib.request.Request(f"http://{host}:{port}/health", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return False
            try:
                data = json.loads(resp.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return False
            return isinstance(data, dict) and data.get("status") == "ok"
    except Exception:
        return False


def wait_for_enxame(
    port: int,
    host: str = "127.0.0.1",
    timeout: float = 120.0,
    interval: float = 0.5,
) -> bool:
    """Sonda `/health` até o servidor responder OK ou o timeout estourar."""
    deadline = time.monotonic() + max(1.0, timeout)
    while True:
        if is_enxame_running(port, host=host):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(max(0.1, interval))


class EnxameLauncher:
    """Launcher cross-platform para o Enxame."""
    
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.process: asyncio.subprocess.Process | None = None
        self.shutdown_event = asyncio.Event()
        self.browser_opened = False
        
    def _open_browser_when_ready(
        self, url: str, port: int, probe_host: str, timeout: float = 120.0
    ) -> None:
        """Abre o navegador assim que `/health` responder (poll, não delay fixo).

        Máquinas lentas podem levar >30s para subir; em timeout, abre mesmo
        assim para o usuário poder atualizar a página.
        """
        def _wait_and_open():
            try:
                ready = wait_for_enxame(port, host=probe_host, timeout=timeout)
                if not ready:
                    print(
                        f"⚠️  Servidor não respondeu em {timeout:.0f}s; "
                        "abrindo mesmo assim (atualize a página)."
                    )
                webbrowser.open(url)
                print(f"🌐 Navegador aberto em {url}")
            except Exception as e:
                print(f"⚠️  Não foi possível abrir o navegador automaticamente: {e}")
                print(f"   Acesse manualmente: {url}")

        thread = threading.Thread(target=_wait_and_open, daemon=True)
        thread.start()
    
    def _get_startup_config(self) -> list[str]:
        """Constrói os argumentos de linha de comando para o kernel."""
        cmd = [sys.executable, "-m", "enxame_evolved.kernel"]
        
        if self.args.data_dir:
            cmd.extend(["--data-dir", str(self.args.data_dir)])
        if self.args.host:
            cmd.extend(["--host", self.args.host])
        if self.args.port:
            cmd.extend(["--port", str(self.args.port)])
        if self.args.ollama_url:
            cmd.extend(["--ollama-url", self.args.ollama_url])
        if self.args.model:
            cmd.extend(["--model", self.args.model])
        if self.args.allow_web:
            cmd.append("--allow-web")
        if self.args.log_level:
            cmd.extend(["--log-level", self.args.log_level])
            
        return cmd
    
    async def _run_kernel(self) -> int:
        """Executa o kernel do Enxame."""
        # Configurar handlers de sinal cross-platform
        loop = asyncio.get_event_loop()
        
        def _signal_handler():
            print("\n🛑 Sinal de parada recebido...")
            self.shutdown_event.set()
        
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, _signal_handler)
            except (NotImplementedError, AttributeError):
                pass  # Windows
        
        # Importar e executar o kernel
        try:
            # Usar o main do kernel diretamente
            config = load_config(self.args)
            webui_url = browser_url_for(config.host, config.port)

            # Print startup info
            use_emoji = sys.stdout.encoding and 'utf' in sys.stdout.encoding.lower()
            ok = "✅" if use_emoji else "[OK]"
            print(f"\n{ok} Iniciando Enxame Kernel {config.node_id}...")
            print(f"   WebUI:  {webui_url}")
            print(f"   Health: {webui_url}/health")
            print(f"   Status: {webui_url}/api/v1/status")

            if not self.args.no_browser:
                self._open_browser_when_ready(
                    webui_url, config.port, probe_host_for(config.host)
                )
            
            print("Pressione Ctrl+C para parar\n")
            
            # Importar kernel aqui para evitar problemas de importação circular
            from enxame_evolved.kernel import EnxameKernel
            
            kernel = EnxameKernel(config)
            await kernel.start()
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
            await kernel.stop()
            print("Enxame Kernel parado.")
            return 0
            
        except KeyboardInterrupt:
            print("\n🛑 Interrupção do teclado recebida")
            return 0
        except Exception as e:
            print(f"❌ Erro ao iniciar Enxame: {e}")
            import traceback
            traceback.print_exc()
            return 1
    
    def run(self) -> int:
        """Ponto de entrada principal."""
        # Atalho "Abrir Enxame": se já está rodando, só abre o navegador.
        if self.args.open_only or self.args.ensure_running:
            probe_host = probe_host_for(self.args.host)
            webui_url = browser_url_for(self.args.host, self.args.port)
            if is_enxame_running(self.args.port, host=probe_host):
                print(f"✅ Enxame já está rodando — abrindo {webui_url}")
                try:
                    webbrowser.open(webui_url)
                except Exception as e:
                    print(f"⚠️  Não foi possível abrir o navegador: {e}")
                    print(f"   Acesse manualmente: {webui_url}")
                return 0
            if self.args.open_only:
                print(f"❌ Nenhum Enxame rodando em {webui_url}")
                print("   Inicie com: python run_enxame.py")
                return 1
            # --ensure-running sem servidor: continua abaixo e sobe o kernel

        # Verificar se Ollama está rodando
        self._check_ollama()

        # Executar kernel
        try:
            return asyncio.run(self._run_kernel())
        except KeyboardInterrupt:
            print("\n🛑 Encerrando...")
            return 0
    
    def _check_ollama(self) -> None:
        """Verifica se Ollama está disponível."""
        import urllib.request
        ollama_url = self.args.ollama_url or "http://localhost:11434"
        try:
            req = urllib.request.Request(f"{ollama_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    print("✅ Ollama detectado e respondendo")
                    return
        except Exception:
            pass
        
        print("⚠️  Ollama não detectado em " + ollama_url)
        print("   O Enxame funcionará apenas com embeddings locais (modo offline)")
        print("   Para usar modelos LLM, instale Ollama: https://ollama.com")


def build_parser() -> argparse.ArgumentParser:
    """Parser da CLI do launcher (nível de módulo para ser testável)."""
    parser = argparse.ArgumentParser(
        description="ENXAME Launcher — Inicia o Enxame e abre o navegador",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python3 run_enxame.py                    # Inicia com defaults, abre navegador
  python3 run_enxame.py --no-browser       # Inicia sem abrir navegador
  python3 run_enxame.py --port 8766        # Usa porta customizada
  python3 run_enxame.py --data-dir ~/meu-enxame  # Diretório de dados customizado
  python3 run_enxame.py --ensure-running   # Abre navegador; sobe o kernel se preciso (atalho)
  python3 run_enxame.py --open-only        # Só abre o navegador se já estiver rodando
        """
    )
    
    parser.add_argument("--data-dir", type=Path, help="Diretório de dados do Enxame")
    parser.add_argument("--host", default="0.0.0.0", help="Host de escuta (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Porta HTTP (default: 8765)")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="URL do Ollama")
    parser.add_argument("--model", help="Modelo Ollama a usar")
    parser.add_argument("--allow-web", action="store_true", help="Permitir fallback web")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Nível de log")
    parser.add_argument("--no-browser", action="store_true", help="Não abrir navegador automaticamente")
    parser.add_argument(
        "--ensure-running",
        action="store_true",
        help="Se o Enxame já estiver rodando, só abre o navegador; senão, sobe o kernel (usado pelo atalho pós-instalação)",
    )
    parser.add_argument(
        "--open-only",
        action="store_true",
        help="Só abre o navegador se o Enxame já estiver rodando (não inicia nada)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    launcher = EnxameLauncher(args)
    return launcher.run()


if __name__ == "__main__":
    sys.exit(main())