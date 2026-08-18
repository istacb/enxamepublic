#!/bin/bash
# =============================================================================
# ENXAME - Instalador Oficial para Ubuntu/Debian Linux v1.0.0
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

echo -e "${YELLOW}>>> PASSO 1/7: Verificando requisitos do sistema...${NC}"

# Verifica requisitos
check_requirements() {
    local missing=()

    # Busca primeiro se já existe Python 3 instalado (e qual versão), em
    # vez de simplesmente mandar instalar por cima de uma instalação
    # existente.
    if command -v python3 &> /dev/null; then
        echo -e "${GREEN}✓ Python 3 encontrado: $(python3 --version)${NC}"
    else
        echo -e "${YELLOW}Python 3 não encontrado, será instalado.${NC}"
        missing+=("python3")
    fi

    if command -v pip3 &> /dev/null; then
        echo -e "${GREEN}✓ pip3 encontrado: $(pip3 --version | cut -d' ' -f1-2)${NC}"
    else
        missing+=("python3-pip")
    fi

    if ! command -v node &> /dev/null; then
        echo -e "${YELLOW}Node.js não encontrado. Instalando...${NC}"
        apt-get update -qq
        apt-get install -y -qq nodejs npm
    else
        echo -e "${GREEN}✓ Node.js encontrado: $(node --version)${NC}"
    fi

    if [ ${#missing[@]} -ne 0 ]; then
        echo -e "${YELLOW}Instalando dependências: ${missing[*]}${NC}"
        apt-get update -qq
        apt-get install -y -qq "${missing[@]}"
    fi

    # A partir do Ubuntu/Debian com Python 3.12 (PEP 668), o ambiente
    # Python do sistema é "externally managed" e recusa `pip install`
    # direto. Em vez de forçar com --break-system-packages (que arrisca
    # quebrar o Python do sistema), instalamos as dependências em um
    # venv isolado — por isso o pacote de venv precisa estar presente.
    if ! python3 -m venv --help &> /dev/null; then
        echo -e "${YELLOW}Módulo venv do Python não encontrado, instalando...${NC}"
        apt-get update -qq
        apt-get install -y -qq python3-venv python3-full 2>/dev/null \
            || apt-get install -y -qq python3-venv
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
    echo -e "${YELLOW}>>> PASSO 3/7: Removendo instalação antiga...${NC}"
    
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
echo -e "${YELLOW}>>> PASSO 4/7: Instalando novo Enxame...${NC}"

# Cria diretórios
mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR/data"
mkdir -p "$LOG_DIR"
mkdir -p "$CONFIG_DIR"

# Copia arquivos. O instalador é distribuído junto com o repositório
# (ele fica em api/install/ dentro do próprio checkout), então nunca é
# necessário clonar nada aqui — e como o repositório é público, clonar
# nunca pediria usuário/senha de qualquer forma.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [ ! -d "$REPO_ROOT/juiz" ] || [ ! -d "$REPO_ROOT/bibliotecario" ]; then
    echo -e "${RED}Erro: não encontrei o repositório do Enxame a partir de $SCRIPT_DIR.${NC}"
    echo -e "${RED}Execute este script de dentro do checkout do repositório (api/install/install-ubuntu.sh).${NC}"
    exit 1
fi
cp -r "$REPO_ROOT"/* "$INSTALL_DIR/"
echo "  ✓ Arquivos copiados de $REPO_ROOT"

cd "$INSTALL_DIR"

# Instala dependências Python em um venv isolado (evita o erro
# "externally-managed-environment" do PEP 668 no Python 3.12+ do
# Ubuntu/Debian, sem precisar de --break-system-packages).
echo "Criando ambiente virtual Python em $INSTALL_DIR/.venv..."
python3 -m venv "$INSTALL_DIR/.venv"
VENV_PIP="$INSTALL_DIR/.venv/bin/pip"
VENV_PYTHON="$INSTALL_DIR/.venv/bin/python3"
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
    cat > "$CONFIG_DIR/.env" << 'EOF'
# Enxame Configuration
ENXAME_ENV=production
ENXAME_HOST=0.0.0.0
ENXAME_DATA_PATH=/var/lib/enxame/data
ENXAME_LOG_PATH=/var/log/enxame
OLLAMA_URL=http://localhost:11434
# ENXAME_NODE_ROLE, ENXAME_NODE_ID e ENXAME_NODE_PORT são preenchidos
# automaticamente pelo passo de configuração de função do node (mais abaixo).
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
echo -e "${YELLOW}>>> PASSO 6/7: Criando serviço e atalhos...${NC}"

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
ExecStart=$INSTALL_DIR/.venv/bin/python3 $INSTALL_DIR/api/install/run_node.py --env-file $CONFIG_DIR/.env
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

# Cria atalho
cat > /usr/local/bin/enxame << EOF
#!/bin/bash
cd $INSTALL_DIR
exec "$INSTALL_DIR/.venv/bin/python3" api/install/run_node.py --env-file $CONFIG_DIR/.env "\$@"
EOF
chmod +x /usr/local/bin/enxame

echo -e "${GREEN}✓ Serviço criado${NC}"

echo ""
echo -e "${YELLOW}>>> PASSO 7/7: Configurando função do node...${NC}"
echo ""

# Pergunta a função inicial do node (só pergunta de fato se o .env restaurado
# ainda não tiver uma função salva de uma instalação anterior), faz a
# varredura mDNS por outros nodes na rede e, na primeira instalação, exibe
# a confirmação de qual função cada node assumiu.
"$INSTALL_DIR/.venv/bin/python3" "$INSTALL_DIR/api/install/node_role_setup.py" --env-file "$CONFIG_DIR/.env"

# Só agora inicia o serviço, já com a função definida no .env
systemctl enable enxame
systemctl start enxame

# Limpa backup
rm -rf "$BACKUP_DIR"

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
echo "║    • systemctl status enxame  - Ver status               ║"
echo "║    • systemctl restart enxame - Reiniciar               ║"
echo "║                                                          ║"
echo "║  Função e porta deste node: ver $CONFIG_DIR/.env"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

exit 0
