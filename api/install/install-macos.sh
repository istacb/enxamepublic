#!/bin/bash
# =============================================================================
# ENXAME - Instalador Oficial para macOS v1.0.0
# Fluxo: Next > Next > Finish (Totalmente Automático)
# =============================================================================
# Este script:
# 1. Detecta instalações antigas do Enxame ou OpenWebUI
# 2. Para serviços antigos
# 3. Faz backup dos dados do usuário
# 4. Remove completamente a instalação antiga
# 5. Instala a nova versão limpa
# 6. Restaura os dados
# =============================================================================

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Versão
ENXAME_VERSION="1.0.0"
INSTALL_DIR="/Applications/Enxame"
DATA_DIR="$HOME/Library/Application Support/Enxame"
LOG_DIR="$HOME/Library/Logs/Enxame"
CONFIG_DIR="$HOME/Library/Preferences/Enxame"
BACKUP_DIR="/tmp/enxame_backup_$(date +%Y%m%d_%H%M%S)"

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║         ENXAME v${ENXAME_VERSION} - Instalador macOS            ║"
echo "║              Next > Next > Finish                        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Verifica se é root (necessário para /Applications)
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Erro: Execute como root (sudo ./install-macos.sh)${NC}"
    exit 1
fi

echo -e "${YELLOW}>>> PASSO 1/7: Verificando requisitos do sistema...${NC}"

# Verifica requisitos
check_requirements() {
    local missing=()
    
    # Verifica Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python 3 não encontrado. Por favor, instale primeiro.${NC}"
        echo "Baixe em: https://www.python.org/downloads/macos/"
        exit 1
    else
        python3 --version
    fi
    
    # Verifica pip
    if ! command -v pip3 &> /dev/null; then
        missing+=("python3-pip")
    fi
    
    # Verifica Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${YELLOW}Node.js não encontrado. Instalando via Homebrew...${NC}"
        if ! command -v brew &> /dev/null; then
            echo "Homebrew não encontrado. Instalando..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        brew install node
    else
        node --version
    fi
    
    if [ ${#missing[@]} -ne 0 ]; then
        echo -e "${YELLOW}Instalando dependências: ${missing[*]}${NC}"
        # macOS geralmente já tem o necessário
    fi

    # Confirma que o módulo venv funciona (normalmente já vem com o
    # Python do macOS/Homebrew, mas confirmamos antes de depender dele).
    if ! python3 -m venv --help &> /dev/null; then
        echo -e "${YELLOW}Módulo venv do Python não encontrado.${NC}"
        if command -v brew &> /dev/null; then
            echo "Tentando reinstalar Python via Homebrew..."
            brew install python3 || true
        fi
    fi
    
    echo -e "${GREEN}✓ Requisitos verificados${NC}"
}

check_requirements

echo ""
echo -e "${YELLOW}>>> PASSO 2/7: Procurando instalações antigas...${NC}"

# Detecta instalações antigas
OLD_INSTALL_FOUND=false
OPENWEBUI_FOUND=false
ENXAME_OLD_FOUND=false

# Detecta OpenWebUI
if [ -d "$HOME/Library/Application Support/open-webui" ] || \
   [ -d "/Applications/open-webui" ] || \
   [ -f "$HOME/.open-webui.env" ] || \
   docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "open-webui"; then
    echo -e "${RED}✗ OpenWebUI detectado no sistema${NC}"
    OPENWEBUI_FOUND=true
    OLD_INSTALL_FOUND=true
fi

# Detecta Enxame antigo
if [ -d "$INSTALL_DIR" ] || [ -d "$DATA_DIR/data" ]; then
    echo -e "${YELLOW}! Instalação antiga do Enxame detectada${NC}"
    ENXAME_OLD_FOUND=true
    OLD_INSTALL_FOUND=true
fi

# Detecta processos rodando
if pgrep -f "enxame|open.webui|open_webui" > /dev/null; then
    echo -e "${YELLOW}! Processos antigos encontrados${NC}"
    OLD_INSTALL_FOUND=true
fi

if [ "$OLD_INSTALL_FOUND" = true ]; then
    echo ""
    echo -e "${YELLOW}>>> PASSO 3/7: Removendo instalação antiga...${NC}"
    
    # Para processos
    echo "Parando processos antigos..."
    pkill -f "enxame" 2>/dev/null || true
    pkill -f "open.webui" 2>/dev/null || true
    pkill -f "open_webui" 2>/dev/null || true
    
    # Para containers Docker se existirem
    if command -v docker &> /dev/null; then
        docker stop open-webui 2>/dev/null || true
        docker rm open-webui 2>/dev/null || true
    fi
    
    # Backup dos dados
    echo "Criando backup dos dados do usuário..."
    mkdir -p "$BACKUP_DIR"
    
    if [ -d "$DATA_DIR/data" ]; then
        cp -r "$DATA_DIR/data" "$BACKUP_DIR/" 2>/dev/null || true
        echo "  ✓ Dados backupados"
    fi
    
    if [ -f "$CONFIG_DIR/.env" ]; then
        cp "$CONFIG_DIR/.env" "$BACKUP_DIR/" 2>/dev/null || true
        echo "  ✓ Configurações backupadas"
    fi
    
    # Remove instalação antiga
    echo "Removendo arquivos antigos..."
    rm -rf "$INSTALL_DIR" 2>/dev/null || true
    rm -rf "$DATA_DIR" 2>/dev/null || true
    rm -rf "$LOG_DIR" 2>/dev/null || true
    rm -rf "$CONFIG_DIR" 2>/dev/null || true
    
    # Remove OpenWebUI se existir
    if [ "$OPENWEBUI_FOUND" = true ]; then
        echo "Removendo OpenWebUI..."
        rm -rf "$HOME/Library/Application Support/open-webui" 2>/dev/null || true
        rm -rf "/Applications/open-webui" 2>/dev/null || true
        rm -f "$HOME/.open-webui.env" 2>/dev/null || true
        
        # Remove containers e imagens
        if command -v docker &> /dev/null; then
            docker stop open-webui 2>/dev/null || true
            docker rm open-webui 2>/dev/null || true
            docker rmi ghcr.io/open-webui/open-webui:main 2>/dev/null || true
        fi
    fi
    
    echo -e "${GREEN}✓ Instalação antiga removida${NC}"
else
    echo -e "${GREEN}✓ Nenhuma instalação antiga encontrada${NC}"
fi

echo ""
echo -e "${YELLOW}>>> PASSO 4/7: Instalando novo Enxame...${NC}"

# Cria diretórios
mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR/data"
mkdir -p "$LOG_DIR"
mkdir -p "$CONFIG_DIR"

# Copia arquivos. O instalador é distribuído junto com o repositório
# (fica em api/install/ dentro do próprio checkout), então nunca é
# necessário clonar nada aqui — e como o repositório é público, clonar
# nunca pediria usuário/senha de qualquer forma.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [ ! -d "$REPO_ROOT/juiz" ] || [ ! -d "$REPO_ROOT/bibliotecario" ]; then
    echo -e "${RED}Erro: não encontrei o repositório do Enxame a partir de $SCRIPT_DIR.${NC}"
    echo -e "${RED}Execute este script de dentro do checkout do repositório (api/install/install-macos.sh).${NC}"
    exit 1
fi
cp -r "$REPO_ROOT"/* "$INSTALL_DIR/"
echo "  ✓ Arquivos copiados de $REPO_ROOT"

cd "$INSTALL_DIR"

# Instala dependências Python em um venv isolado (evita o erro
# "externally-managed-environment" do PEP 668, presente também no Python
# 3.12+ instalado via Homebrew/python.org no macOS).
echo "Criando ambiente virtual Python em $INSTALL_DIR/.venv..."
python3 -m venv "$INSTALL_DIR/.venv"
VENV_PIP="$INSTALL_DIR/.venv/bin/pip"
"$VENV_PIP" install --quiet --upgrade pip

echo "Instalando dependências Python..."
if [ -f "requirements.txt" ]; then
    "$VENV_PIP" install -r requirements.txt --quiet --upgrade
elif [ -d "kernel" ] && [ -f "kernel/requirements.txt" ]; then
    "$VENV_PIP" install -r kernel/requirements.txt --quiet --upgrade
fi
echo "  ✓ Dependências Python instaladas em $INSTALL_DIR/.venv"

# Instala dependências Node se necessário
if [ -f "package.json" ]; then
    echo "Instalando dependências Node.js..."
    npm install --production --silent
    echo "  ✓ Dependências Node.js instaladas"
fi

echo -e "${GREEN}✓ Enxame instalado em $INSTALL_DIR${NC}"

echo ""
echo -e "${YELLOW}>>> PASSO 5/7: Restaurando dados e configurando...${NC}"

# Restaura backup
if [ -d "$BACKUP_DIR/data" ]; then
    cp -r "$BACKUP_DIR/data"/* "$DATA_DIR/" 2>/dev/null || true
    echo "  ✓ Dados restaurados"
fi

if [ -f "$BACKUP_DIR/.env" ]; then
    cp "$BACKUP_DIR/.env" "$CONFIG_DIR/.env"
    echo "  ✓ Configurações restauradas"
else
    # Cria .env padrão
    cat > "$CONFIG_DIR/.env" << EOF
# Enxame Configuration
ENXAME_ENV=production
ENXAME_HOST=0.0.0.0
ENXAME_DATA_PATH=$DATA_DIR/data
ENXAME_LOG_PATH=$LOG_DIR
OLLAMA_URL=http://localhost:11434
# ENXAME_NODE_ROLE, ENXAME_NODE_ID e ENXAME_NODE_PORT são preenchidos
# automaticamente pelo passo de configuração de função do node (mais abaixo).
EOF
    echo "  ✓ Configuração padrão criada"
fi

# Configura permissões
chown -R $(whoami):staff "$INSTALL_DIR"
chown -R $(whoami):staff "$DATA_DIR"
chown -R $(whoami):staff "$LOG_DIR"
chown -R $(whoami):staff "$CONFIG_DIR"
chmod 755 "$INSTALL_DIR"
chmod 644 "$CONFIG_DIR/.env"

echo -e "${GREEN}✓ Configuração concluída${NC}"

echo ""
echo -e "${YELLOW}>>> PASSO 6/7: Criando atalhos e serviço...${NC}"

# Cria script de inicialização (usa o Python do venv isolado criado acima)
cat > "$INSTALL_DIR/run.sh" << EOF
#!/bin/bash
cd "$INSTALL_DIR"
exec "$INSTALL_DIR/.venv/bin/python3" "$INSTALL_DIR/api/install/run_node.py" --env-file "$CONFIG_DIR/.env" "\$@"
EOF
chmod +x "$INSTALL_DIR/run.sh"

# Cria atalho no Dock (opcional)
# Cria um .app simples
APP_DIR="$INSTALL_DIR/Enxame.app"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

cat > "$APP_DIR/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>run.sh</string>
    <key>CFBundleIdentifier</key>
    <string>com.enxame.app</string>
    <key>CFBundleName</key>
    <string>Enxame</string>
    <key>CFBundleVersion</key>
    <string>${ENXAME_VERSION}</string>
</dict>
</plist>
EOF

cp "$INSTALL_DIR/run.sh" "$APP_DIR/Contents/MacOS/"

# Cria LaunchAgent para iniciar automaticamente
LAUNCHAGENT_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCHAGENT_DIR"

cat > "$LAUNCHAGENT_DIR/com.enxame.app.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.enxame.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/run.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/enxame.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/enxame.err</string>
</dict>
</plist>
EOF

echo -e "${GREEN}✓ Atalhos e LaunchAgent criados${NC}"

echo ""
echo -e "${YELLOW}>>> PASSO 7/7: Configurando função do node...${NC}"
echo ""

# Pergunta a função inicial do node (só pergunta de fato se o .env restaurado
# ainda não tiver uma função salva de uma instalação anterior), faz a
# varredura mDNS por outros nodes na rede e, na primeira instalação, exibe
# a confirmação de qual função cada node assumiu.
python3 "$INSTALL_DIR/api/install/node_role_setup.py" --env-file "$CONFIG_DIR/.env"

# Só agora carrega o LaunchAgent, já com a função definida no .env
launchctl unload "$LAUNCHAGENT_DIR/com.enxame.app.plist" 2>/dev/null || true
launchctl load "$LAUNCHAGENT_DIR/com.enxame.app.plist"

# Limpa backup
rm -rf "$BACKUP_DIR"

echo -e "${GREEN}✓ Serviço criado e iniciado${NC}"

echo ""
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║              INSTALAÇÃO CONCLUÍDA!                       ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Enxame v${ENXAME_VERSION} instalado com sucesso                ║"
echo "║                                                          ║"
echo "║  Localização: $INSTALL_DIR"
echo "║  Dados: $DATA_DIR"
echo "║  Config: $CONFIG_DIR"
echo "║                                                          ║"
echo "║  Comandos úteis:                                         ║"
echo "║    • $INSTALL_DIR/run.sh      - Iniciar Enxame          ║"
echo "║    • Enxame.app              - Abrir aplicativo         ║"
echo "║                                                          ║"
echo "║  Função e porta deste node: ver $CONFIG_DIR/.env"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

exit 0
