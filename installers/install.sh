#!/bin/bash
# =============================================================================
# ENXAME - Instalador Unificado (Shell Wrapper)
# Detecta plataforma e executa instalador Python next-next-finish
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLER="$SCRIPT_DIR/install.py"

if [[ ! -f "$INSTALLER" ]]; then
    echo "Instalador Python não encontrado: $INSTALLER"
    exit 1
fi

exec python3 "$INSTALLER" "$@"
