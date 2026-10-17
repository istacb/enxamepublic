#!/usr/bin/env bash
# ============================================================
# Instalador Enxame - Linux Debian/Ubuntu (next-next-finish)
# ============================================================
set -euo pipefail

# Garantir python3 e pip via apt se faltar
if ! command -v python3 &>/dev/null; then
    echo "[.] Instalando python3 via apt..."
    sudo apt-get update -y
    sudo apt-get install -y python3 python3-pip python3-venv
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENXAME_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
bash "$SCRIPT_DIR/install_unix.sh"
