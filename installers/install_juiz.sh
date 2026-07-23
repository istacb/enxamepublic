#!/bin/bash
# =============================================================================
# ENXAME v5 - Instalador do Juiz (Coordinator)
# Instalação automática do serviço coordenador do cluster
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
JUIZ_DIR="${ENXAME_DIR}/juiz"

# Variáveis de ambiente
NODE_ID="${NODE_ID:-juiz-$(hostname)}"
JUIZ_PORT="${JUIZ_PORT:-7700}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
EXP_SHARED_SECRET="${EXP_SHARED_SECRET:-$(openssl rand -hex 32)}"

echo "============================================================"
echo "  ENXAME v5 - Instalador do Juiz (Coordenador)"
echo "============================================================"
echo ""

# 1. Verificar dependências
log_info "Verificando dependências..."
if ! command -v docker &> /dev/null; then
    log_error "Docker não encontrado. Instale o Docker primeiro."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    log_error "Docker Compose não encontrado."
    exit 1
fi

# 2. Criar diretórios
log_info "Criando estrutura de diretórios..."
mkdir -p "$JUIZ_DIR/data"
mkdir -p "$JUIZ_DIR/logs"
mkdir -p "$JUIZ_DIR/config"

# 3. Copiar arquivos do Juiz
log_info "Copiando arquivos do Juiz..."
if [ -d "/workspace/juiz" ]; then
    cp -r /workspace/juiz/* "$JUIZ_DIR/" 2>/dev/null || true
elif [ -d "$ENXAME_DIR/juiz" ]; then
    : # Já existe
else
    mkdir -p "$JUIZ_DIR"
fi

# 4. Copiar core do Enxame
log_info "Copiando núcleo do Enxame..."
if [ -d "/workspace/core" ]; then
    cp -r /workspace/core "$ENXAME_DIR/" 2>/dev/null || true
fi

# 5. Criar arquivo .env do Juiz
log_info "Criando configuração do Juiz..."
cat > "$JUIZ_DIR/.env" << EOF
# Juiz Configuration
NODE_ID=${NODE_ID}
ROLE=juiz
PORT=${JUIZ_PORT}

# Ollama
OLLAMA_URL=${OLLAMA_URL}

# Security
EXP_SHARED_SECRET=${EXP_SHARED_SECRET}

# Cluster
CLUSTER_ENABLED=true
DISCOVERY_ENABLED=true
EOF

# 6. Criar docker-compose.yml para o Juiz
log_info "Criando configuração Docker..."
cat > "$JUIZ_DIR/docker-compose.yml" << EOF
version: '3.8'

services:
  ollama-juiz:
    image: ollama/ollama:latest
    container_name: enxame-ollama-juiz
    volumes:
      - ./ollama-data:/root/.ollama
    ports:
      - "11434:11434"
    restart: always
    networks:
      - enxame-network

  juiz:
    build:
      context: ${ENXAME_DIR}
      dockerfile: juiz/Dockerfile
    container_name: enxame-juiz
    ports:
      - "\${JUIZ_PORT:-7700}:7700"
    environment:
      - NODE_ID=${NODE_ID}
      - ROLE=juiz
      - OLLAMA_URL=${OLLAMA_URL}
      - EXP_SHARED_SECRET=${EXP_SHARED_SECRET}
    volumes:
      - ${ENXAME_DIR}/core:/app/core:ro
      - ${ENXAME_DIR}/agentes:/app/agentes:ro
      - ./data:/app/data
    depends_on:
      - ollama-juiz
    restart: always
    networks:
      - enxame-network

networks:
  enxame-network:
    name: enxame-network
EOF

# 7. Criar script de gerenciamento
log_info "Criando script de gerenciamento..."
cat > "$JUIZ_DIR/manage.sh" << EOF
#!/bin/bash
# Gerenciamento do Juiz

JUIZ_DIR="\$(dirname "\$0")"
cd "\$JUIZ_DIR"

case "\$1" in
    start)
        echo "Iniciando Juiz..."
        docker compose up -d
        ;;
    stop)
        echo "Parando Juiz..."
        docker compose down
        ;;
    restart)
        echo "Reiniciando Juiz..."
        docker compose restart
        ;;
    status)
        echo "Status do Juiz:"
        docker compose ps
        ;;
    logs)
        docker compose logs -f
        ;;
    *)
        echo "Uso: \$0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
EOF
chmod +x "$JUIZ_DIR/manage.sh"

# 8. Criar rede Docker se não existir
log_info "Configurando rede Docker..."
docker network create enxame-network 2>/dev/null || true

# 9. Iniciar Juiz
log_info "Iniciando Juiz..."
cd "$JUIZ_DIR"
docker compose up -d

# Aguardar inicialização
sleep 5

# 10. Mostrar informações finais
IP_ADDRESS=$(hostname -I | awk '{print $1}' | head -1)

echo ""
echo "============================================================"
echo -e "${GREEN}  JUIZ INSTALADO COM SUCESSO!${NC}"
echo "============================================================"
echo ""
echo "🏛️ ID: ${NODE_ID}"
echo "🌐 API: http://${IP_ADDRESS}:${JUIZ_PORT}"
echo "🔗 WebSocket: ws://${IP_ADDRESS}:${JUIZ_PORT}/exp"
echo ""
echo "📁 Diretório: $JUIZ_DIR"
echo "🔧 Gerenciar: $JUIZ_DIR/manage.sh"
echo ""
echo "Comandos úteis:"
echo "  $JUIZ_DIR/manage.sh start   - Iniciar Juiz"
echo "  $JUIZ_DIR/manage.sh stop    - Parar Juiz"
echo "  $JUIZ_DIR/manage.sh status  - Ver status"
echo "  $JUIZ_DIR/manage.sh logs    - Ver logs"
echo ""
echo "Próximos passos:"
echo "  1. Instale workers: install_worker.sh"
echo "  2. Instale OpenWebUI: install_openwebui.sh"
echo ""
echo "============================================================"
