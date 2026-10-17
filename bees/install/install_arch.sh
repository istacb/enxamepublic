#!/usr/bin/env bash
# ============================================================
# Instalador Enxame - Linux Arch (next-next-finish)
# ============================================================
set -euo pipefail

# Garantir python e pip via pacman se faltar
if ! command -v python3 &>/dev/null; then
    echo "[.] Instalando python via pacman..."
    sudo pacman -Sy --needed --noconfirm python python-pip
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENXAME_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
bash "$SCRIPT_DIR/install_unix.sh"
