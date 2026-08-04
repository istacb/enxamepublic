#!/bin/bash
# =============================================================================
# ENXAME - Instalador Oficial para macOS
# Fluxo: Next > Next > Finish (Totalmente Automático)
# =============================================================================
# Este script:
# 1. Varre a rede em busca de instâncias do Enxame
# 2. Detecta instalações antigas do Enxame ou OpenWebUI
# 3. Para serviços antigos e remove completamente
# 4. Faz backup dos dados do usuário
# 5. Instala a nova versão usando o repositório local
# 6. Restaura os dados e configura
# 7. Pergunta a função inicial do node (apenas na primeira instalação)
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
FIRST_INSTALL_FLAG="$DATA_DIR/.first_install"

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

echo -e "${YELLOW}>>> PASSO 1/7: Varrendo rede por instâncias do Enxame...${NC}"

# Varre a rede em busca de nós do Enxame
scan_enxame_nodes() {
    local nodes_found=0
    
    echo "Procurando nós do Enxame na rede local..."
    
    # Tenta comunicação HTTP com portas conhecidas
    for port in 8080 7700 8081 8082; do
        if curl -s --max-time 2 http://localhost:$port/api/health > /dev/null 2>&1; then
            echo -e "  ${GREEN}✓${NC} Nó respondendo em localhost:$port"
            nodes_found=$((nodes_found + 1))
            
            # Notifica shutdown gracioso
            curl -s --max-time 2 -X POST http://localhost:$port/api/system/shutdown \
                -H "Content-Type: application/json" \
                -d '{"reason": "install", "graceful": true}' > /dev/null 2>&1 || true
        fi
    done
    
    # Verifica Ollama
    if curl -s --max-time 2 http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Ollama respondendo em localhost:11434"
        nodes_found=$((nodes_found + 1))
    fi
    
    if [ $nodes_found -eq 0 ]; then
        echo -e "  ${YELLOW}!${NC} Nenhum nó ativo encontrado"
    else
        echo "  Total: $nodes_found nó(s) encontrados"
        echo "Notificando nós para shutdown gracioso..."
        sleep 2
    fi
}

scan_enxame_nodes

echo -e "${YELLOW}>>> PASSO 2/7: Verificando requisitos do sistema...${NC}"

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
    
    echo -e "${GREEN}✓ Requisitos verificados${NC}"
}

check_requirements

echo ""
echo -e "${YELLOW}>>> PASSO 3/7: Procurando instalações antigas...${NC}"

# Detecta instalações antigas
OLD_INSTALL_FOUND=false
OPENWEBUI_FOUND=false
ENXAME_OLD_FOUND=false
IS_FIRST_INSTALL=true

# Detecta OpenWebUI
if [ -d "$HOME/Library/Application Support/open-webui" ] || \
   [ -d "/Applications/open-webui" ] || \
   [ -f "$HOME/.open-webui.env" ] || \
   docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "open-webui"; then
    echo -e "${RED}✗ OpenWebUI detectado no sistema${NC}"
    OPENWEBUI_FOUND=true
    OLD_INSTALL_FOUND=true
    IS_FIRST_INSTALL=false
fi

# Detecta Enxame antigo
if [ -d "$INSTALL_DIR" ] || [ -d "$DATA_DIR/data" ]; then
    echo -e "${YELLOW}! Instalação antiga do Enxame detectada${NC}"
    ENXAME_OLD_FOUND=true
    OLD_INSTALL_FOUND=true
    IS_FIRST_INSTALL=false
fi

# Verifica se é primeira instalação
if [ -f "$FIRST_INSTALL_FLAG" ]; then
    IS_FIRST_INSTALL=false
fi

# Detecta processos rodando
if pgrep -f "enxame|open.webui|open_webui" > /dev/null; then
    echo -e "${YELLOW}! Processos antigos encontrados${NC}"
    OLD_INSTALL_FOUND=true
fi

if [ "$OLD_INSTALL_FOUND" = true ]; then
    echo ""
    echo -e "${YELLOW}>>> PASSO 4/7: Removendo instalação antiga...${NC}"
    
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
echo -e "${YELLOW}>>> PASSO 5/7: Instalando novo Enxame...${NC}"

# Cria diretórios
mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR/data"
mkdir -p "$LOG_DIR"
mkdir -p "$CONFIG_DIR"

# Copia arquivos do repositório local (não precisa clonar novamente)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "Copiando arquivos do repositório local em $REPO_ROOT..."
if [ -d "$REPO_ROOT/kernel" ] || [ -d "$REPO_ROOT/core" ]; then
    cp -r "$REPO_ROOT"/* "$INSTALL_DIR/"
    echo "  ✓ Arquivos copiados do repositório local"
else
    echo -e "${RED}Erro: Repositório não encontrado em $REPO_ROOT${NC}"
    echo "Certifique-se de que o instalador está dentro do repositório do Enxame."
    exit 1
fi

cd "$INSTALL_DIR"

# Instala dependências Python
echo "Instalando dependências Python..."
if [ -f "agentes/requirements.txt" ]; then
    pip3 install -r agentes/requirements.txt --quiet --upgrade
elif [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt --quiet --upgrade
elif [ -d "kernel" ] && [ -f "kernel/requirements.txt" ]; then
    pip3 install -r kernel/requirements.txt --quiet --upgrade
fi
echo "  ✓ Dependências Python instaladas"

# Instala dependências Node se necessário
if [ -f "package.json" ]; then
    echo "Instalando dependências Node.js..."
    npm install --production --silent
    echo "  ✓ Dependências Node.js instaladas"
fi

echo -e "${GREEN}✓ Enxame instalado em $INSTALL_DIR${NC}"

echo ""
echo -e "${YELLOW}>>> PASSO 6/7: Restaurando dados e configurando...${NC}"

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
ENXAME_PORT=8080
ENXAME_HOST=0.0.0.0
ENXAME_DATA_PATH=$HOME/Library/Application Support/Enxame/data
ENXAME_LOG_PATH=$HOME/Library/Logs/Enxame
OLLAMA_URL=http://localhost:11434
EXP_SHARED_SECRET=enxame-secret-$(openssl rand -hex 16)
EOF
    echo "  ✓ Configuração padrão criada"
fi

# Marca como não sendo mais primeira instalação
if [ "$IS_FIRST_INSTALL" = true ]; then
    touch "$FIRST_INSTALL_FLAG"
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
echo -e "${YELLOW}>>> PASSO 7/7: Criando atalhos e serviço...${NC}"

# Cria script de inicialização
cat > "$INSTALL_DIR/run.sh" << EOF
#!/bin/bash
cd "$INSTALL_DIR"
exec python3 -m kernel.start "\$@"
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

# Carrega o LaunchAgent
launchctl unload "$LAUNCHAGENT_DIR/com.enxame.app.plist" 2>/dev/null || true
launchctl load "$LAUNCHAGENT_DIR/com.enxame.app.plist"

# Limpa backup
rm -rf "$BACKUP_DIR"

echo -e "${GREEN}✓ Serviço criado e iniciado${NC}"

# Pergunta sobre função inicial do node (apenas na primeira instalação)
if [ "$IS_FIRST_INSTALL" = true ]; then
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║         CONFIGURAÇÃO INICIAL DO NODE                     ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Qual será a função inicial deste node no enxame?"
    echo ""
    echo "  1) Kernel (Orquestrador principal)"
    echo "  2) Juiz (Distribuidor de tarefas)"
    echo "  3) Bibliotecário (Gerenciamento de documentos)"
    echo "  4) Agente (Executor de tarefas)"
    echo "  5) Worker (Processamento distribuído)"
    echo ""
    read -p "Escolha uma opção [1-5] (padrão: 1): " node_role
    node_role=${node_role:-1}
    
    case $node_role in
        1)
            ROLE_NAME="kernel"
            ENXAME_PORT="8080"
            echo "Configurando node como KERNEL..."
            ;;
        2)
            ROLE_NAME="juiz"
            ENXAME_PORT="8082"
            echo "Configurando node como JUIZ..."
            ;;
        3)
            ROLE_NAME="bibliotecario"
            ENXAME_PORT="8081"
            echo "Configurando node como BIBLIOTECÁRIO..."
            ;;
        4)
            ROLE_NAME="agente"
            ENXAME_PORT="8083"
            echo "Configurando node como AGENTE..."
            ;;
        5)
            ROLE_NAME="worker"
            ENXAME_PORT="8084"
            echo "Configurando node como WORKER..."
            ;;
        *)
            ROLE_NAME="kernel"
            ENXAME_PORT="8080"
            echo "Opção inválida. Configurando como KERNEL por padrão..."
            ;;
    esac
    
    # Atualiza configuração com a função
    echo "ENXAME_NODE_ROLE=$ROLE_NAME" >> "$CONFIG_DIR/.env"
    NODE_ID="node-$(hostname)-$(date +%s)"
    echo "ENXAME_NODE_ID=$NODE_ID" >> "$CONFIG_DIR/.env"
    echo "ENXAME_PORT=$ENXAME_PORT" >> "$CONFIG_DIR/.env"
    
    echo ""
    echo -e "${GREEN}✓ Função do node configurada: $ROLE_NAME${NC}"
    echo -e "${GREEN}✓ Porta configurada: $ENXAME_PORT${NC}"
    
    # Descobre e registra node no cluster
    echo ""
    echo -e "${YELLOW}>>> Descobrindo cluster e registrando node...${NC}"
    if command -v python3 &> /dev/null; then
        python3 "$SCRIPT_DIR/discover_nodes.py" discover 2>/dev/null || true
        python3 "$SCRIPT_DIR/discover_nodes.py" advertise "$NODE_ID" "$ROLE_NAME" "$ENXAME_PORT" 2>/dev/null || true
        python3 "$SCRIPT_DIR/discover_nodes.py" confirm "$NODE_ID" "$ROLE_NAME" 2>/dev/null || true
        
        echo ""
        echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
        echo -e "${BLUE}  FUNÇÃO ASSUMIDA: $ROLE_NAME${NC}"
        echo -e "${BLUE}  NODE ID: $NODE_ID${NC}"
        echo -e "${BLUE}  STATUS: Ativo e descoberto na rede${NC}"
        echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
    fi
fi

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
echo "║  Acesse: http://localhost:8080                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

exit 0
