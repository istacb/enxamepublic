#!/usr/bin/env bash
# ============================================================
# Instalador Enxame - macOS (next-next-finish)
# ============================================================
set -euo pipefail

# Garantir python3 via brew se faltar
if ! command -v python3 &>/dev/null; then
    if command -v brew &>/dev/null; then
        echo "[.] Instalando python3 via brew..."
        brew install python@3.11 || brew install python
    else
        echo "[!] Python3 nao encontrado e o Homebrew nao esta instalado."
        echo "    Instale o Python 3.10+ em https://www.python.org/downloads/"
        exit 1
    fi
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENXAME_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
bash "$SCRIPT_DIR/install_unix.sh"
