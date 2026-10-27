#!/bin/bash
# =============================================================================
# ENXAME Bee - Debian/Ubuntu Package Builder
# Creates a .deb package for Debian-based systems
# =============================================================================

set -euo pipefail

# Configuration
PACKAGE_NAME="enxame-bee"
VERSION="1.0.0"
ARCHITECTURE="amd64"
MAINTAINER="Enxame Project <contato@enxame.dev>"
DESCRIPTION="ENXAME Bee - Abelha standalone offline-first com RAG local, descoberta mDNS e protocolo P2P"
HOMEPAGE="https://github.com/enxame/enxamepublic"
SECTION="utils"
PRIORITY="optional"

# Dependencies
DEPENDS="python3 (>=3.10), python3-pip, python3-venv, curl, ca-certificates, \
         libssl3, libffi8, zlib1g, sqlite3"
RECOMMENDS="ollama, tesseract-ocr, poppler-utils"
SUGGESTS="nvidia-driver, cuda-toolkit"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$SCRIPT_DIR/build_deb"
DEB_DIR="$BUILD_DIR/deb"
DEBIAN_DIR="$DEB_DIR/DEBIAN"
OPT_DIR="$DEB_DIR/opt/enxame-bee"
ETC_DIR="$DEB_DIR/etc"
SYSTEMD_DIR="$DEB_DIR/lib/systemd/system"
BIN_DIR="$DEB_DIR/usr/bin"
SHARE_DIR="$DEB_DIR/usr/share/enxame-bee"
OUTPUT_DIR="$SCRIPT_DIR/dist"

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

# Cleanup
cleanup() {
    log "Limpando build anterior..."
    rm -rf "$BUILD_DIR"
}
trap cleanup EXIT

# =============================================================================
# Main build process
# =============================================================================
main() {
    step "Iniciando build do .deb para $PACKAGE_NAME v$VERSION"
    
    # Create directory structure
    mkdir -p "$DEBIAN_DIR"
    mkdir -p "$OPT_DIR"
    mkdir -p "$ETC_DIR/enxame-bee"
    mkdir -p "$SYSTEMD_DIR"
    mkdir -p "$BIN_DIR"
    mkdir -p "$SHARE_DIR"
    mkdir -p "$OUTPUT_DIR"
    
    # -------------------------------------------------------------------------
    # Copy Python package
    # -------------------------------------------------------------------------
    step "Copiando pacote Python para /opt/enxame-bee..."
    rsync -av --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' \
        --exclude='tests' --exclude='*.md' --exclude='spec' \
        "$PROJECT_ROOT/bees/" "$OPT_DIR/bees/"
    
    # Compile Python bytecode for faster startup
    python3 -m compileall -q "$OPT_DIR/bees" 2>/dev/null || true
    
    # -------------------------------------------------------------------------
    # Create bee wrapper script
    # -------------------------------------------------------------------------
    step "Criando wrapper 'bee' em /usr/bin..."
    cat > "$BIN_DIR/bee" << 'EOF'
#!/bin/bash
# ENXAME Bee - CLI wrapper for system installation

export PYTHONPATH="/opt/enxame-bee:${PYTHONPATH:-}"
export BEE_HOME="${BEE_HOME:-$HOME/.enxame/bee}"

# Ensure data directory exists
mkdir -p "$BEE_HOME"
mkdir -p "$BEE_HOME/documents"
mkdir -p "$BEE_HOME/zim"
mkdir -p "$BEE_HOME/lancedb"
mkdir -p "$BEE_HOME/cache"
mkdir -p "$BEE_HOME/logs"

exec python3 -m bees.cli "$@"
EOF
    chmod +x "$BIN_DIR/bee"
    
    # -------------------------------------------------------------------------
    # Create enxame-install-ollama helper
    # -------------------------------------------------------------------------
    cat > "$BIN_DIR/enxame-install-ollama" << 'EOF'
#!/bin/bash
# ENXAME Bee - Ollama installer for Debian/Ubuntu

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

main() {
    echo -e "${BLUE}==================================================${NC}"
    echo -e "${BLUE}  ENXAME Bee - Ollama Installer (Debian/Ubuntu)${NC}"
    echo -e "${BLUE}==================================================${NC}"
    echo
    
    if command -v ollama &> /dev/null; then
        log "Ollama ja instalado: $(ollama --version)"
        return 0
    fi
    
    # Install via official script
    log "Instalando Ollama via script oficial..."
    curl -fsSL https://ollama.com/install.sh | sh
    
    # Enable and start service
    log "Habilitando e iniciando servico systemd..."
    sudo systemctl daemon-reload
    sudo systemctl enable ollama
    sudo systemctl start ollama
    
    # Wait for service
    sleep 3
    
    if ollama list &> /dev/null; then
        log "Ollama instalado e rodando!"
    else
        error "Falha ao iniciar Ollama"
        return 1
    fi
}

main "$@"
EOF
    chmod +x "$BIN_DIR/enxame-install-ollama"
    
    # -------------------------------------------------------------------------
    # Create systemd service file
    # -------------------------------------------------------------------------
    step "Criando servico systemd..."
    cat > "$SYSTEMD_DIR/enxame-bee.service" << 'EOF'
[Unit]
Description=ENXAME Bee - Abelha Standalone
After=network-online.target ollama.service
Wants=network-online.target ollama.service
Documentation=https://github.com/enxame/enxamepublic

[Service]
Type=simple
User=%i
Group=%i
Environment=BEE_HOME=%h/.enxame/bee
Environment=PYTHONPATH=/opt/enxame-bee
ExecStart=/usr/bin/bee start
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=enxame-bee

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=%h/.enxame

[Install]
WantedBy=default.target
EOF
    
    # -------------------------------------------------------------------------
    # Create default config
    # -------------------------------------------------------------------------
    step "Criando configuracao padrao..."
    cat > "$ETC_DIR/enxame-bee/config.json.example" << 'EOF'
{
  "node_id": "",
  "host": "0.0.0.0",
  "port": 8765,
  "host_ip": "127.0.0.1",
  "ollama_base_url": "http://localhost:11434",
  "model": "llama3.2:3b",
  "data_dir": "~/.enxame/bee",
  "allow_web": false,
  "shared_secret": null,
  "log_level": "INFO",
  "confidence_threshold_enxame": 0.7,
  "confidence_threshold_web": 0.8,
  "heartbeat_interval": 5.0,
  "heartbeat_timeout": 15.0,
  "max_concurrent_queries": 4,
  "query_timeout_seconds": 60,
  "max_cache_items": 1000
}
EOF
    
    # -------------------------------------------------------------------------
    # Create DEBIAN/control file
    # -------------------------------------------------------------------------
    step "Criando DEBIAN/control..."
    cat > "$DEBIAN_DIR/control" << EOF
Package: $PACKAGE_NAME
Version: $VERSION
Architecture: $ARCHITECTURE
Maintainer: $MAINTAINER
Installed-Size: $(du -ks "$DEB_DIR" | cut -f1)
Depends: $DEPENDS
Recommends: $RECOMMENDS
Suggests: $SUGGESTS
Section: $SECTION
Priority: $PRIORITY
Homepage: $HOMEPAGE
Description: $DESCRIPTION
 ENXAME Bee e uma unidade autonoma do sistema Enxame que opera
 offline-first, descobre peers via mDNS, e segue a politica
 LOCAL -> ENXAME -> WEB para consultas de conhecimento.
 .
 Caracteristicas:
  * RAG local com LanceDB e embeddings
  * Descoberta automatica de peers via mDNS
  * Protocolo P2P seguro com HMAC
  * Memoria persistente (SQLite)
  * Suporte a OCR, ZIM, Web fallback
  * Selecao automatica de modelo por hardware
  * CLI completa: bee start, query, discover, status
EOF
    
    # -------------------------------------------------------------------------
    # Create DEBIAN/postinst
    # -------------------------------------------------------------------------
    step "Criando DEBIAN/postinst..."
    cat > "$DEBIAN_DIR/postinst" << 'EOF'
#!/bin/bash
# Post-installation script for enxame-bee

set -euo pipefail

log() { echo "[enxame-bee] $1"; }

case "$1" in
    configure)
        # Create enxame user if doesn't exist
        if ! id "enxame" &>/dev/null; then
            log "Criando usuario 'enxame'..."
            useradd --system --home-dir /var/lib/enxame --shell /bin/false enxame 2>/dev/null || true
        fi
        
        # Create data directories
        mkdir -p /var/lib/enxame/.enxame/bee
        mkdir -p /var/lib/enxame/.enxame/bee/documents
        mkdir -p /var/lib/enxame/.enxame/bee/zim
        mkdir -p /var/lib/enxame/.enxame/bee/lancedb
        mkdir -p /var/lib/enxame/.enxame/bee/cache
        mkdir -p /var/lib/enxame/.enxame/bee/logs
        
        chown -R enxame:enxame /var/lib/enxame 2>/dev/null || true
        
        # Install Python dependencies
        log "Instalando dependencias Python..."
        python3 -m pip install --upgrade pip setuptools wheel >/dev/null 2>&1
        python3 -m pip install httpx pydantic pydantic-settings psutil zeroconf cryptography rich pyyaml >/dev/null 2>&1
        
        # Install Ollama if not present
        if ! command -v ollama &> /dev/null; then
            log "Ollama nao encontrado. Instalando..."
            curl -fsSL https://ollama.com/install.sh | sh
        fi
        
        # Enable and start Ollama
        log "Habilitando servico Ollama..."
        systemctl daemon-reload
        systemctl enable ollama >/dev/null 2>&1 || true
        systemctl start ollama >/dev/null 2>&1 || true
        
        # Enable enxame-bee service (user instance)
        log "Habilitando servico enxame-bee..."
        systemctl daemon-reload
        
        # Run Bee installer for the first user
        if [ -n "$SUDO_USER" ]; then
            sudo -u "$SUDO_USER" bash -c "
                export BEE_HOME=\$HOME/.enxame/bee
                mkdir -p \$BEE_HOME/documents \$BEE_HOME/zim \$BEE_HOME/lancedb \$BEE_HOME/cache \$BEE_HOME/logs
                python3 -m bees.install.install_bee --skip-model-test || true
            " 2>/dev/null || true
        fi
        
        log "Instalacao concluida!"
        echo ""
        echo "Para iniciar a Abelha:"
        echo "  bee start"
        echo ""
        echo "Para iniciar como servico (requer sudo):"
        echo "  sudo systemctl enable --now enxame-bee@\$USER"
        echo ""
        echo "Para descobrir peers:"
        echo "  bee discover"
        echo ""
        echo "Para fazer uma query:"
        echo "  bee query \"Sua pergunta\""
        ;;
        
    abort-upgrade|abort-remove|abort-deconfigure)
        ;;
        
    *)
        echo "postinst called with unknown argument \`$1'" >&2
        exit 1
        ;;
esac

exit 0
EOF
    chmod +x "$DEBIAN_DIR/postinst"
    
    # -------------------------------------------------------------------------
    # Create DEBIAN/prerm
    # -------------------------------------------------------------------------
    step "Criando DEBIAN/prerm..."
    cat > "$DEBIAN_DIR/prerm" << 'EOF'
#!/bin/bash
# Pre-removal script for enxame-bee

set -euo pipefail

case "$1" in
    remove|upgrade|deconfigure)
        # Stop service if running
        if systemctl is-active --quiet enxame-bee@$SUDO_USER 2>/dev/null; then
            systemctl stop enxame-bee@$SUDO_USER 2>/dev/null || true
        fi
        
        # Disable service
        systemctl disable enxame-bee@$SUDO_USER 2>/dev/null || true
        ;;
        
    failed-upgrade)
        ;;
        
    *)
        echo "prerm called with unknown argument \`$1'" >&2
        exit 1
        ;;
esac

exit 0
EOF
    chmod +x "$DEBIAN_DIR/prerm"
    
    # -------------------------------------------------------------------------
    # Create DEBIAN/postrm
    # -------------------------------------------------------------------------
    step "Criando DEBIAN/postrm..."
    cat > "$DEBIAN_DIR/postrm" << 'EOF'
#!/bin/bash
# Post-removal script for enxame-bee

set -euo pipefail

case "$1" in
    purge)
        # Remove user data
        rm -rf /var/lib/enxame
        
        # Remove user if exists and no other processes
        if id "enxame" &>/dev/null; then
            userdel enxame 2>/dev/null || true
        fi
        ;;
        
    remove|upgrade|failed-upgrade|disappear|abort-install|abort-upgrade)
        ;;
        
    *)
        echo "postrm called with unknown argument \`$1'" >&2
        exit 1
        ;;
esac

# Reload systemd
systemctl daemon-reload >/dev/null 2>&1 || true

exit 0
EOF
    chmod +x "$DEBIAN_DIR/postrm"
    
    # -------------------------------------------------------------------------
    # Create DEBIAN/conffiles
    # -------------------------------------------------------------------------
    cat > "$DEBIAN_DIR/conffiles" << 'EOF'
/etc/enxame-bee/config.json.example
EOF
    
    # -------------------------------------------------------------------------
    # Create copyright file
    # -------------------------------------------------------------------------
    cat > "$DEBIAN_DIR/copyright" << 'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: enxame-bee
Source: https://github.com/enxame/enxamepublic

Files: *
Copyright: 2024 Enxame Project
License: MIT
 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:
 .
 The above copyright notice and this permission notice shall be included in all
 copies or substantial portions of the Software.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 SOFTWARE.
EOF
    
    # -------------------------------------------------------------------------
    # Build the .deb package
    # -------------------------------------------------------------------------
    step "Construindo pacote .deb..."
    
    # Calculate installed size
    INSTALLED_SIZE=$(du -ks "$DEB_DIR" | cut -f1)
    sed -i "s/Installed-Size: .*/Installed-Size: $INSTALLED_SIZE/" "$DEBIAN_DIR/control"
    
    # Build
    dpkg-deb --build "$DEB_DIR" "$OUTPUT_DIR/${PACKAGE_NAME}_${VERSION}-1_${ARCHITECTURE}.deb"
    
    step "Build concluido!"
    log "Pacote criado: $OUTPUT_DIR/${PACKAGE_NAME}_${VERSION}-1_${ARCHITECTURE}.deb"
    log "Tamanho: $(du -h "$OUTPUT_DIR/${PACKAGE_NAME}_${VERSION}-1_${ARCHITECTURE}.deb" | cut -f1)"
    
    # Verify package
    dpkg-deb --info "$OUTPUT_DIR/${PACKAGE_NAME}_${VERSION}-1_${ARCHITECTURE}.deb"
    dpkg-deb --contents "$OUTPUT_DIR/${PACKAGE_NAME}_${VERSION}-1_${ARCHITECTURE}.deb" | head -20
}

main "$@"