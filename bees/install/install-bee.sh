#!/bin/bash
#
# BEE-0008 — Instalador Rápido da Abelha (Linux/macOS)
#
# Script wrapper que:
# 1. Verifica dependências do sistema
# 2. Baixa instalador Python se necessário
# 3. Executa instalação com opções padrão seguras
#
# Uso:
#   curl -fsSL https://.../install-bee.sh | bash
#   ou
#   ./install-bee.sh [--force-ollama] [--dry-run]
#

set -e  # Sair em caso de erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funções de log
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detectar sistema operacional
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    else
        echo "unknown"
    fi
}

# Verificar Python
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        log_error "Python não encontrado. Instale Python 3.8+"
        exit 1
    fi
    
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    log_info "Python encontrado: $PYTHON_CMD ($PYTHON_VERSION)"
}

# Verificar pip
check_pip() {
    if ! $PYTHON_CMD -m pip --version &> /dev/null; then
        log_warn "pip não encontrado. Tentando instalar..."
        
        OS=$(detect_os)
        if [[ "$OS" == "linux" ]]; then
            if command -v apt &> /dev/null; then
                sudo apt update && sudo apt install -y python3-pip
            elif command -v yum &> /dev/null; then
                sudo yum install -y python3-pip
            elif command -v dnf &> /dev/null; then
                sudo dnf install -y python3-pip
            fi
        elif [[ "$OS" == "macos" ]]; then
            if ! command -v brew &> /dev/null; then
                log_info "Instalando Homebrew..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            fi
            brew install python
        fi
    fi
    
    log_success "pip verificado"
}

# Instalar dependências Python necessárias
install_dependencies() {
    log_info "Instalando dependências Python..."
    
    DEPS=(
        "requests"
        "psutil"
    )
    
    # Determinar site-packages path baseado na versão do Python
    PY_VER=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    SITE_PACKAGES="$HOME/.local/lib/python${PY_VER}/site-packages"
    
    for dep in "${DEPS[@]}"; do
        if ! $PYTHON_CMD -c "import $dep" &> /dev/null; then
            log_info "Instalando $dep..."
            # Tentar instalação user-first
            if $PYTHON_CMD -m pip install --user "$dep" &> /dev/null; then
                log_info "$dep instalado via --user"
            else
                # Fallback: instalar diretamente no site-packages do usuário (evita PEP 668)
                log_warn "Falha --user, tentando instalação direta no site-packages..."
                $PYTHON_CMD -m pip install --target "$SITE_PACKAGES" "$dep" || {
                    log_error "Falha crítica: não foi possível instalar $dep"
                    exit 1
                }
            fi
        fi
    done
    
    log_success "Dependências instaladas"
}

# Verificar espaço em disco
check_disk_space() {
    REQUIRED_GB=10
    AVAILABLE_GB=$(df -h / | tail -1 | awk '{print $4}' | sed 's/G//')
    
    if [[ -z "$AVAILABLE_GB" ]] || [[ "$AVAILABLE_GB" < "$REQUIRED_GB" ]]; then
        log_warn "Espaço em disco insuficiente. Recomendado: ${REQUIRED_GB}GB, Disponível: ${AVAILABLE_GB:-0}GB"
        read -p "Continuar mesmo assim? (y/N): " response
        if [[ "$response" != "y" && "$response" != "Y" ]]; then
            log_info "Instalação cancelada"
            exit 0
        fi
    else
        log_success "Espaço em disco OK: ${AVAILABLE_GB}GB disponíveis"
    fi
}

# Download do instalador Python
download_installer() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    INSTALLER_PATH="$SCRIPT_DIR/install_bee.py"
    
    if [[ -f "$INSTALLER_PATH" ]]; then
        log_info "Instalador Python já existe: $INSTALLER_PATH"
        return 0
    fi
    
    log_info "Baixando instalador Python..."
    
    # Se estiver no repositório, copiar
    if [[ -f "/workspace/bees/install/install_bee.py" ]]; then
        cp /workspace/bees/install/install_bee.py "$INSTALLER_PATH"
        log_success "Instalador copiado do repositório"
        return 0
    fi
    
    # Fallback: download direto (URL fictícia para exemplo)
    # curl -fsSL "https://raw.githubusercontent.com/enxamepublic/main/bees/install/install_bee.py" -o "$INSTALLER_PATH"
    
    log_error "Instalador não encontrado. Execute a partir do repositório."
    exit 1
}

# Executar instalador Python
run_installer() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    INSTALLER_PATH="$SCRIPT_DIR/install_bee.py"
    
    log_info "Executando instalador Python..."
    log_info "Opções: $@"
    
    $PYTHON_CMD "$INSTALLER_PATH" "$@"
    
    EXIT_CODE=$?
    
    if [[ $EXIT_CODE -eq 0 ]]; then
        log_success "Instalação concluída com sucesso!"
        echo ""
        echo "════════════════════════════════════════════"
        echo "🐝 ABELHA INSTALADA"
        echo "════════════════════════════════════════════"
        echo ""
        echo "Próximos passos:"
        echo "  1. Execute: python3 -m bees.cli status"
        echo "  2. Para iniciar: python3 -m bees.cli start"
        echo "  3. Documentação: bees/docs/"
        echo ""
    else
        log_error "Instalação falhou com código $EXIT_CODE"
        log_warn "Verifique o log em: ~/.enxame/bee/install.log"
    fi
    
    return $EXIT_CODE
}

# Main
main() {
    echo "════════════════════════════════════════════"
    echo "🐝 INSTALADOR DA ABELHA"
    echo "════════════════════════════════════════════"
    echo ""
    
    OS=$(detect_os)
    log_info "Sistema operacional: $OS"
    
    # Verificações preliminares
    check_python
    check_pip
    install_dependencies
    check_disk_space
    
    # Download/copiar instalador
    download_installer
    
    # Executar com argumentos passados
    run_installer "$@"
}

# Executar main
main "$@"
