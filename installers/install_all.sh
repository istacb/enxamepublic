#!/bin/bash
# =============================================================================
# ENXAME v5 - Instalador Principal (Next > Next > Finish)
# Instalação completa de todos os componentes do Enxame
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[AVISO]${NC} $1"; }
log_error() { echo -e "${RED}[ERRO]${NC} $1"; }

# Diretórios
ENXAME_DIR="${ENXAME_DIR:-/opt/enxame}"
INSTALLER_DIR="$(dirname "$0")"

# Opções de instalação
INSTALL_JUIZ="${INSTALL_JUIZ:-true}"
INSTALL_BIBLIOTECARIO="${INSTALL_BIBLIOTECARIO:-true}"
INSTALL_WORKERS="${INSTALL_WORKERS:-true}"
INSTALL_OPENWEBUI="${INSTALL_OPENWEBUI:-true}"
INSTALL_CONSULTOR="${INSTALL_CONSULTOR:-true}"
WORKER_COUNT="${WORKER_COUNT:-2}"
WORKER_ROLE="${WORKER_ROLE:-generic}"

echo "============================================================"
echo "  ENXAME v5 - Instalador Completo"
echo "  Sistema de comunicação descentralizada com IA"
echo "============================================================"
echo ""

# Verificar se é root
if [ "$EUID" -ne 0 ]; then 
    log_error "Por favor execute como root (sudo ./install_all.sh)"
    exit 1
fi

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
    openssl \
    > /dev/null 2>&1

# 3. Verificar Docker
log_info "Verificando Docker..."
if ! command -v docker &> /dev/null; then
    log_warn "Docker não encontrado. Instalando..."
    curl -fsSL https://get.docker.com | sh -s -- --skip-start -q
    systemctl enable docker
    systemctl start docker
else
    log_info "Docker já está instalado."
fi

# Verificar Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    log_error "Docker Compose não encontrado. Por favor instale manualmente."
    exit 1
fi

# 4. Criar diretórios base
log_info "Criando estrutura de diretórios..."
mkdir -p "$ENXAME_DIR"
mkdir -p "$ENXAME_DIR/logs"
mkdir -p "$ENXAME_DIR/memory"
mkdir -p "$ENXAME_DIR/guardian"
mkdir -p "$ENXAME_DIR/failover"
mkdir -p "$ENXAME_DIR/data/kb_contabil"
mkdir -p "$ENXAME_DIR/data/kb_engenharia"
mkdir -p "$ENXAME_DIR/data/kb_rh_trabalhista"
mkdir -p "$ENXAME_DIR/data/kb_vendas"
mkdir -p "$ENXAME_DIR/data/kb_seguranca"
mkdir -p "$ENXAME_DIR/perfis"

# 5. Copiar arquivos do projeto
log_info "Copiando arquivos do projeto..."
if [ -d "/workspace" ]; then
    cp -r /workspace/core "$ENXAME_DIR/" 2>/dev/null || true
    cp -r /workspace/bibliotecario "$ENXAME_DIR/" 2>/dev/null || true
    cp -r /workspace/agentes "$ENXAME_DIR/" 2>/dev/null || true
    cp -r /workspace/juiz "$ENXAME_DIR/" 2>/dev/null || true
    cp -r /workspace/guardian "$ENXAME_DIR/" 2>/dev/null || true
    cp -r /workspace/scripts "$ENXAME_DIR/" 2>/dev/null || true
    cp /workspace/requirements.txt "$ENXAME_DIR/" 2>/dev/null || true
fi

# 6. Instalar Juiz
if [ "$INSTALL_JUIZ" = true ]; then
    log_info "Instalando Juiz (Coordenador)..."
    if [ -f "$INSTALLER_DIR/install_juiz.sh" ]; then
        bash "$INSTALLER_DIR/install_juiz.sh"
    else
        log_warn "Script install_juiz.sh não encontrado. Pulando..."
    fi
fi

# 7. Instalar Bibliotecário
if [ "$INSTALL_BIBLIOTECARIO" = true ]; then
    log_info "Instalando Bibliotecário (RAG)..."
    if [ -f "$INSTALLER_DIR/install_bibliotecario.sh" ]; then
        bash "$INSTALLER_DIR/install_bibliotecario.sh"
    else
        log_warn "Script install_bibliotecario.sh não encontrado. Pulando..."
    fi
fi

# 8. Instalar Workers
if [ "$INSTALL_WORKERS" = true ]; then
    log_info "Instalando ${WORKER_COUNT} workers com função: ${WORKER_ROLE}..."
    for i in $(seq 1 $WORKER_COUNT); do
        log_info "Instalando worker $i de $WORKER_COUNT..."
        if [ -f "$INSTALLER_DIR/install_worker.sh" ]; then
            WORKER_ID="worker-${i}-$(hostname)" \
            WORKER_ROLE="${WORKER_ROLE}" \
            bash "$INSTALLER_DIR/install_worker.sh"
        else
            log_warn "Script install_worker.sh não encontrado. Pulando..."
            break
        fi
    done
fi

# 9. Instalar OpenWebUI
if [ "$INSTALL_OPENWEBUI" = true ]; then
    log_info "Instalando OpenWebUI Integrado..."
    if [ -f "$INSTALLER_DIR/install_openwebui.sh" ]; then
        JUIZ_URL="${JUIZ_URL:-http://$(hostname -I | awk '{print $1}' | head -1):7700}" \
        bash "$INSTALLER_DIR/install_openwebui.sh"
    else
        log_warn "Script install_openwebui.sh não encontrado. Pulando..."
    fi
fi

# 10. Instalar Consultor
if [ "$INSTALL_CONSULTOR" = true ]; then
    log_info "Instalando Consultor (Interface + Monitoramento)..."
    if [ -f "$INSTALLER_DIR/install_consultor.sh" ]; then
        JUIZ_URL="${JUIZ_URL:-http://$(hostname -I | awk '{print $1}' | head -1):7700}" \
        OPENWEBUI_PORT="${OPENWEBUI_PORT:-3000}" \
        bash "$INSTALLER_DIR/install_consultor.sh"
    else
        log_warn "Script install_consultor.sh não encontrado. Pulando..."
    fi
fi

# 11. Configurar firewall (se ufw estiver ativo)
if command -v ufw &> /dev/null && ufw status | grep -q "Status: active"; then
    log_info "Configurando regras de firewall..."
    ufw allow 7700/tcp comment "ENXAME Juiz" 2>/dev/null || true
    ufw allow 7710/tcp comment "ENXAME Bibliotecário" 2>/dev/null || true
    ufw allow 7720/tcp comment "ENXAME Consultor" 2>/dev/null || true
    ufw allow 9000:9999/tcp comment "ENXAME Workers" 2>/dev/null || true
    ufw allow 3000/tcp comment "ENXAME OpenWebUI" 2>/dev/null || true
    ufw allow 11434/tcp comment "ENXAME Ollama" 2>/dev/null || true
fi

# 12. Criar script de comando unificado
log_info "Criando comando unificado 'enxame'..."
cat > /usr/local/bin/enxame << 'EOF'
#!/bin/bash
# Comando unificado do ENXAME v5

ENXAME_DIR="/opt/enxame"
JUIZ_DIR="$ENXAME_DIR/juiz"
BIB_DIR="$ENXAME_DIR/bibliotecario"
WORKERS_DIR="$ENXAME_DIR/workers"
OPENWEBUI_DIR="$ENXAME_DIR/openwebui"
CONSULTOR_DIR="$ENXAME_DIR/consultor"

usage() {
    cat << USAGE
Uso: enxame <comando> [componente]

Comandos:
  start     - Iniciar componentes
  stop      - Parar componentes
  restart   - Reiniciar componentes
  status    - Ver status dos componentes
  logs      - Ver logs dos componentes

Componentes:
  juiz          - Serviço coordenador
  bibliotecario - Serviço RAG/Knowledge Base
  workers       - Workers/Agentes
  openwebui     - Interface Web
  consultor     - Interface + Monitoramento (novo)
  all           - Todos os componentes (padrão)

Exemplos:
  enxame start all
  enxame status juiz
  enxame logs workers
  enxame restart openwebui
  enxame status consultor
USAGE
    exit 0
}

if [ $# -eq 0 ]; then
    usage
fi

ACTION="$1"
COMPONENT="${2:-all}"

run_action() {
    local dir="$1"
    local name="$2"
    
    if [ -f "$dir/manage.sh" ]; then
        echo "[$name] Executando $ACTION..."
        cd "$dir"
        bash manage.sh "$ACTION" 2>/dev/null || true
    fi
}

case "$COMPONENT" in
    juiz)
        run_action "$JUIZ_DIR" "Juiz"
        ;;
    bibliotecario)
        run_action "$BIB_DIR" "Bibliotecário"
        ;;
    workers)
        run_action "$WORKERS_DIR" "Workers"
        ;;
    openwebui)
        run_action "$OPENWEBUI_DIR" "OpenWebUI"
        ;;
    consultor)
        run_action "$CONSULTOR_DIR" "Consultor"
        ;;
    all)
        run_action "$JUIZ_DIR" "Juiz"
        run_action "$BIB_DIR" "Bibliotecário"
        run_action "$WORKERS_DIR" "Workers"
        run_action "$OPENWEBUI_DIR" "OpenWebUI"
        run_action "$CONSULTOR_DIR" "Consultor"
        ;;
    *)
        echo "Componente desconhecido: $COMPONENT"
        usage
        ;;
esac
EOF
chmod +x /usr/local/bin/enxame

# 12. Mostrar informações finais
IP_ADDRESS=$(hostname -I | awk '{print $1}' | head -1)

echo ""
echo "============================================================"
echo -e "${GREEN}  INSTALAÇÃO CONCLUÍDA COM SUCESSO!${NC}"
echo "============================================================"
echo ""
echo "📦 ENXAME v5 foi instalado em: $ENXAME_DIR"
echo ""
echo "🚀 Serviços instalados:"
[ "$INSTALL_JUIZ" = true ] && echo "   ✓ Juiz (porta 7700)"
[ "$INSTALL_BIBLIOTECARIO" = true ] && echo "   ✓ Bibliotecário (porta 7710)"
[ "$INSTALL_WORKERS" = true ] && echo "   ✓ ${WORKER_COUNT} Workers (função: ${WORKER_ROLE})"
[ "$INSTALL_OPENWEBUI" = true ] && echo "   ✓ OpenWebUI (porta 3000)"
[ "$INSTALL_CONSULTOR" = true ] && echo "   ✓ Consultor (porta 7720) - Interface + Monitoramento"
echo ""
echo "🌐 Acessos:"
[ "$INSTALL_JUIZ" = true ] && echo "   Juiz:        http://${IP_ADDRESS}:7700"
[ "$INSTALL_BIBLIOTECARIO" = true ] && echo "   Bibliotecário: http://${IP_ADDRESS}:7710"
[ "$INSTALL_OPENWEBUI" = true ] && echo "   OpenWebUI:   http://${IP_ADDRESS}:3000"
[ "$INSTALL_CONSULTOR" = true ] && echo "   Consultor:   http://${IP_ADDRESS}:7720"
echo ""
echo "🔧 Comando unificado:"
echo "   enxame start all      - Iniciar tudo"
echo "   enxame stop all       - Parar tudo"
echo "   enxame status all     - Ver status"
echo "   enxame logs workers   - Ver logs dos workers"
echo "   enxame status consultor - Ver status do Consultor"
echo ""
echo "📖 Documentação: https://github.com/istacb/enxamepublic"
echo ""
echo "============================================================"
