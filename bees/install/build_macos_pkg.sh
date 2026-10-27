#!/bin/bash
# =============================================================================
# ENXAME Bee - macOS Package Builder
# Creates a .pkg installer for macOS
# =============================================================================

set -euo pipefail

# Configuration
APP_NAME="ENXAME Bee"
VERSION="1.0.0"
BUNDLE_ID="com.enxame.bee"
INSTALL_DIR="/usr/local/bin"
DATA_DIR="$HOME/.enxame/bee"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$SCRIPT_DIR/build_macos"
PAYLOAD_DIR="$BUILD_DIR/payload"
SCRIPTS_DIR="$BUILD_DIR/scripts"
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

# Cleanup function
cleanup() {
    log "Limpando build anterior..."
    rm -rf "$BUILD_DIR"
}
trap cleanup EXIT

# =============================================================================
# Main build process
# =============================================================================
main() {
    step "Iniciando build do macOS pkg para $APP_NAME v$VERSION"
    
    # Create build directories
    mkdir -p "$PAYLOAD_DIR$INSTALL_DIR"
    mkdir -p "$PAYLOAD_DIR/Library/LaunchDaemons"
    mkdir -p "$SCRIPTS_DIR"
    
    # -------------------------------------------------------------------------
    # Copy Python package
    # -------------------------------------------------------------------------
    step "Copiando pacote Python..."
    rsync -av --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' \
        "$PROJECT_ROOT/bees/" "$PAYLOAD_DIR/usr/local/lib/enxame/bees/"
    
    # -------------------------------------------------------------------------
    # Create bee wrapper script
    # -------------------------------------------------------------------------
    step "Criando wrapper 'bee'..."
    cat > "$PAYLOAD_DIR$INSTALL_DIR/bee" << 'EOF'
#!/bin/bash
# ENXAME Bee - CLI wrapper
export PYTHONPATH="/usr/local/lib/enxame:${PYTHONPATH:-}"
exec python3 -m bees.cli "$@"
EOF
    chmod +x "$PAYLOAD_DIR$INSTALL_DIR/bee"
    
    # -------------------------------------------------------------------------
    # Create Ollama installer script
    # -------------------------------------------------------------------------
    step "Criando script de instalacao do Ollama..."
    cat > "$PAYLOAD_DIR$INSTALL_DIR/enxame-install-ollama" << 'EOF'
#!/bin/bash
# ENXAME Bee - Ollama installer for macOS

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
    echo -e "${BLUE}  ENXAME Bee - Ollama Installer (macOS)${NC}"
    echo -e "${BLUE}==================================================${NC}"
    echo
    
    # Check if Ollama is already installed
    if command -v ollama &> /dev/null; then
        log "Ollama ja instalado: $(ollama --version)"
        return 0
    fi
    
    # Check for Homebrew
    if command -v brew &> /dev/null; then
        log "Instalando Ollama via Homebrew..."
        brew install ollama
    else
        warn "Homebrew nao encontrado. Baixando installer oficial..."
        
        # Download and run official installer
        curl -fsSL https://ollama.com/install.sh | sh
    fi
    
    # Start Ollama service
    log "Iniciando servico Ollama..."
    if [[ -f "/Library/LaunchDaemons/com.ollama.ollama.plist" ]]; then
        sudo launchctl load -w /Library/LaunchDaemons/com.ollama.ollama.plist
    else
        # Start in background
        ollama serve &
        sleep 3
    fi
    
    # Verify
    sleep 2
    if ollama list &> /dev/null; then
        log "Ollama instalado e rodando com sucesso!"
    else
        error "Falha ao iniciar Ollama"
        return 1
    fi
}

main "$@"
EOF
    chmod +x "$PAYLOAD_DIR$INSTALL_DIR/enxame-install-ollama"
    
    # -------------------------------------------------------------------------
    # Create post-install script
    # -------------------------------------------------------------------------
    step "Criando script post-install..."
    cat > "$SCRIPTS_DIR/postinstall" << 'EOF'
#!/bin/bash
# Post-install script for ENXAME Bee pkg

set -euo pipefail

log() { echo "[ENXAME POST-INSTALL] $1"; }

# Create data directory
mkdir -p "$HOME/.enxame/bee"
mkdir -p "$HOME/.enxame/bee/documents"
mkdir -p "$HOME/.enxame/bee/zim"
mkdir -p "$HOME/.enxame/bee/lancedb"
mkdir -p "$HOME/.enxame/bee/cache"
mkdir -p "$HOME/.enxame/bee/logs"

# Install Python dependencies
log "Instalando dependencias Python..."
python3 -m pip install --upgrade pip setuptools wheel >/dev/null 2>&1
python3 -m pip install httpx pydantic pydantic-settings psutil zeroconf cryptography rich pyyaml >/dev/null 2>&1

# Install Ollama if not present
if ! command -v ollama &> /dev/null; then
    log "Ollama nao encontrado. Instalando..."
    if command -v brew &> /dev/null; then
        brew install ollama
    else
        curl -fsSL https://ollama.com/install.sh | sh
    fi
fi

# Start Ollama service
log "Iniciando servico Ollama..."
if [[ -f "/Library/LaunchDaemons/com.ollama.ollama.plist" ]]; then
    launchctl load -w /Library/LaunchDaemons/com.ollama.ollama.plist 2>/dev/null || true
else
    # Start in background
    nohup ollama serve >/dev/null 2>&1 &
    sleep 3
fi

# Run Bee installer
log "Executando instalador da Abelha..."
cd /usr/local/lib/enxame
python3 -m bees.install.install_bee --skip-model-test || true

# Set permissions
chown -R "$USER:staff" "$HOME/.enxame" 2>/dev/null || true

log "Instalacao concluida!"
echo ""
echo "Para iniciar a Abelha:"
echo "  bee start"
echo ""
echo "Para descobrir peers:"
echo "  bee discover"
echo ""
echo "Para fazer uma query:"
echo "  bee query \"Sua pergunta\""

exit 0
EOF
    chmod +x "$SCRIPTS_DIR/postinstall"
    
    # -------------------------------------------------------------------------
    # Create pre-install script
    # -------------------------------------------------------------------------
    step "Criando script pre-install..."
    cat > "$SCRIPTS_DIR/preinstall" << 'EOF'
#!/bin/bash
# Pre-install script for ENXAME Bee pkg

set -euo pipefail

# Stop any running bee processes
pkill -f "bees.service" 2>/dev/null || true
pkill -f "bee start" 2>/dev/null || true

exit 0
EOF
    chmod +x "$SCRIPTS_DIR/preinstall"
    
    # -------------------------------------------------------------------------
    # Build the package
    # -------------------------------------------------------------------------
    step "Construindo pacote .pkg..."
    mkdir -p "$OUTPUT_DIR"
    
    pkgbuild \
        --root "$PAYLOAD_DIR" \
        --scripts "$SCRIPTS_DIR" \
        --identifier "$BUNDLE_ID" \
        --version "$VERSION" \
        --install-location "/" \
        --ownership recommended \
        "$OUTPUT_DIR/enxame-bee-${VERSION}.pkg"
    
    # -------------------------------------------------------------------------
    # Create distribution XML for productbuild (optional, for better UI)
    # -------------------------------------------------------------------------
    cat > "$BUILD_DIR/distribution.xml" << EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>$APP_NAME</title>
    <organization>$BUNDLE_ID</organization>
    <domains enable_anywhere="true" enable_currentUserHome="true" enable_localSystem="true"/>
    <options customize="never" require-scripts="false" rootVolumeOnly="false"/>
    <welcome file="welcome.html" mime-type="text/html"/>
    <license file="license.html" mime-type="text/html"/>
    <conclusion file="conclusion.html" mime-type="text/html"/>
    
    <pkg-ref id="$BUNDLE_ID">enxame-bee-${VERSION}.pkg</pkg-ref>
    
    <choices-outline>
        <line choice="default">
            <line choice="bee"/>
            <line choice="ollama"/>
        </line>
    </choices-outline>
    
    <choice id="default" title="$APP_NAME" description="Instalacao completa do ENXAME Bee">
        <pkg-ref id="$BUNDLE_ID"/>
    </choice>
    
    <choice id="bee" title="ENXAME Bee Core" description="Abelha standalone, CLI e bibliotecas" start_selected="true" start_enabled="true" start_visible="true"/>
    
    <choice id="ollama" title="Ollama (recomendado)" description="Runtime de modelos locais para inferencia" start_selected="true" start_enabled="true" start_visible="true"/>
</installer-gui-script>
EOF
    
    # Create welcome/license/conclusion HTML
    cat > "$BUILD_DIR/welcome.html" << 'EOF'
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>body{font-family:-apple-system,sans-serif;padding:20px;line-height:1.6}</style></head>
<body>
<h1>Bem-vindo ao ENXAME Bee</h1>
<p>Este instalador configurara:</p>
<ul>
<li>Abelha ENXAME (standalone, offline-first)</li>
<li>CLI <code>bee</code> para gerenciamento</li>
<li>Ollama para inferencia local (opcional)</li>
</ul>
<p>O instalador precisa de acesso a internet para baixar modelos.</p>
</body>
</html>
EOF
    
    cat > "$BUILD_DIR/license.html" << 'EOF'
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>body{font-family:-apple-system,sans-serif;padding:20px;line-height:1.6}</style></head>
<body>
<h1>Licenca MIT</h1>
<p>Copyright (c) 2024 Enxame Project</p>
<p>Permission is hereby granted, free of charge, to any person obtaining a copy of this software...</p>
</body>
</html>
EOF
    
    cat > "$BUILD_DIR/conclusion.html" << 'EOF'
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>body{font-family:-apple-system,sans-serif;padding:20px;line-height:1.6}</style></head>
<body>
<h1>Instalacao Concluida!</h1>
<p>ENXAME Bee foi instalado com sucesso.</p>
<p>Para comecar:</p>
<ol>
<li>Abra o Terminal</li>
<li>Execute: <code>bee status</code></li>
<li>Inicie a Abelha: <code>bee start</code></li>
<li>Descubra peers: <code>bee discover</code></li>
<li>Faca uma query: <code>bee query "Sua pergunta"</code></li>
</ol>
<p>Documentacao: <a href="https://github.com/enxame/enxamepublic">github.com/enxame/enxamepublic</a></p>
</body>
</html>
EOF
    
    # Build product archive (optional, for better UI)
    if command -v productbuild &> /dev/null; then
        step "Criando product archive com UI personalizada..."
        productbuild \
            --distribution "$BUILD_DIR/distribution.xml" \
            --resources "$BUILD_DIR" \
            --package-path "$OUTPUT_DIR" \
            "$OUTPUT_DIR/enxame-bee-${VERSION}-installer.pkg" 2>/dev/null || \
        cp "$OUTPUT_DIR/enxame-bee-${VERSION}.pkg" "$OUTPUT_DIR/enxame-bee-${VERSION}-installer.pkg"
    else
        cp "$OUTPUT_DIR/enxame-bee-${VERSION}.pkg" "$OUTPUT_DIR/enxame-bee-${VERSION}-installer.pkg"
    fi
    
    step "Build concluido!"
    log "Pacote criado: $OUTPUT_DIR/enxame-bee-${VERSION}-installer.pkg"
    log "Tamanho: $(du -h "$OUTPUT_DIR/enxame-bee-${VERSION}-installer.pkg" | cut -f1)"
}

main "$@"