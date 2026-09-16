#!/bin/bash
# ENXAME Bee - macOS Uninstaller

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

REMOVE_OLLAMA=false
FORCE_OLLAMA=false
KEEP_DATA=false
DRY_RUN=false
YES=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --remove-ollama) REMOVE_OLLAMA=true ;;
        --force-remove-ollama) FORCE_OLLAMA=true ;;
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
    # Stop user launch agent
    launchctl unload ~/Library/LaunchAgents/com.enxame.bee.plist 2>/dev/null || true
    
    # Stop system launch daemon
    sudo launchctl unload /Library/LaunchDaemons/com.enxame.bee.plist 2>/dev/null || true
fi

step "Removendo binarios..."
if [[ "$DRY_RUN" != true ]]; then
    sudo rm -f /usr/local/bin/bee
    sudo rm -f /usr/local/bin/enxame-install-ollama
    sudo rm -rf /usr/local/lib/enxame-bee
fi

step "Removendo configuracoes..."
if [[ "$DRY_RUN" != true ]]; then
    sudo rm -rf /usr/local/etc/enxame-bee
    sudo rm -f /Library/LaunchDaemons/com.enxame.bee.plist
    rm -f ~/Library/LaunchAgents/com.enxame.bee.plist
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
            sed -i '' '/enxame\|bee\|BEE_HOME\|ENXAME/d' "$f"
        fi
    done
fi

if [[ "$REMOVE_OLLAMA" == true || "$FORCE_OLLAMA" == true ]]; then
    step "Removendo Ollama..."
    if [[ "$DRY_RUN" != true ]]; then
        launchctl unload -w /Library/LaunchDaemons/com.ollama.ollama.plist 2>/dev/null || true
        sudo rm -f /usr/local/bin/ollama
        sudo rm -rf /usr/local/share/ollama
        rm -rf "$HOME/.ollama/models"
    fi
fi

log "=================================================="
log "Desinstalacao concluida!"
log "=================================================="

if [[ "$KEEP_DATA" == true ]]; then
    log "Dados mantidos em: $HOME/.enxame/bee"
fi