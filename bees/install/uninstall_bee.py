#!/usr/bin/env python3
"""
ENXAME Bee - Desinstalador Universal
Remove completamente a Abelha do sistema.
"""

import os
import sys
import platform
import subprocess
import argparse
import shutil
from pathlib import Path

# Colors
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def log(msg): print(f"{GREEN}[INFO]{NC} {msg}")
def warn(msg): print(f"{YELLOW}[WARN]{NC} {msg}")
def error(msg): print(f"{RED}[ERROR]{NC} {msg}")
def step(msg): print(f"\n{BLUE}=== {msg} ===${NC}")

def get_data_dir():
    """Retorna diretorio de dados da Abelha"""
    system = platform.system().lower()
    home = Path.home()
    
    if system == "windows":
        return Path(os.getenv("LOCALAPPDATA", home / "AppData" / "Local")) / "enxame" / "bee"
    elif system == "darwin":
        return home / "Library" / "Application Support" / "enxame" / "bee"
    else:
        return home / ".enxame" / "bee"

def stop_bee_service():
    """Para servicos da Abelha"""
    system = platform.system().lower()
    
    try:
        if system == "linux":
            # systemd user service
            subprocess.run(["systemctl", "--user", "stop", "enxame-bee"], capture_output=True)
            subprocess.run(["systemctl", "--user", "disable", "enxame-bee"], capture_output=True)
            # systemd system service
            subprocess.run(["sudo", "systemctl", "stop", "enxame-bee"], capture_output=True)
            subprocess.run(["sudo", "systemctl", "disable", "enxame-bee"], capture_output=True)
        elif system == "darwin":
            # launchd
            subprocess.run(["launchctl", "unload", "~/Library/LaunchAgents/enxame-bee.plist"], capture_output=True)
        elif system == "windows":
            # Windows service ou task scheduler
            subprocess.run(["schtasks", "/Delete", "/TN", "ENXAME Bee", "/F"], capture_output=True, shell=True)
    except Exception as e:
        warn(f"Erro ao parar servicos: {e}")

def remove_data_dir(keep_data: bool = False):
    """Remove diretorio de dados"""
    if keep_data:
        log("Mantendo dados da Abelha (--keep-data)")
        return
    
    data_dir = get_data_dir()
    if data_dir.exists():
        log(f"Removendo diretorio de dados: {data_dir}")
        try:
            shutil.rmtree(data_dir)
            log("Dados removidos")
        except Exception as e:
            error(f"Falha ao remover dados: {e}")

def remove_config_files():
    """Remove arquivos de configuracao"""
    system = platform.system().lower()
    
    configs = []
    
    if system == "linux":
        configs.extend([
            Path("/etc/enxame-bee"),
            Path("/usr/lib/systemd/system/enxame-bee.service"),
            Path("/usr/lib/sysusers.d/enxame-bee.conf"),
            Path("/usr/lib/tmpfiles.d/enxame-bee.conf"),
        ])
    elif system == "darwin":
        configs.extend([
            Path("/usr/local/etc/enxame-bee"),
            Path("/Library/LaunchDaemons/com.enxame.bee.plist"),
        ])
    elif system == "windows":
        configs.extend([
            Path(os.getenv("PROGRAMDATA", "C:/ProgramData")) / "enxame-bee",
        ])
    
    for config in configs:
        if config.exists():
            try:
                if config.is_dir():
                    shutil.rmtree(config)
                else:
                    config.unlink()
                log(f"Removido: {config}")
            except Exception as e:
                warn(f"Erro ao remover {config}: {e}")

def remove_binaries():
    """Remove binarios e wrappers"""
    system = platform.system().lower()
    
    bins = []
    
    if system == "linux":
        bins.extend([
            Path("/usr/bin/bee"),
            Path("/usr/bin/enxame-install-ollama"),
            Path("/opt/enxame-bee"),
        ])
    elif system == "darwin":
        bins.extend([
            Path("/usr/local/bin/bee"),
            Path("/usr/local/bin/enxame-install-ollama"),
            Path("/usr/local/lib/enxame-bee"),
        ])
    elif system == "windows":
        bins.extend([
            Path(os.getenv("PROGRAMFILES", "C:/Program Files")) / "ENXAME Bee",
            Path(os.getenv("LOCALAPPDATA", "")) / "ENXAME Bee",
        ])
    
    for bin_path in bins:
        if bin_path.exists():
            try:
                if bin_path.is_dir():
                    shutil.rmtree(bin_path)
                else:
                    bin_path.unlink()
                log(f"Removido: {bin_path}")
            except Exception as e:
                warn(f"Erro ao remover {bin_path}: {e}")

def remove_python_packages():
    """Remove pacotes Python instalados (opcional)"""
    # Cuidado: nao remover pacotes que outros apps precisam
    # Apenas avisar
    warn("Pacotes Python (httpx, pydantic, etc.) NAO foram removidos")
    warn("Use 'pip uninstall' manualmente se desejar remove-los")

def remove_ollama(force: bool = False):
    """Remove Ollama (opcional)"""
    if not force:
        return
    
    log("Removendo Ollama...")
    system = platform.system().lower()
    
    try:
        if system == "linux":
            subprocess.run(["sudo", "systemctl", "stop", "ollama"], capture_output=True)
            subprocess.run(["sudo", "systemctl", "disable", "ollama"], capture_output=True)
            subprocess.run(["sudo", "rm", "-f", "/usr/local/bin/ollama"], capture_output=True)
            subprocess.run(["sudo", "rm", "-f", "/etc/systemd/system/ollama.service"], capture_output=True)
        elif system == "darwin":
            subprocess.run(["launchctl", "unload", "-w", "/Library/LaunchDaemons/com.ollama.ollama.plist"], capture_output=True)
            subprocess.run(["sudo", "rm", "-f", "/usr/local/bin/ollama"], capture_output=True)
            subprocess.run(["sudo", "rm", "-rf", "/usr/local/share/ollama"], capture_output=True)
        elif system == "windows":
            subprocess.run(["ollama", "stop"], capture_output=True, shell=True)
            subprocess.run(["powershell", "-Command", "Uninstall-Package -Name Ollama"], capture_output=True)
        
        # Remover modelos
        ollama_models = Path.home() / ".ollama" / "models"
        if ollama_models.exists():
            shutil.rmtree(ollama_models)
        
        log("Ollama removido")
    except Exception as e:
        error(f"Erro ao remover Ollama: {e}")

def clean_shell_configs():
    """Remove linhas adicionadas aos .bashrc/.zshrc"""
    shell_files = [
        Path.home() / ".bashrc",
        Path.home() / ".zshrc",
        Path.home() / ".profile",
    ]
    
    patterns = ["enxame", "bee", "BEE_HOME", "ENXAME"]
    
    for shell_file in shell_files:
        if shell_file.exists():
            try:
                content = shell_file.read_text()
                lines = content.splitlines()
                filtered = [l for l in lines if not any(p in l for p in patterns)]
                if len(filtered) != len(lines):
                    shell_file.write_text("\n".join(filtered) + "\n")
                    log(f"Limpado: {shell_file}")
            except Exception as e:
                warn(f"Erro ao limpar {shell_file}: {e}")

def main():
    parser = argparse.ArgumentParser(description="ENXAME Bee - Desinstalador")
    parser.add_argument("--remove-ollama", action="store_true", help="Tambem remover Ollama")
    parser.add_argument("--force-remove-ollama", action="store_true", help="Forcar remocao do Ollama mesmo se nao instalado pela Abelha")
    parser.add_argument("--keep-data", action="store_true", help="Manter documentos e indices")
    parser.add_argument("--dry-run", action="store_true", help="Simular desinstalacao")
    parser.add_argument("-y", "--yes", action="store_true", help="Confirmar automaticamente")
    args = parser.parse_args()
    
    print(f"{BLUE}==================================================${NC}")
    print(f"{BLUE}  ENXAME Bee - Desinstalador v1.0.0${NC}")
    print(f"{BLUE}==================================================${NC}")
    
    if not args.yes and not args.dry_run:
        confirm = input("Isso removera a Abelha completamente. Continuar? [y/N]: ")
        if confirm.lower() != 'y':
            print("Cancelado.")
            return 0
    
    if args.dry_run:
        log("MODO DRY-RUN - Nenhuma acao sera executada")
    
    step("Parando servicos da Abelha...")
    if not args.dry_run:
        stop_bee_service()
    
    step("Removendo binarios...")
    if not args.dry_run:
        remove_binaries()
    
    step("Removendo configuracoes...")
    if not args.dry_run:
        remove_config_files()
    
    step("Removendo dados...")
    if not args.dry_run:
        remove_data_dir(args.keep_data)
    
    step("Limpando configuracoes de shell...")
    if not args.dry_run:
        clean_shell_configs()
    
    if args.remove_ollama or args.force_remove_ollama:
        step("Removendo Ollama...")
        if not args.dry_run:
            remove_ollama(force=args.force_remove_ollama)
    
    step("Removendo pacotes Python (opcional)...")
    if not args.dry_run:
        remove_python_packages()
    
    log("==================================================")
    log("Desinstalacao concluida!")
    log("==================================================")
    
    if args.keep_data:
        log(f"Dados mantidos em: {get_data_dir()}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())