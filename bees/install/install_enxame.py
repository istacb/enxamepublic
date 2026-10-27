#!/usr/bin/env python3
"""
ENXAME Bee - Universal Installer
Detects platform and runs appropriate installer.

Usage:
    python install_enxame.py [--dry-run] [--skip-ollama] [--skip-model-test]
"""

import os
import sys
import platform
import subprocess
import argparse
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
def step(msg): print(f"\n{BLUE}=== {msg} ==={NC}")

def detect_platform():
    """Detect OS and distribution"""
    system = platform.system().lower()
    
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "macos"
    elif system == "linux":
        # Detect distribution
        try:
            with open("/etc/os-release") as f:
                content = f.read().lower()
                if "ubuntu" in content or "debian" in content or "mint" in content:
                    return "debian"
                elif "arch" in content or "manjaro" in content or "endeavour" in content:
                    return "arch"
                elif "fedora" in content or "rhel" in content or "centos" in content:
                    return "fedora"
                elif "opensuse" in content or "suse" in content:
                    return "opensuse"
        except:
            pass
        return "linux"
    return "unknown"

def run_windows_installer(args):
    """Run Windows installer"""
    step("Instalando ENXAME Bee no Windows")
    
    script_dir = Path(__file__).parent
    bat_file = script_dir / "install_enxame.bat"
    
    if not bat_file.exists():
        error("install_enxame.bat nao encontrado")
        return 1
    
    # Run as admin if not already
    if not is_admin():
        warn("Reiniciando como Administrador...")
        subprocess.run(["powershell", "-Command", f"Start-Process cmd -ArgumentList '/c \"{bat_file}\"' -Verb RunAs"], check=True)
        return 0
    
    return subprocess.run([str(bat_file)], shell=True).returncode

def run_macos_installer(args):
    """Run macOS installer"""
    step("Instalando ENXAME Bee no macOS")
    
    script_dir = Path(__file__).parent
    build_script = script_dir / "build_macos_pkg.sh"
    
    if not build_script.exists():
        error("build_macos_pkg.sh nao encontrado")
        return 1
    
    # Build package first
    log("Construindo pacote .pkg...")
    result = subprocess.run(["bash", str(build_script)], check=False)
    if result.returncode != 0:
        error("Falha ao construir pacote")
        return 1
    
    # Find and install package
    pkg_files = list((script_dir / "dist").glob("enxame-bee-*.pkg"))
    if not pkg_files:
        error("Pacote .pkg nao encontrado em dist/")
        return 1
    
    pkg = max(pkg_files, key=lambda f: f.stat().st_mtime)
    log(f"Instalando {pkg.name}...")
    return subprocess.run(["sudo", "installer", "-pkg", str(pkg), "-target", "/"]).returncode

def run_debian_installer(args):
    """Run Debian/Ubuntu installer"""
    step("Instalando ENXAME Bee no Debian/Ubuntu")
    
    script_dir = Path(__file__).parent
    build_script = script_dir / "build_deb.sh"
    
    if not build_script.exists():
        error("build_deb.sh nao encontrado")
        return 1
    
    # Build package first
    log("Construindo pacote .deb...")
    result = subprocess.run(["bash", str(build_script)], check=False)
    if result.returncode != 0:
        error("Falha ao construir pacote")
        return 1
    
    # Find and install package
    deb_files = list((script_dir / "dist").glob("enxame-bee_*.deb"))
    if not deb_files:
        error("Pacote .deb nao encontrado em dist/")
        return 1
    
    deb = max(deb_files, key=lambda f: f.stat().st_mtime)
    log(f"Instalando {deb.name}...")
    return subprocess.run(["sudo", "dpkg", "-i", str(deb)]).returncode

def run_arch_installer(args):
    """Run Arch Linux installer"""
    step("Instalando ENXAME Bee no Arch Linux")
    
    script_dir = Path(__file__).parent
    pkgbuild_dir = script_dir
    
    # Check if we have PKGBUILD
    pkgbuild = pkgbuild_dir / "PKGBUILD"
    if not pkgbuild.exists():
        error("PKGBUILD nao encontrado")
        return 1
    
    # Build and install with makepkg
    log("Construindo e instalando pacote...")
    os.chdir(str(pkgbuild_dir))
    
    # Install dependencies first
    subprocess.run(["sudo", "pacman", "-S", "--needed", "--noconfirm", 
                    "python", "python-pip", "python-httpx", "python-pydantic",
                    "python-pydantic-settings", "python-psutil", "python-zeroconf",
                    "python-cryptography", "python-rich", "python-pyaml",
                    "curl", "ca-certificates", "sqlite"], check=False)
    
    # Build package
    result = subprocess.run(["makepkg", "-si", "--noconfirm"], check=False)
    return result.returncode

def run_linux_generic_installer(args):
    """Fallback for other Linux distros - use Python installer directly"""
    step("Instalando ENXAME Bee (Python installer)")
    
    # Run the Python installer directly
    cmd = [sys.executable, "-m", "bees.install.install_bee"]
    
    if args.dry_run:
        cmd.append("--dry-run")
    if args.skip_ollama:
        cmd.append("--skip-ollama")
    if args.skip_model_test:
        cmd.append("--skip-model-test")
    if args.force_ollama:
        cmd.append("--force-ollama")
    if args.force_model_download:
        cmd.append("--force-model-download")
    
    return subprocess.run(cmd).returncode

def is_admin():
    """Check if running as administrator on Windows"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def main():
    parser = argparse.ArgumentParser(description="ENXAME Bee - Universal Installer")
    parser.add_argument("--dry-run", action="store_true", help="Simular instalacao")
    parser.add_argument("--skip-ollama", action="store_true", help="Pular instalacao do Ollama")
    parser.add_argument("--skip-model-test", action="store_true", help="Pular teste de inferencia")
    parser.add_argument("--force-ollama", action="store_true", help="Forcar reinstalacao do Ollama")
    parser.add_argument("--force-model-download", action="store_true", help="Forcar redownload do modelo")
    parser.add_argument("--platform", choices=["windows", "macos", "debian", "arch", "linux", "auto"],
                       default="auto", help="Forcar plataforma especifica")
    args = parser.parse_args()
    
    print(f"{BLUE}=================================================={NC}")
    print(f"{BLUE}  ENXAME Bee - Universal Installer v1.0.0{NC}")
    print(f"{BLUE}=================================================={NC}")
    
    # Detect platform
    if args.platform == "auto":
        detected = detect_platform()
        log(f"Plataforma detectada: {detected}")
    else:
        detected = args.platform
    
    # Route to appropriate installer
    if detected == "windows":
        return run_windows_installer(args)
    elif detected == "macos":
        return run_macos_installer(args)
    elif detected == "debian":
        return run_debian_installer(args)
    elif detected == "arch":
        return run_arch_installer(args)
    elif detected == "linux":
        return run_linux_generic_installer(args)
    else:
        error(f"Plataforma nao suportada: {detected}")
        error("Plataformas suportadas: windows, macos, debian, arch, linux")
        return 1

if __name__ == "__main__":
    sys.exit(main())