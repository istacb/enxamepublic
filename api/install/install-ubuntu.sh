#!/bin/bash
# =============================================================================
# ENXAME - Instalador Oficial para Ubuntu/Debian Linux
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
INSTALL_DIR="/opt/enxame"
DATA_DIR="/var/lib/enxame"
LOG_DIR="/var/log/enxame"
CONFIG_DIR="/etc/enxame"
BACKUP_DIR="/tmp/enxame_backup_$(date +%Y%m%d_%H%M%S)"

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║         ENXAME v${ENXAME_VERSION} - Instalador Ubuntu           ║"
echo "║              Next > Next > Finish                        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Verifica se é root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Erro: Execute como root (sudo ./install-ubuntu.sh)${NC}"
    exit 1
fi

echo -e "${YELLOW}>>> PASSO 1/6: Verificando requisitos do sistema...${NC}"

# Verifica requisitos
check_requirements() {
    local missing=()
    
    if ! command -v python3 &> /dev/null; then
        missing+=("python3")
    fi
    
    if ! command -v pip3 &> /dev/null; then
        missing+=("python3-pip")
    fi
    
    if ! command -v node &> /dev/null; then
        echo -e "${YELLOW}Node.js não encontrado. Instalando...${NC}"
        apt-get update -qq
        apt-get install -y -qq nodejs npm
    fi
    
    if [ ${#missing[@]} -ne 0 ]; then
        echo -e "${YELLOW}Instalando dependências: ${missing[*]}${NC}"
        apt-get update -qq
        apt-get install -y -qq "${missing[@]}"
    fi
    
    echo -e "${GREEN}✓ Requisitos verificados${NC}"
}

check_requirements

echo ""
echo -e "${YELLOW}>>> PASSO 2/6: Procurando instalações antigas...${NC}"

# Detecta instalações antigas
OLD_INSTALL_FOUND=false
OPENWEBUI_FOUND=false
ENXAME_OLD_FOUND=false

# Detecta OpenWebUI
if [ -d "/var/lib/open-webui" ] || [ -d "/opt/open-webui" ] || \
   [ -f "/etc/open-webui.env" ] || [ -f "/etc/systemd/system/open-webui.service" ] || \
   docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "open-webui"; then
    echo -e "${RED}✗ OpenWebUI detectado no sistema${NC}"
    OPENWEBUI_FOUND=true
    OLD_INSTALL_FOUND=true
fi

# Detecta Enxame antigo
if [ -d "$INSTALL_DIR" ] || [ -f "/etc/systemd/system/enxame.service" ] || \
   [ -d "$DATA_DIR/data" ]; then
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
    echo -e "${YELLOW}>>> PASSO 3/6: Removendo instalação antiga...${NC}"
    
    # Para serviços
    echo "Parando serviços antigos..."
    systemctl stop enxame 2>/dev/null || true
    systemctl disable enxame 2>/dev/null || true
    systemctl stop open-webui 2>/dev/null || true
    systemctl disable open-webui 2>/dev/null || true
    
    # Para containers Docker se existirem
    if command -v docker &> /dev/null; then
        docker stop open-webui 2>/dev/null || true
        docker rm open-webui 2>/dev/null || true
    fi
    
    # Mata processos
    pkill -f "enxame" 2>/dev/null || true
    pkill -f "open.webui" 2>/dev/null || true
    pkill -f "open_webui" 2>/dev/null || true
    
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
    rm -f /etc/systemd/system/enxame.service 2>/dev/null || true
    rm -f /etc/systemd/system/open-webui.service 2>/dev/null || true
    
    # Remove OpenWebUI se existir
    if [ "$OPENWEBUI_FOUND" = true ]; then
        echo "Removendo OpenWebUI..."
        rm -rf /var/lib/open-webui 2>/dev/null || true
        rm -rf /opt/open-webui 2>/dev/null || true
        rm -f /etc/open-webui.env 2>/dev/null || true
        
        # Remove containers e imagens
        if command -v docker &> /dev/null; then
            docker stop open-webui 2>/dev/null || true
            docker rm open-webui 2>/dev/null || true
            docker rmi ghcr.io/open-webui/open-webui:main 2>/dev/null || true
        fi
    fi
    
    systemctl daemon-reload
    
    echo -e "${GREEN}✓ Instalação antiga removida${NC}"
else
    echo -e "${GREEN}✓ Nenhuma instalação antiga encontrada${NC}"
fi

echo ""
echo -e "${YELLOW}>>> PASSO 4/6: Instalando novo Enxame...${NC}"

# Cria diretórios
mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR/data"
mkdir -p "$LOG_DIR"
mkdir -p "$CONFIG_DIR"

# Copia arquivos (assumindo que o script está no repositório)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$SCRIPT_DIR/kernel" ]; then
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
    echo "  ✓ Arquivos copiados"
else
    # Se estiver rodando de um download, baixa do repositório
    echo "Baixando Enxame do repositório oficial..."
    cd /tmp
    git clone --depth 1 https://github.com/enxame/enxame.git enxame_temp
    cp -r enxame_temp/* "$INSTALL_DIR/"
    rm -rf enxame_temp
    echo "  ✓ Arquivos baixados"
fi

cd "$INSTALL_DIR"

# Instala dependências Python
echo "Instalando dependências Python..."
if [ -f "requirements.txt" ]; then
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
echo -e "${YELLOW}>>> PASSO 5/6: Restaurando dados e configurando...${NC}"

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
    cat > "$CONFIG_DIR/.env" << 'EOF'
# Enxame Configuration
ENXAME_ENV=production
ENXAME_PORT=8080
ENXAME_HOST=0.0.0.0
ENXAME_DATA_PATH=/var/lib/enxame/data
ENXAME_LOG_PATH=/var/log/enxame
OLLAMA_URL=http://localhost:11434
EOF
    echo "  ✓ Configuração padrão criada"
fi

# Configura permissões
chown -R root:root "$INSTALL_DIR"
chown -R root:root "$DATA_DIR"
chown -R root:root "$LOG_DIR"
chown -R root:root "$CONFIG_DIR"
chmod 755 "$INSTALL_DIR"
chmod 644 "$CONFIG_DIR/.env"

echo -e "${GREEN}✓ Configuração concluída${NC}"

echo ""
echo -e "${YELLOW}>>> PASSO 6/6: Criando serviço e atalhos...${NC}"

# Cria serviço systemd
cat > /etc/systemd/system/enxame.service << EOF
[Unit]
Description=Enxame AI Platform
After=network.target ollama.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$CONFIG_DIR/.env
ExecStart=/usr/bin/python3 -m kernel.start
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable enxame
systemctl start enxame

# Cria atalho
cat > /usr/local/bin/enxame << EOF
#!/bin/bash
cd $INSTALL_DIR
exec python3 -m kernel.start "\$@"
EOF
chmod +x /usr/local/bin/enxame

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
echo "║    • enxame              - Iniciar Enxame               ║"
echo "║    • systemctl status enxame - Ver status               ║"
echo "║    • systemctl restart enxame - Reiniciar               ║"
echo "║                                                          ║"
echo "║  Acesse: http://localhost:8080                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

exit 0
