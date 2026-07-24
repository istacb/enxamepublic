#!/bin/bash
# =============================================================================
# ENXAME v5 - Instalador Automático para Ubuntu/Debian
# Instalação "Next > Next > Finish" - sem perguntas ao usuário
# Inclui: Backend Python, Frontend Svelte/OpenWebUI, Ollama e configuração completa
# =============================================================================

set -e

echo "============================================================"
echo "  ENXAME v5 - Instalador Automático (Ubuntu/Debian)"
echo "  Sistema de comunicação descentralizada com IA"
echo "============================================================"
echo ""

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[AVISO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERRO]${NC} $1"
}

# Verificar se é root
if [ "$EUID" -ne 0 ]; then 
    log_error "Por favor execute como root (sudo ./install_ubuntu.sh)"
    exit 1
fi

# Diretório de instalação
ENXAME_DIR="/opt/enxame"
USER_ENXAME_DIR="$HOME/.enxame"
OPENWEBUI_DIR="$ENXAME_DIR/openwebui"

log_info "Instalando ENXAME v5 em $ENXAME_DIR..."

# 1. Atualizar repositórios
log_info "Atualizando repositórios do sistema..."
apt-get update -qq

# 2. Instalar dependências do sistema
log_info "Instalando dependências do sistema..."
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    curl \
    wget \
    git \
    sqlite3 \
    libsqlite3-dev \
    net-tools \
    iproute2 \
    openssh-client \
    jq \
    nodejs \
    npm \
    > /dev/null 2>&1

# 3. Criar diretórios
log_info "Criando estrutura de diretórios..."
mkdir -p "$ENXAME_DIR"
mkdir -p "$USER_ENXAME_DIR/logs"
mkdir -p "$USER_ENXAME_DIR/memory"
mkdir -p "$USER_ENXAME_DIR/guardian"
mkdir -p "$USER_ENXAME_DIR/failover"
mkdir -p "$USER_ENXAME_DIR/data/kb_contabil"
mkdir -p "$USER_ENXAME_DIR/data/kb_engenharia"
mkdir -p "$USER_ENXAME_DIR/data/kb_rh_trabalhista"
mkdir -p "$USER_ENXAME_DIR/data/kb_vendas"
mkdir -p "$USER_ENXAME_DIR/data/kb_seguranca"
mkdir -p "$USER_ENXAME_DIR/perfis"
mkdir -p "$OPENWEBUI_DIR"

# 4. Copiar arquivos do projeto
log_info "Copiando arquivos do projeto..."
cd "$(dirname "$0")/.."

# Copiar backend Python
cp -r backend/ "$ENXAME_DIR/" 2>/dev/null || true
cp -r agentes/ "$ENXAME_DIR/" 2>/dev/null || true
cp -r bibliotecario/ "$ENXAME_DIR/" 2>/dev/null || true
cp -r juiz/ "$ENXAME_DIR/" 2>/dev/null || true
cp -r guardian/ "$ENXAME_DIR/" 2>/dev/null || true
cp -r scripts/ "$ENXAME_DIR/" 2>/dev/null || true
cp requirements.txt "$ENXAME_DIR/" 2>/dev/null || true

# Copiar frontend SvelteKit (OpenWebUI + Enxame)
log_info "Copiando frontend SvelteKit (OpenWebUI + Enxame)..."
cp -r src/ "$OPENWEBUI_DIR/" 2>/dev/null || true
cp package.json "$OPENWEBUI_DIR/" 2>/dev/null || true
cp package-lock.json "$OPENWEBUI_DIR/" 2>/dev/null || true
cp svelte.config.js "$OPENWEBUI_DIR/" 2>/dev/null || true
cp vite.config.ts "$OPENWEBUI_DIR/" 2>/dev/null || true
cp tsconfig.json "$OPENWEBUI_DIR/" 2>/dev/null || true
cp .npmrc "$OPENWEBUI_DIR/" 2>/dev/null || true
cp -r static/ "$OPENWEBUI_DIR/" 2>/dev/null || true

# Copiar perfis JSON
if [ -d "perfis" ]; then
    cp perfis/*.json "$USER_ENXAME_DIR/perfis/" 2>/dev/null || true
fi

# 5. Criar ambiente virtual Python
log_info "Criando ambiente virtual Python..."
python3 -m venv "$ENXAME_DIR/venv"
source "$ENXAME_DIR/venv/bin/activate"

# 6. Instalar dependências Python
log_info "Instalando dependências Python..."
pip install --upgrade pip -q
pip install fastapi uvicorn pydantic httpx websockets zeroconf typer rich numpy -q

# Instalar dependências do OpenWebUI backend
log_info "Instalando dependências do OpenWebUI backend..."
cd "$ENXAME_DIR/backend"
pip install -r requirements.txt -q 2>/dev/null || true

# 7. Instalar Node.js dependencies e build do frontend
log_info "Instalando dependências Node.js e build do frontend..."
cd "$OPENWEBUI_DIR"

# Instalar dependências npm
npm install --legacy-peer-deps -q 2>/dev/null || npm install -q 2>/dev/null || true

# Build do frontend
log_info "Compilando frontend SvelteKit..."
npm run build -q 2>/dev/null || true

# 8. Configurar serviço systemd para o OpenWebUI
log_info "Configurando serviços systemd..."
cat > /etc/systemd/system/openwebui.service << 'EOF'
[Unit]
Description=OpenWebUI with Enxame Integration
After=network.target enxame-juiz.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/enxame/openwebui
Environment="PATH=/opt/enxame/venv/bin"
Environment="PYTHONPATH=/opt/enxame/backend"
ExecStart=/opt/enxame/venv/bin/python -m uvicorn backend.open_webui.main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 9. Configurar serviço systemd para o Juiz
cat > /etc/systemd/system/enxame-juiz.service << 'EOF'
[Unit]
Description=ENXAME v5 - Serviço Juiz
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/enxame
Environment="PATH=/opt/enxame/venv/bin"
ExecStart=/opt/enxame/venv/bin/python /opt/enxame/juiz.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 10. Configurar serviço systemd para o Guardian
cat > /etc/systemd/system/enxame-guardian.service << 'EOF'
[Unit]
Description=ENXAME v5 - Serviço Guardian (Segurança)
After=network.target enxame-juiz.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/enxame
Environment="PATH=/opt/enxame/venv/bin"
ExecStart=/opt/enxame/venv/bin/python /opt/enxame/guardian/guardian.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 11. Recarregar systemd e iniciar serviços
log_info "Iniciando serviços do ENXAME..."
systemctl daemon-reload
systemctl enable enxame-juiz -q
systemctl enable enxame-guardian -q
systemctl enable openwebui -q
systemctl start enxame-juiz
systemctl start enxame-guardian
systemctl start openwebui

# 12. Instalar Ollama (opcional mas recomendado)
log_info "Verificando Ollama..."
if ! command -v ollama &> /dev/null; then
    log_warn "Ollama não encontrado. Instalando..."
    curl -fsSL https://ollama.com/install.sh | sh -s -- --skip-start -q
    
    # Iniciar Ollama como serviço
    systemctl enable ollama -q
    systemctl start ollama
else
    log_info "Ollama já está instalado."
fi

# 13. Verificar e instalar modelos mínimos (apenas se necessário)
log_info "Verificando modelos de IA instalados..."

# Função para verificar tamanho do modelo (em bilhões de parâmetros)
check_model_size() {
    local model=$1
    local min_size=$2
    
    # Verificar se o modelo existe
    if ollama list | grep -q "^$model"; then
        log_info "Modelo $model já está instalado (não será modificado)."
        return 0
    fi
    
    # Modelo não existe, verificar se atende tamanho mínimo
    # Lista de modelos recomendados com seus tamanhos mínimos
    case $model in
        "qwen2.5:1.5b"|"qwen2.5:3b"|"qwen2.5:7b")
            log_info "Baixando modelo $model (mínimo 1.5B parâmetros)..."
            su -c "ollama pull $model" -s /bin/sh 2>/dev/null || true
            ;;
        "llama3.2:1b")
            log_warn "Modelo $model tem menos de 1.5B. Pulando..."
            return 1
            ;;
        "llama3.2:3b"|"llama3.1:8b"|"mistral:7b"|"gemma2:2b"|"gemma2:9b")
            log_info "Baixando modelo $model (mínimo 1.5B parâmetros)..."
            su -c "ollama pull $model" -s /bin/sh 2>/dev/null || true
            ;;
        *)
            log_warn "Modelo $model não está na lista de recomendados. Pulando..."
            return 1
            ;;
    esac
}

# Verificar modelos existentes
EXISTING_MODELS=$(ollama list 2>/dev/null | grep -v "^NAME" | wc -l)

if [ "$EXISTING_MODELS" -eq 0 ]; then
    log_warn "Nenhum modelo encontrado. Instalando modelos mínimos recomendados..."
    
    # Instalar apenas modelos >= 1.5B
    check_model_size "qwen2.5:1.5b" 1.5
    check_model_size "nomic-embed-text" 0  # Modelo de embedding, sempre útil
    
    log_info "Modelos básicos instalados. Usuário pode adicionar mais modelos manualmente."
else
    log_info "$EXISTING_MODELS modelo(s) já instalado(s). Nenhum modelo será modificado."
    log_info "Para adicionar modelos adicionais, execute: ollama pull <nome-do-modelo>"
    log_info "Nota: Apenas modelos com >= 1.5B parâmetros são recomendados para produção."
fi

# 14. Criar arquivo de configuração
log_info "Criando arquivo de configuração..."
cat > "$USER_ENXAME_DIR/.env" << EOF
# Configuração ENXAME v5
NODE_ID=$(hostname)
IP_JUIZ=$(hostname -I | awk '{print $1}' | head -1)
JUIZ_PORTA=7700
BIBLIOTECARIO_PORTA=7710
GUARDIAN_PORTA=7720
OLLAMA_URL=http://localhost:11434
OPENWEBUI_URL=http://localhost:8080
ENXAME_DIR=$USER_ENXAME_DIR
EOF

# 15. Criar script de inicialização rápida
cat > /usr/local/bin/enxame << 'EOF'
#!/bin/bash
# Script de linha de comando do ENXAME v5

case "$1" in
    status)
        echo "=== Status do ENXAME ==="
        systemctl status enxame-juiz --no-pager -l
        echo ""
        systemctl status enxame-guardian --no-pager -l
        echo ""
        systemctl status openwebui --no-pager -l
        ;;
    start)
        systemctl start enxame-juiz
        systemctl start enxame-guardian
        systemctl start openwebui
        echo "Serviços iniciados."
        ;;
    stop)
        systemctl stop enxame-juiz
        systemctl stop enxame-guardian
        systemctl stop openwebui
        echo "Serviços parados."
        ;;
    restart)
        systemctl restart enxame-juiz
        systemctl restart enxame-guardian
        systemctl restart openwebui
        echo "Serviços reiniciados."
        ;;
    logs)
        journalctl -u enxame-juiz -u enxame-guardian -u openwebui -f --no-pager
        ;;
    rebuild-frontend)
        echo "Recompilando frontend..."
        cd /opt/enxame/openwebui
        npm install --legacy-peer-deps
        npm run build
        systemctl restart openwebui
        echo "Frontend recompilado e serviço reiniciado."
        ;;
    *)
        echo "Uso: enxame {status|start|stop|restart|logs|rebuild-frontend}"
        exit 1
        ;;
esac
EOF
chmod +x /usr/local/bin/enxame

# 16. Configurar firewall (se ufw estiver ativo)
if command -v ufw &> /dev/null && ufw status | grep -q "Status: active"; then
    log_info "Configurando regras de firewall..."
    ufw allow 7700/tcp comment "ENXAME Juiz" 2>/dev/null || true
    ufw allow 7710/tcp comment "ENXAME Bibliotecário" 2>/dev/null || true
    ufw allow 7720/tcp comment "ENXAME Guardian" 2>/dev/null || true
    ufw allow 9000:9999/tcp comment "ENXAME Workers" 2>/dev/null || true
    ufw allow 8080/tcp comment "OpenWebUI" 2>/dev/null || true
fi

# 17. Mostrar informações finais
echo ""
echo "============================================================"
echo -e "${GREEN}  INSTALAÇÃO CONCLUÍDA COM SUCESSO!${NC}"
echo "============================================================"
echo ""
echo "📦 ENXAME v5 foi instalado em: $ENXAME_DIR"
echo "📁 Diretório do usuário: $USER_ENXAME_DIR"
echo "🌐 Frontend OpenWebUI: $OPENWEBUI_DIR"
echo ""
echo "🚀 Serviços iniciados:"
echo "   - Juiz (porta 7700)"
echo "   - Guardian (porta 7720)"
echo "   - OpenWebUI com Enxame (porta 8080)"
echo ""
echo "🔧 Comandos úteis:"
echo "   enxame status           - Ver status dos serviços"
echo "   enxame logs             - Ver logs em tempo real"
echo "   enxame restart          - Reiniciar serviços"
echo "   enxame rebuild-frontend - Recompilar frontend após alterações"
echo ""
echo "🌐 Acesse o painel web:"
echo "   OpenWebUI + Enxame: http://$(hostname -I | awk '{print $1}' | head -1):8080"
echo "   Mission Control:    http://$(hostname -I | awk '{print $1}' | head -1):8080/enxame"
echo ""
echo "📖 Documentação: https://github.com/istacb/enxamepublic"
echo ""
echo "============================================================"
