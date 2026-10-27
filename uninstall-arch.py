#!/usr/bin/env python3
"""
BEE - Desinstalador Arch Linux
===============================

Remove os arquivos do BEE instalado e opcionalmente o Ollama.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def print_header():
    print("=" * 50)
    print("  BEE - Desinstalador Arch Linux")
    print("=" * 50)


def uninstall_python_venv():
    """Remove o ambiente virtual do Bee."""
    venv_path = Path(".venv-bee")
    if venv_path.exists():
        print("\nRemovendo ambiente virtual .venv-bee...")
        shutil.rmtree(venv_path)
        print("✓ Ambiente virtual removido")
    else:
        print("✓ Ambiente virtual .venv-bee não encontrado (já removido)")


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


def uninstall_ollama_arch():
    """Remove o Ollama no Arch Linux."""
    print("\nRemovendo Ollama do Arch Linux...")

    # Remover pacote via pacman
    result = subprocess.run(
        ["sudo", "pacman", "-Rns", "--noconfirm", "ollama"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("✓ Ollama removido via pacman")
    else:
        print("⚠ Ollama não encontrado via pacman ou já removido")

    # Remover caches do pacman
    subprocess.run(["sudo", "pacman", "-Sc", "--noconfirm"], capture_output=True)


def main():
    print_header()
    print("\nEste desinstalador removerá os arquivos do BEE instalado no Arch Linux.")
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
    print("  [3] Tudo (BEE + Ollama + modelos)")

    choice = input("\nEscolha (1-3, padrão: 3): ").strip() or "3"

    print_header()
    print("\n--- Removendo componentes do BEE ---")

    # Always remove these
    venv_removed = choice in ("1", "3")
    env_removed = choice in ("1", "3")
    dash_removed = choice in ("1", "3")

    if venv_removed:
        uninstall_python_venv()
    if env_removed:
        uninstall_env_file()
    if dash_removed:
        uninstall_dashboard()

    # Ollama removal
    if choice in ("2", "3"):
        print("\n--- Removendo Ollama ---")
        uninstall_ollama_arch()
    else:
        print("\nOllama mantido no sistema.")

    print_header()
    print("=== Desinstalação Concluída ===")
    print("Apenas os arquivos originais do enxamepublic permanecem.")
    print("Reexecute este script se desejar remover mais algo.")


if __name__ == "__main__":
    main()