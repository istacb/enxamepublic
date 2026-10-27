#!/bin/bash
# =============================================================================
# ENXAME Bee - Universal Installer (Shell Wrapper)
# Detecta plataforma e executa instalador apropriado
# =============================================================================

set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
step() { echo -e "\n${BLUE}=== $1 ===${NC}"; }

# Detect platform
detect_platform() {
    local system=$(uname -s | tr '[:upper:]' '[:lower:]')
    
    if [[ "$system" == "linux" ]]; then
        if [[ -f /etc/os-release ]]; then
            . /etc/os-release
            case "$ID" in
                ubuntu|debian|mint|pop|elementary|zorin)
                    echo "debian"
                    return
                    ;;
                arch|manjaro|endeavouros|garuda|artix)
                    echo "arch"
                    return
                    ;;
                fedora|rhel|centos|rocky|alma)
                    echo "fedora"
                    return
                    ;;
                opensuse*|suse)
                    echo "opensuse"
                    return
                    ;;
            esac
        fi
        echo "linux"
    elif [[ "$system" == "darwin" ]]; then
        echo "macos"
    else
        echo "unknown"
    fi
}

# Install on Debian/Ubuntu
install_debian() {
    step "Instalando ENXAME Bee no Debian/Ubuntu"
    
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local build_script="$script_dir/build_deb.sh"
    
    if [[ ! -f "$build_script" ]]; then
        error "build_deb.sh nao encontrado em $script_dir"
        return 1
    fi
    
    log "Construindo pacote .deb..."
    bash "$build_script"
    
    # Find and install
    local deb_files=("$script_dir/dist/enxame-bee_"*.deb)
    if [[ ! -f "${deb_files[0]}" ]]; then
        error "Pacote .deb nao encontrado em dist/"
        return 1
    fi
    
    local deb=$(ls -t "${deb_files[@]}" | head -1)
    log "Instalando $deb..."
    sudo dpkg -i "$deb"
    sudo apt-get install -f -y  # Fix dependencies if needed
}

# Install on Arch Linux
install_arch() {
    step "Instalando ENXAME Bee no Arch Linux"
    
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # Install dependencies
    log "Instalando dependencias..."
    sudo pacman -S --needed --noconfirm \
        python python-pip python-httpx python-pydantic python-pydantic-settings \
        python-psutil python-zeroconf python-cryptography python-rich python-pyaml \
        curl ca-certificates sqlite base-devel git
    
    # Build and install with makepkg
    log "Construindo pacote..."
    cd "$script_dir"
    makepkg -si --noconfirm
}

# Install on Fedora/RHEL
install_fedora() {
    step "Instalando ENXAME Bee no Fedora/RHEL"
    
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # Install dependencies
    log "Instalando dependencias..."
    sudo dnf install -y \
        python3 python3-pip python3-httpx python3-pydantic python3-pydantic-settings \
        python3-psutil python3-zeroconf python3-cryptography python3-rich python3-pyyaml \
        curl ca-certificates sqlite rpm-build
    
    # Use Python installer
    log "Executando instalador Python..."
    python3 -m bees.install.install_bee
}

# Install on macOS
install_macos() {
    step "Instalando ENXAME Bee no macOS"
    
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local build_script="$script_dir/build_macos_pkg.sh"
    
    if [[ ! -f "$build_script" ]]; then
        error "build_macos_pkg.sh nao encontrado"
        return 1
    fi
    
    log "Construindo pacote .pkg..."
    bash "$build_script"
    
    local pkg_files=("$script_dir/dist/enxame-bee-"*.pkg)
    if [[ ! -f "${pkg_files[0]}" ]]; then
        error "Pacote .pkg nao encontrado em dist/"
        return 1
    fi
    
    local pkg=$(ls -t "${pkg_files[@]}" | head -1)
    log "Instalando $pkg..."
    sudo installer -pkg "$pkg" -target /
}

# Install on generic Linux (Python installer)
install_generic_linux() {
    step "Instalando ENXAME Bee (instalador Python)"
    python3 -m bees.install.install_bee "$@"
}

# Main
main() {
    echo -e "${BLUE}==================================================${NC}"
    echo -e "${BLUE}  ENXAME Bee - Universal Installer v1.0.0${NC}"
    echo -e "${BLUE}==================================================${NC}"
    echo
    
    local platform=$(detect_platform)
    log "Plataforma detectada: $platform"
    echo
    
    case "$platform" in
        debian)
            install_debian "$@"
            ;;
        arch)
            install_arch "$@"
            ;;
        fedora)
            install_fedora "$@"
            ;;
        macos)
            install_macos "$@"
            ;;
        linux)
            install_generic_linux "$@"
            ;;
        *)
            error "Plataforma nao suportada: $platform"
            echo "Plataformas suportadas: debian, ubuntu, arch, manjaro, fedora, rhel, macos"
            return 1
            ;;
    esac
}

# Pass all arguments to installer
main "$@"