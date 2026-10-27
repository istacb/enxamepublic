#!/usr/bin/env python3
"""
Build script para criar instaladores empacotados.
Uso: python build_installer.py [--windows] [--macos] [--linux] [--all]
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
INSTALL_DIR = ROOT / "bees" / "install"
DIST_DIR = ROOT / "dist"


def run(cmd, cwd=None):
    print(f"[BUILD] {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd or ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"Comando falhou: {cmd}")
    return result


def build_windows():
    """Build Windows .exe via PyInstaller."""
    print("\n=== Building Windows Installer ===")
    
    # Verificar PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("Instalando PyInstaller...")
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Criar ícone simples se não existir
    icon_path = INSTALL_DIR / "enxame.ico"
    if not icon_path.exists():
        print("Criando ícone placeholder...")
        # PyInstaller vai usar ícone padrão se não existir
    
    # Build
    os.chdir(INSTALL_DIR)
    run([sys.executable, "-m", "PyInstaller", "--clean", "enxame_installer.spec"])
    
    # Copiar para dist/
    exe_src = INSTALL_DIR / "dist" / "enxame_installer.exe"
    if exe_src.exists():
        DIST_DIR.mkdir(exist_ok=True)
        shutil.copy2(exe_src, DIST_DIR / "enxame_installer_windows.exe")
        print(f"✅ Windows installer: {DIST_DIR}/enxame_installer_windows.exe")
    else:
        raise RuntimeError("Build falhou - exe não encontrado")


def build_macos():
    """Build macOS .app ou .pkg (requer macOS)."""
    if platform.system() != "Darwin":
        print("⚠️ Build macOS só pode ser feito no macOS")
        return
    
    print("\n=== Building macOS Installer ===")
    
    # Opção 1: PyInstaller para .app
    try:
        import PyInstaller
    except ImportError:
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    os.chdir(INSTALL_DIR)
    run([
        sys.executable, "-m", "PyInstaller",
        "--clean", "--windowed", "--name", "EnxameInstaller",
        "--icon", "enxame.icns" if (INSTALL_DIR / "enxame.icns").exists() else "",
        "universal_installer.py"
    ])
    
    app_path = INSTALL_DIR / "dist" / "EnxameInstaller.app"
    if app_path.exists():
        DIST_DIR.mkdir(exist_ok=True)
        # Criar DMG
        run([
            "hdiutil", "create", "-volname", "Enxame Installer",
            "-srcfolder", str(app_path), "-ov", "-format", "UDZO",
            str(DIST_DIR / "EnxameInstaller_macos.dmg")
        ])
        print(f"✅ macOS installer: {DIST_DIR}/EnxameInstaller_macos.dmg")


def build_linux():
    """Build Linux AppImage (requer Linux)."""
    if platform.system() != "Linux":
        print("⚠️ Build Linux AppImage só pode ser feito no Linux")
        return
    
    print("\n=== Building Linux AppImage ===")
    
    # Verificar appimagetool
    if not shutil.which("appimagetool"):
        print("Instalando appimagetool...")
        run("wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage -O /tmp/appimagetool")
        run("chmod +x /tmp/appimagetool")
        APPIMAGETOOL = "/tmp/appimagetool"
    else:
        APPIMAGETOOL = "appimagetool"
    
    # Criar estrutura AppDir
    appdir = ROOT / "build" / "EnxameInstaller.AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    appdir.mkdir(parents=True)
    
    # Copiar instalador
    (appdir / "usr" / "bin").mkdir(parents=True)
    shutil.copy2(INSTALL_DIR / "universal_installer.py", appdir / "usr" / "bin" / "enxame-installer")
    
    # Copiar dependências (bees, core, bibliotecario)
    for pkg in ["bees", "core", "bibliotecario"]:
        src = ROOT / pkg
        if src.exists():
            shutil.copytree(src, appdir / "usr" / "lib" / "python3" / "site-packages" / pkg)
    
    # AppRun
    apprun = """#!/bin/bash
export PYTHONPATH="/usr/lib/python3/site-packages:$PYTHONPATH"
exec python3 /usr/bin/enxame-installer "$@"
"""
    (appdir / "AppRun").write_text(apprun)
    (appdir / "AppRun").chmod(0o755)
    
    # .desktop
    desktop = """[Desktop Entry]
Name=Enxame Installer
Exec=AppRun
Icon=enxame
Type=Application
Categories=Network;Utility;
"""
    (appdir / "enxame-installer.desktop").write_text(desktop)
    
    # Ícone placeholder
    (appdir / "enxame.png").write_bytes(b"\x89PNG\r\n\x1a\n")  # Mínimo
    
    # Build AppImage
    DIST_DIR.mkdir(exist_ok=True)
    run(f"{APPIMAGETOOL} {appdir} {DIST_DIR}/EnxameInstaller_linux.AppImage")
    print(f"✅ Linux AppImage: {DIST_DIR}/EnxameInstaller_linux.AppImage")


def build_shell_wrappers():
    """Copia wrappers shell para dist/."""
    print("\n=== Preparando Shell Wrappers ===")
    DIST_DIR.mkdir(exist_ok=True)
    
    # PowerShell para Windows
    ps_src = INSTALL_DIR / "install_enxame.ps1"
    if ps_src.exists():
        shutil.copy2(ps_src, DIST_DIR / "install_enxame.ps1")
        print(f"✅ PowerShell wrapper: {DIST_DIR}/install_enxame.ps1")
    
    # Shell para macOS/Linux
    sh_src = INSTALL_DIR / "install_enxame.sh"
    if sh_src.exists():
        shutil.copy2(sh_src, DIST_DIR / "install_enxame.sh")
        (DIST_DIR / "install_enxame.sh").chmod(0o755)
        print(f"✅ Shell wrapper: {DIST_DIR}/install_enxame.sh")


def main():
    parser = argparse.ArgumentParser(description="Build ENXAME installers")
    parser.add_argument("--windows", action="store_true", help="Build Windows .exe")
    parser.add_argument("--macos", action="store_true", help="Build macOS .dmg/.app")
    parser.add_argument("--linux", action="store_true", help="Build Linux AppImage")
    parser.add_argument("--all", action="store_true", help="Build all platforms")
    parser.add_argument("--wrappers-only", action="store_true", help="Apenas shell wrappers")
    args = parser.parse_args()
    
    if args.all:
        args.windows = args.macos = args.linux = True
    
    if not any([args.windows, args.macos, args.linux, args.wrappers_only]):
        parser.print_help()
        return 1
    
    build_shell_wrappers()
    
    if args.windows:
        build_windows()
    if args.macos:
        build_macos()
    if args.linux:
        build_linux()
    
    print(f"\n✅ Build concluído! Artefatos em: {DIST_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())