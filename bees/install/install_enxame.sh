#!/bin/bash
# ENXAME Universal Installer - macOS/Linux Wrapper
# Uso: curl -fsSL https://.../install_enxame.sh | bash
#      ou ./install_enxame.sh [--auto] [--force-ollama] ...

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[AVISO]${NC} $*"; }
log_error() { echo -e "${RED}[ERRO]${NC} $*" >&2; }

print_banner() {
    echo -e "\n${BLUE}============================================"
    echo -e "  ENXAME UNIVERSAL INSTALLER - macOS/Linux"
    echo -e "============================================${NC}\n"
}

# Detectar Python
detect_python() {
    if command -v python3 &>/dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &>/dev/null; then
        PYTHON_CMD="python"
    else
        log_warn "Python não encontrado. Instalando..."
        install_python
    fi
    
    PY_VER=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    log_ok "Python encontrado: $PYTHON_CMD ($PY_VER)"
    
    # Verificar versão >= 3.10
    MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
    MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")
    if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]; }; then
        log_error "Python 3.10+ necessário (encontrado $MAJOR.$MINOR)"
        exit 1
    fi
}

install_python() {
    OS=$(uname -s)
    if [ "$OS" = "Darwin" ]; then
        if ! command -v brew &>/dev/null; then
            log_info "Instalando Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        brew install python@3.11
    elif [ "$OS" = "Linux" ]; then
        if command -v apt &>/dev/null; then
            sudo apt update && sudo apt install -y python3 python3-pip python3-venv
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y python3 python3-pip
        elif command -v pacman &>/dev/null; then
            sudo pacman -S --noconfirm python python-pip
        elif command -v zypper &>/dev/null; then
            sudo zypper install -y python3 python3-pip
        else
            log_error "Gerenciador de pacotes não suportado. Instale Python 3.10+ manualmente."
            exit 1
        fi
    fi
}

# Verificar pip
ensure_pip() {
    if ! $PYTHON_CMD -m pip --version &>/dev/null; then
        log_warn "pip não encontrado. Instalando..."
        $PYTHON_CMD -m ensurepip --upgrade
    fi
}

# Baixar instalador universal
download_installer() {
    INSTALLER_URL="https://raw.githubusercontent.com/enxamepublic/enxamepublic/main/bees/install/universal_installer.py"
    INSTALLER_PATH="/tmp/enxame_universal_installer.py"
    
    log_info "Baixando instalador universal..."
    if command -v curl &>/dev/null; then
        curl -fsSL "$INSTALLER_URL" -o "$INSTALLER_PATH"
    elif command -v wget &>/dev/null; then
        wget -q "$INSTALLER_URL" -O "$INSTALLER_PATH"
    else
        log_error "curl ou wget necessário para download"
        exit 1
    fi
    log_ok "Instalador baixado em $INSTALLER_PATH"
}

# Main
main() {
    print_banner
    
    # Parse args
    ARGS=()
    for arg in "$@"; do
        ARGS+=("$arg")
    done
    
    detect_python
    ensure_pip
    download_installer
    
    log_info "Executando instalador universal..."
    log_info "Isso pode levar vários minutos (download de modelos)...\n"
    
    $PYTHON_CMD "$INSTALLER_PATH" "${ARGS[@]}"
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        log_ok "\nInstalação concluída com sucesso!"
    else
        log_error "\nInstalação falhou (código $EXIT_CODE)"
        log_info "Verifique o log em: ~/.local/share/enxame/bee/install.log (Linux) ou ~/Library/Application Support/enxame/bee/install.log (macOS)"
    fi
    
    exit $EXIT_CODE
}

main "$@"