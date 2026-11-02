#!/bin/bash
# =============================================================================
# ENXAME - Instalador Oficial (Launcher Multi-Plataforma)
# =============================================================================
# Detecta o sistema operacional e executa o instalador apropriado.
# Fluxo interativo: pergunta a pasta de instalação e se inicia junto ao boot.
#
# Uso:
#   sudo ./api/install/install.sh          # Linux / macOS
#   ./api/install/install.bat              # Windows (duplo-clique)
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

detect_os() {
    case "$(uname -s 2>/dev/null)" in
        Linux*)   echo "linux" ;;
        Darwin*)  echo "macos" ;;
        CYGWIN*|MINGW*|MSYS*) echo "windows" ;;
        *)        echo "unknown" ;;
    esac
}

OS_TYPE=$(detect_os)

echo ""
echo "╔═══════════════════════════════════════════════════════════════════════╗"
echo "║                    ENXAME - Instalador Oficial                      ║"
echo "║                        v1.0 - Instalação                            ║"
echo "╚═══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Sistema detectado: $OS_TYPE"
echo ""

case "$OS_TYPE" in
    linux)
        exec bash "$SCRIPT_DIR/install-linux.sh" "$@"
        ;;
    macos)
        exec bash "$SCRIPT_DIR/install-macos.sh" "$@"
        ;;
    windows)
        echo "No Windows, duplo-clique em: api/install/install-windows.bat"
        echo "Ou execute no PowerShell: & ./api/install/install-windows.bat"
        exit 0
        ;;
    *)
        echo "Sistema operacional não detectado automaticamente."
        echo ""
        echo "Escolha manualmente:"
        echo "  [1] Linux (Ubuntu/Debian e similares)"
        echo "  [2] macOS"
        echo "  [3] Windows"
        echo ""
        read -r -p "Opção (1-3): " choice
        case "$choice" in
            1) exec bash "$SCRIPT_DIR/install-linux.sh" "$@" ;;
            2) exec bash "$SCRIPT_DIR/install-macos.sh" "$@" ;;
            3)
                echo "No Windows, duplo-clique em: api/install/install-windows.bat"
                exit 0
                ;;
            *) echo "Opção inválida."; exit 1 ;;
        esac
        ;;
esac
