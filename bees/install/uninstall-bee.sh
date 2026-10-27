#!/bin/bash
# ENXAME Bee - Desinstalador Universal (Shell Wrapper)

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
step() { echo -e "\n${BLUE}=== $1 ===${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect platform
detect_platform() {
    local system=$(uname -s | tr '[:upper:]' '[:lower:]')
    if [[ "$system" == "linux" ]]; then
        if [[ -f /etc/os-release ]]; then
            . /etc/os-release
            case "$ID" in
                ubuntu|debian|mint|pop) echo "debian" ;;
                arch|manjaro) echo "arch" ;;
                fedora|rhel) echo "fedora" ;;
                *) echo "linux" ;;
            esac
        else
            echo "linux"
        fi
    elif [[ "$system" == "darwin" ]]; then
        echo "macos"
    else
        echo "unknown"
    fi
}

main() {
    echo -e "${BLUE}==================================================${NC}"
    echo -e "${BLUE}  ENXAME Bee - Desinstalador${NC}"
    echo -e "${BLUE}==================================================${NC}"
    echo
    
    local platform=$(detect_platform)
    log "Plataforma: $platform"
    
    # Parse args
    local REMOVE_OLLAMA=false
    local FORCE_REMOVE_OLLAMA=false
    local KEEP_DATA=false
    local DRY_RUN=false
    local YES=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --remove-ollama) REMOVE_OLLAMA=true ;;
            --force-remove-ollama) FORCE_REMOVE_OLLAMA=true ;;
            --keep-data) KEEP_DATA=true ;;
            --dry-run) DRY_RUN=true ;;
            -y|--yes) YES=true ;;
            *) error "Opcao desconhecida: $1"; exit 1 ;;
        esac
        shift
    done
    
    if [[ "$YES" != true && "$DRY_RUN" != true ]]; then
        read -p "Isso removera a Abelha completamente. Continuar? [y/N]: " confirm
        if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
            echo "Cancelado."
            exit 0
        fi
    fi
    
    if [[ "$DRY_RUN" == true ]]; then
        log "MODO DRY-RUN - Nenhuma acao sera executada"
    fi
    
    step "Parando servicos..."
    if [[ "$DRY_RUN" != true ]]; then
        case "$platform" in
            linux)
                systemctl --user stop enxame-bee 2>/dev/null || true
                systemctl --user disable enxame-bee 2>/dev/null || true
                sudo systemctl stop enxame-bee 2>/dev/null || true
                sudo systemctl disable enxame-bee 2>/dev/null || true
                ;;
            macos)
                launchctl unload ~/Library/LaunchAgents/enxame-bee.plist 2>/dev/null || true
                sudo launchctl unload /Library/LaunchDaemons/com.enxame.bee.plist 2>/dev/null || true
                ;;
        esac
    fi
    
    step "Removendo binarios..."
    if [[ "$DRY_RUN" != true ]]; then
        case "$platform" in
            linux)
                sudo rm -f /usr/bin/bee /usr/bin/enxame-install-ollama
                sudo rm -rf /opt/enxame-bee
                ;;
            macos)
                sudo rm -f /usr/local/bin/bee /usr/local/bin/enxame-install-ollama
                sudo rm -rf /usr/local/lib/enxame-bee
                ;;
        esac
    fi
    
    step "Removendo configuracoes..."
    if [[ "$DRY_RUN" != true ]]; then
        case "$platform" in
            linux)
                sudo rm -rf /etc/enxame-bee
                sudo rm -f /usr/lib/systemd/system/enxame-bee.service
                sudo rm -f /usr/lib/sysusers.d/enxame-bee.conf
                sudo rm -f /usr/lib/tmpfiles.d/enxame-bee.conf
                ;;
            macos)
                sudo rm -rf /usr/local/etc/enxame-bee
                sudo rm -f /Library/LaunchDaemons/com.enxame.bee.plist
                ;;
        esac
    fi
    
    if [[ "$KEEP_DATA" != true ]]; then
        step "Removendo dados..."
        if [[ "$DRY_RUN" != true ]]; then
            rm -rf "$HOME/.enxame/bee"
            rm -rf "$HOME/.cache/enxame"
        fi
    else
        log "Mantendo dados (--keep-data)"
    fi
    
    step "Limpando shell configs..."
    if [[ "$DRY_RUN" != true ]]; then
        for f in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
            if [[ -f "$f" ]]; then
                sed -i '/enxame\|bee\|BEE_HOME\|ENXAME/d' "$f"
            fi
        done
    fi
    
    if [[ "$REMOVE_OLLAMA" == true || "$FORCE_REMOVE_OLLAMA" == true ]]; then
        step "Removendo Ollama..."
        if [[ "$DRY_RUN" != true ]]; then
            case "$platform" in
                linux)
                    sudo systemctl stop ollama 2>/dev/null || true
                    sudo systemctl disable ollama 2>/dev/null || true
                    sudo rm -f /usr/local/bin/ollama
                    sudo rm -f /etc/systemd/system/ollama.service
                    ;;
                macos)
                    launchctl unload -w /Library/LaunchDaemons/com.ollama.ollama.plist 2>/dev/null || true
                    sudo rm -f /usr/local/bin/ollama
                    sudo rm -rf /usr/local/share/ollama
                    ;;
            esac
            rm -rf "$HOME/.ollama/models"
        fi
    fi
    
    log "=================================================="
    log "Desinstalacao concluida!"
    log "=================================================="
    
    if [[ "$KEEP_DATA" == true ]]; then
        log "Dados mantidos em: $HOME/.enxame/bee"
    fi
}

main "$@"