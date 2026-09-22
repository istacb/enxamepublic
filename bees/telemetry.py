#!/usr/bin/env python3
"""
Telemetry & Update Check — Opt-in Anonymous Stats
===================================================
Funcionalidades:
1. Verificação semanal de atualizações (GitHub releases)
2. Coleta de stats anônimos (se opt-in)
3. Zero PII - sem IPs, sem conteúdo, sem IDs identificáveis
"""

from __future__ import annotations

import json
import os
import platform
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import httpx
except ImportError:
    httpx = None


TELEMETRY_VERSION = "1.0.0"
GITHUB_REPO = "enxamepublic/enxame"
CHECK_INTERVAL_SECONDS = 7 * 24 * 60 * 60  # 7 dias


@dataclass
class TelemetryConfig:
    """Configuração de telemetria."""
    enabled: bool = False
    installation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    last_check: float = 0
    last_update_check: float = 0
    update_available: bool = False
    latest_version: str = ""
    check_interval: int = CHECK_INTERVAL_SECONDS


def get_telemetry_path(data_dir: Path) -> Path:
    """Retorna caminho do arquivo de telemetria."""
    return data_dir / "telemetry.json"


def load_telemetry(data_dir: Path) -> TelemetryConfig:
    """Carrega configuração de telemetria."""
    path = get_telemetry_path(data_dir)
    if path.exists():
        try:
            with open(path, "r") as f:
                data = json.load(f)
            return TelemetryConfig(**data)
        except Exception:
            pass
    return TelemetryConfig()


def save_telemetry(data_dir: Path, config: TelemetryConfig) -> None:
    """Salva configuração de telemetria."""
    path = get_telemetry_path(data_dir)
    try:
        with open(path, "w") as f:
            json.dump({
                "enabled": config.enabled,
                "installation_id": config.installation_id,
                "last_check": config.last_check,
                "last_update_check": config.last_update_check,
                "update_available": config.update_available,
                "latest_version": config.latest_version,
                "check_interval": config.check_interval,
            }, f, indent=2)
    except Exception:
        pass


def collect_anonymous_stats(data_dir: Path, config: Any) -> dict[str, Any]:
    """Coleta stats anônimos do sistema (sem PII)."""
    import psutil
    
    stats = {
        "os": platform.system(),
        "os_version": platform.version(),
        "arch": platform.machine(),
        "python_version": platform.python_version(),
        "ram_gb": round(psutil.virtual_memory().total / (1024**3), 1),
        "cpu_cores": psutil.cpu_count(logical=False),
        "cpu_logical": psutil.cpu_count(logical=True),
        "disk_gb": round(psutil.disk_usage("/").free / (1024**3), 1),
        "has_gpu": False,
        "model": getattr(config, "model", "unknown"),
        "offline_mode": getattr(config, "offline_mode", False),
        "allow_web": getattr(config, "allow_web", False),
        "cluster_enabled": getattr(config, "cluster", {}).get("enabled", False),
        "uptime_hours": 0,  # Será preenchido pelo serviço
        "queries_total": 0,  # Será preenchido pelo serviço
        "peers_connected": 0,  # Será preenchido pelo serviço
        "timestamp": time.time(),
    }
    
    # Detectar GPU
    try:
        if platform.system() == "Linux":
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                stats["has_gpu"] = True
                stats["gpu_name"] = result.stdout.strip().split("\n")[0]
        elif platform.system() == "Darwin":
            stats["has_gpu"] = "Apple" in platform.processor() or "arm" in platform.machine().lower()
        elif platform.system() == "Windows":
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                stats["has_gpu"] = True
                stats["gpu_name"] = result.stdout.strip().split("\n")[0]
    except Exception:
        pass
    
    return stats


async def send_telemetry(data_dir: Path, stats: dict[str, Any]) -> bool:
    """Envia telemetria anônima para endpoint (se habilitado)."""
    if not httpx:
        return False
    
    telemetry = load_telemetry(data_dir)
    if not telemetry.enabled:
        return False
    
    try:
        payload = {
            "installation_id": telemetry.installation_id,
            "version": TELEMETRY_VERSION,
            "stats": stats,
        }
        
        # Endpoint fictício - substituir por real se necessário
        # async with httpx.AsyncClient(timeout=10.0) as client:
        #     await client.post("https://telemetry.enxame.dev/v1/stats", json=payload)
        
        # Por enquanto, apenas log local
        log_path = data_dir / "logs" / "telemetry.log"
        log_path.parent.mkdir(exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(payload) + "\n")
        
        return True
    except Exception:
        return False


async def check_for_updates(data_dir: Path, current_version: str) -> dict[str, Any]:
    """Verifica se há nova versão disponível no GitHub."""
    if not httpx:
        return {"available": False, "error": "httpx not installed"}
    
    telemetry = load_telemetry(data_dir)
    now = time.time()
    
    # Verificar se já checou recentemente
    if now - telemetry.last_update_check < telemetry.check_interval:
        return {
            "available": telemetry.update_available,
            "version": telemetry.latest_version,
            "cached": True,
        }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github.v3+json"}
            )
            
            if resp.status_code == 200:
                release = resp.json()
                latest_tag = release.get("tag_name", "").lstrip("v")
                current = current_version.lstrip("v")
                
                # Comparação simples de versão
                def version_tuple(v):
                    return tuple(map(int, (v.split(".") + ["0", "0", "0"])[:3]))
                
                is_newer = version_tuple(latest_tag) > version_tuple(current)
                
                telemetry.last_update_check = now
                telemetry.update_available = is_newer
                telemetry.latest_version = latest_tag
                save_telemetry(data_dir, telemetry)
                
                return {
                    "available": is_newer,
                    "version": latest_tag,
                    "current": current,
                    "release_url": release.get("html_url", ""),
                    "notes": release.get("body", "")[:500],
                    "cached": False,
                }
            
    except Exception as e:
        return {"available": False, "error": str(e)}
    
    return {"available": False, "error": "Unknown"}


def prompt_telemetry_optin(data_dir: Path, auto: bool = False) -> bool:
    """Pergunta ao usuário se deseja habilitar telemetria anônima."""
    telemetry = load_telemetry(data_dir)
    
    if telemetry.enabled:
        return True
    
    if auto:
        return False
    
    print(f"\n{'='*60}")
    print(f"  📊 TELEMETRIA ANÔNIMA (OPCIONAL)")
    print(f"{'='*60}")
    print(f"\nO Enxame pode coletar estatísticas anônimas para melhorar o projeto:")
    print(f"  • OS, arquitetura, RAM, CPU, GPU (sem identificadores)")
    print(f"  • Modelo usado, modo offline, cluster ativo")
    print(f"  • Contadores: queries, peers, uptime")
    print(f"\n  NÃO coletamos: IPs, conteúdo de queries, arquivos, IDs pessoais")
    print(f"\n  Dados são enviados 1x/semana, opt-out a qualquer momento.")
    
    resp = input(f"\nDeseja habilitar telemetria anônima? [s/N]: ").strip().lower()
    if resp in ("s", "sim", "y", "yes"):
        telemetry.enabled = True
        save_telemetry(data_dir, telemetry)
        print("✅ Telemetria habilitada. Obrigado por ajudar!")
        return True
    
    return False


def prompt_update_check(data_dir: Path, current_version: str, auto: bool = False) -> dict[str, Any] | None:
    """Verifica atualizações e pergunta se deseja atualizar."""
    import asyncio
    
    result = asyncio.run(check_for_updates(data_dir, current_version))
    
    if result.get("available") and not auto:
        print(f"\n{'='*60}")
        print(f"  🔄 ATUALIZAÇÃO DISPONÍVEL!")
        print(f"{'='*60}")
        print(f"\n  Versão atual: {current_version}")
        print(f"  Nova versão:  {result['version']}")
        print(f"  Notas: {result.get('notes', 'N/A')[:200]}...")
        
        resp = input(f"\nDeseja abrir página de download? [S/n]: ").strip().lower()
        if resp in ("s", "sim", "y", "yes", ""):
            import webbrowser
            webbrowser.open(result.get("release_url", f"https://github.com/{GITHUB_REPO}/releases"))
    
    return result


# Função de conveniência para uso no instalador
def run_post_install_checks(data_dir: Path, current_version: str, auto: bool = False) -> None:
    """Executa verificações pós-instalação (telemetria + updates)."""
    # Telemetria opt-in
    if not auto:
        prompt_telemetry_optin(data_dir)
    
    # Verificar atualizações
    if not auto:
        prompt_update_check(data_dir, current_version)


if __name__ == "__main__":
    import sys
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".enxame" / "bee"
    current_version = sys.argv[2] if len(sys.argv) > 2 else "1.0.0"
    
    run_post_install_checks(data_dir, current_version, auto=False)