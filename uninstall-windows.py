#!/usr/bin/env python3
"""
BEE - Desinstalador Windows
==========================

Remove os arquivos do BEE instalado e opcionalmente o Ollama.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def print_header():
    print("=" * 50)
    print("  BEE - Desinstalador Windows")
    print("=" * 50)


def uninstall_python_venv():
    """Remove o ambiente virtual do Bee."""
    venv_path = Path(".venv-bee")
    if venv_path.exists():
        print("\nRemovendo ambiente virtual .venv-bee...")
        shutil.rmtree(venv_path)
        print("✓ Ambiente virtual removido")
    else:
        print("✓ Ambiente virtual .venv-beu não encontrado (já removido)")


def uninstall_env_file():
    """Remove o arquivo .env."""
    env_path = Path(".env")
    if env_path.exists():
        print("\nRemovendo arquivo .env...")
        env_path.unlink()
        print("✓ Arquivo .env removido")
    else:
        print("✓ Arquivo .env não encontrado (já removido)")


def uninstall_dashboard():
    """Remove o dashboard HTML."""
    dashboard_path = Path("bee-dashboard.html")
    if dashboard_path.exists():
        print("\nRemovendo dashboard bee-dashboard.html...")
        dashboard_path.unlink()
        print("✓ Dashboard removido")
    else:
        print("✓ Dashboard não encontrado (já removido)")


def uninstall_ollama_windows():
    """Remove o Ollama no Windows."""
    print("\nRemovendo Ollama do Windows...")

    # Tentar parar o processo
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "ollama.exe"],
            capture_output=True,
            timeout=5,
        )
        print("✓ Processo Ollama interrompido")
    except:
        print("ℹ Processo Ollama não estava rodando ou já estava parado")

    # Remover pasta de instalação
    ollama_dirs = [
        r"C:\ProgramData\Ollama",
        r"C:\Users\%USERNAME%\AppData\Local\Ollama",
    ]

    for dir_path in ollama_dirs:
        # Expandir %USERNAME%
        expanded = dir_path.replace("%USERNAME%", os.environ.get("USERNAME", ""))
        if os.path.exists(expanded):
            shutil.rmtree(expanded)
            print(f"✓ Pasta removida: {expanded}")

    # Remover atalho do menu Iniciar (aproximado)
    start_menu = Path(
        f"C:\\Users\\{os.environ.get('USERNAME', 'DefaultUser')}\\Start Menu\\Programs\\Ollama"
    )
    if start_menu.exists():
        shutil.rmtree(start_menu)
        print("✓ Atalho do menu Iniciar removido")

    print("✓ Ollama removido do Windows")


def main():
    print_header()
    print("\nEste desinstalador removerá os arquivos do BEE do seu sistema.")
    print()

    # Confirmar
    confirm = input("Tem certeza que deseja continuar? (s/N): ").strip().lower()
    if confirm not in ("s", "sim", "y", "yes"):
        print("Operação cancelada.")
        return

    # Coletar o que remover
    print("\nO que deseja remover?")
    print("  [1] Apenas arquivos do BEE (config, dados, dashboard, venv)")
    print("  [2] Remover Ollama também")
    print("  [3] Tudo (BEE + Ollama + venv + config)")

    choice = input("\nEscolha (1-3, padrão: 3): ").strip() or "3"

    print_header()
    print("\n--- Removendo componentes do BEE ---")

    # Always remove these
    uninstall_venv = choice in ("1", "3")
    uninstall_env = choice in ("1", "3")
    uninstall_dash = choice in ("1", "3")

    if uninstall_venv:
        uninstall_python_venv()
    if uninstall_env:
        uninstall_env_file()
    if uninstall_dash:
        uninstall_dashboard()

    # Ollama removal
    if choice in ("2", "3"):
        print("\n--- Removendo Ollama ---")
        uninstall_ollama_windows()
    else:
        print("\nOllama mantido no sistema.")

    print_header()
    print("=== Desinstalação Concluída ===")
    print("Apenas os arquivos originais do enxamepublic permanecem.")
    print("Reexecute este script se desejar remover mais algo.")


if __name__ == "__main__":
    main()