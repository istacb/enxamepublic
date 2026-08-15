#!/bin/bash
#
# BEE-0008 — Desinstalador Rápido da Abelha (Linux/macOS)
#
# Script wrapper que:
# 1. Verifica estado atual da instalação
# 2. Executa desinstalador Python com opções
# 3. Limpa resíduos do sistema
#
# Uso:
#   ./uninstall-bee.sh [--remove-ollama] [--keep-data]
#

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    else
        echo "unknown"
    fi
}

check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        log_error "Python não encontrado"
        exit 1
    fi
}

find_uninstaller() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    UNINSTALLER_PATH="$SCRIPT_DIR/uninstall_bee.py"
    
    if [[ -f "$UNINSTALLER_PATH" ]]; then
        echo "$UNINSTALLER_PATH"
        return 0
    fi
    
    if [[ -f "/workspace/bees/install/uninstall_bee.py" ]]; then
        echo "/workspace/bees/install/uninstall_bee.py"
        return 0
    fi
    
    log_error "Desinstalador não encontrado"
    exit 1
}

show_status() {
    echo ""
    log_info "Verificando estado atual..."
    
    BEE_HOME="$HOME/.enxame/bee"
    
    if [[ -d "$BEE_HOME" ]]; then
        log_info "Abelha instalada em: $BEE_HOME"
        
        if [[ -f "$BEE_HOME/manifest.json" ]]; then
            log_info "Manifesto encontrado"
        fi
        
        MODEL_COUNT=$(ls -1 "$BEE_HOME/models" 2>/dev/null | wc -l || echo "0")
        log_info "Modelos baixados: $MODEL_COUNT"
    else
        log_warn "Abelha não encontrada em $BEE_HOME"
    fi
    
    if command -v ollama &> /dev/null; then
        OLLAMA_VERSION=$(ollama --version 2>&1 || echo "unknown")
        log_info "Ollama instalado: $OLLAMA_VERSION"
        
        MODEL_LIST=$(ollama list 2>/dev/null | tail -n +2 | wc -l || echo "0")
        log_info "Modelos no Ollama: $MODEL_LIST"
    else
        log_info "Ollama não encontrado no PATH"
    fi
    
    echo ""
}

confirm_removal() {
    if [[ "$AUTO_CONFIRM" == "true" ]]; then
        return 0
    fi
    
    echo "════════════════════════════════════════════"
    echo "⚠️  ATENÇÃO: DESINSTALAÇÃO DA ABELHA"
    echo "════════════════════════════════════════════"
    echo ""
    
    if [[ "$REMOVE_OLLAMA" == "true" ]]; then
        echo "Esta operação irá REMOVER:"
        echo "  ✓ Configurações da Abelha"
        echo "  ✓ Modelos baixados"
        echo "  ✓ Manifesto e logs"
        [[ "$KEEP_DATA" != "true" ]] && echo "  ✓ Documentos indexados"
        echo "  ✓ Ollama (runtime de IA)"
    else
        echo "Esta operação irá REMOVER:"
        echo "  ✓ Configurações da Abelha"
        echo "  ✓ Modelos baixados"
        echo "  ✓ Manifesto e logs"
        [[ "$KEEP_DATA" != "true" ]] && echo "  ✓ Documentos indexados"
        echo ""
        echo "Ollama NÃO será removido (use --remove-ollama)"
    fi
    
    echo ""
    read -p "Deseja continuar? (y/N): " response
    
    if [[ "$response" != "y" && "$response" != "Y" ]]; then
        log_info "Desinstalação cancelada"
        exit 0
    fi
}

main() {
    echo "════════════════════════════════════════════"
    echo "🐝 DESINSTALADOR DA ABELHA"
    echo "════════════════════════════════════════════"
    echo ""
    
    OS=$(detect_os)
    log_info "Sistema operacional: $OS"
    
    # Parse arguments
    REMOVE_OLLAMA="false"
    KEEP_DATA="false"
    AUTO_CONFIRM="false"
    DRY_RUN="false"
    
    for arg in "$@"; do
        case $arg in
            --remove-ollama)
                REMOVE_OLLAMA="true"
                shift
                ;;
            --keep-data)
                KEEP_DATA="true"
                shift
                ;;
            -y|--yes)
                AUTO_CONFIRM="true"
                shift
                ;;
            --dry-run)
                DRY_RUN="true"
                shift
                ;;
        esac
    done
    
    show_status
    confirm_removal
    
    check_python
    
    UNINSTALLER=$(find_uninstaller)
    log_info "Usando desinstalador: $UNINSTALLER"
    
    # Build command
    CMD="$PYTHON_CMD $UNINSTALLER"
    [[ "$REMOVE_OLLAMA" == "true" ]] && CMD="$CMD --remove-ollama"
    [[ "$KEEP_DATA" == "true" ]] && CMD="$CMD --keep-data"
    [[ "$AUTO_CONFIRM" == "true" ]] && CMD="$CMD -y"
    [[ "$DRY_RUN" == "true" ]] && CMD="$CMD --dry-run"
    
    log_info "Executando: $CMD"
    echo ""
    
    eval "$CMD"
    EXIT_CODE=$?
    
    if [[ $EXIT_CODE -eq 0 ]]; then
        echo ""
        log_success "Desinstalação concluída!"
        
        if [[ "$DRY_RUN" != "true" ]]; then
            # Limpar shell configs
            for config in ~/.bashrc ~/.zshrc ~/.profile; do
                if [[ -f "$config" ]]; then
                    grep -v "BEE_HOME\|OLLAMA" "$config" > "$config.tmp" && mv "$config.tmp" "$config"
                fi
            done 2>/dev/null || true
            
            log_info "Shell configs limpos"
        fi
    else
        log_error "Desinstalação falhou com código $EXIT_CODE"
    fi
    
    return $EXIT_CODE
}

main "$@"
