#!/bin/bash
# =============================================================================
# ENXAME v5 - Instalador do Bibliotecário (RAG/Knowledge Base)
# Instalação automática do serviço de gerenciamento de conhecimento
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
BIBLIOTECARIO_DIR="${ENXAME_DIR}/bibliotecario"

# Variáveis de ambiente
NODE_ID="${NODE_ID:-bibliotecario-$(hostname)}"
BIB_PORT="${BIB_PORT:-7710}"
JUIZ_URL="${JUIZ_URL:-ws://localhost:7700/exp}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
REDIS_URL="${REDIS_URL:-redis://redis-bibliotecario:6379/0}"
QDRANT_URL="${QDRANT_URL:-http://qdrant-bibliotecario:6333}"
EXP_SHARED_SECRET="${EXP_SHARED_SECRET:-enxame-secret-key}"
TRANSLATION_ENABLED="${TRANSLATION_ENABLED:-true}"

echo "============================================================"
echo "  ENXAME v5 - Instalador do Bibliotecário (RAG)"
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
mkdir -p "$BIBLIOTECARIO_DIR/data/docs"
mkdir -p "$BIBLIOTECARIO_DIR/data/zim"
mkdir -p "$BIBLIOTECARIO_DIR/data/qdrant"
mkdir -p "$BIBLIOTECARIO_DIR/logs"

# 3. Copiar arquivos do Bibliotecário
log_info "Copiando arquivos do Bibliotecário..."
if [ -d "/workspace/bibliotecario" ]; then
    cp -r /workspace/bibliotecario/* "$BIBLIOTECARIO_DIR/" 2>/dev/null || true
elif [ -d "$ENXAME_DIR/bibliotecario" ]; then
    : # Já existe
else
    mkdir -p "$BIBLIOTECARIO_DIR"
fi

# 4. Copiar core do Enxame
log_info "Copiando núcleo do Enxame..."
if [ -d "/workspace/core" ]; then
    cp -r /workspace/core "$ENXAME_DIR/" 2>/dev/null || true
fi

# 5. Criar arquivo .env do Bibliotecário
log_info "Criando configuração do Bibliotecário..."
cat > "$BIBLIOTECARIO_DIR/.env" << EOF
# Bibliotecário Configuration
NODE_ID=${NODE_ID}
ROLE=bibliotecario
PORT=${BIB_PORT}

# Connection
JUIZ_URL=${JUIZ_URL}
OLLAMA_URL=${OLLAMA_URL}

# RAG Services
REDIS_URL=${REDIS_URL}
QDRANT_URL=${QDRANT_URL}

# Directories
BIB_DOCS_DIR=/data/docs
BIB_ZIM_DIR=/data/zim
NODE_DOCS_DIR=/data/docs
NODE_ZIM_DIR=/data/zim

# Features
TRANSLATION_ENABLED=${TRANSLATION_ENABLED}
EXP_SHARED_SECRET=${EXP_SHARED_SECRET}
EOF

# 6. Criar docker-compose.yml para o Bibliotecário
log_info "Criando configuração Docker..."
cat > "$BIBLIOTECARIO_DIR/docker-compose.yml" << EOF
version: '3.8'

services:
  ollama-bibliotecario:
    image: ollama/ollama:latest
    container_name: enxame-ollama-bibliotecario
    volumes:
      - ./ollama-data:/root/.ollama
    restart: always
    networks:
      - enxame-network

  redis-bibliotecario:
    image: redis:7-alpine
    container_name: enxame-redis-bibliotecario
    restart: always
    networks:
      - enxame-network

  qdrant-bibliotecario:
    image: qdrant/qdrant:v1.10.1
    container_name: enxame-qdrant-bibliotecario
    volumes:
      - ./data/qdrant:/qdrant/storage
    restart: always
    networks:
      - enxame-network

  bibliotecario:
    build:
      context: ${ENXAME_DIR}
      dockerfile: bibliotecario/Dockerfile
    container_name: enxame-bibliotecario
    ports:
      - "\${BIB_PORT:-7710}:7710"
    environment:
      - NODE_ID=${NODE_ID}
      - ROLE=bibliotecario
      - CLUSTER_ROLE=agente
      - JUIZ_URL=${JUIZ_URL}
      - OLLAMA_URL=${OLLAMA_URL}
      - BIB_MODEL=gemma2:9b
      - REDIS_URL=${REDIS_URL}
      - QDRANT_URL=${QDRANT_URL}
      - BIB_DOCS_DIR=/data/docs
      - BIB_ZIM_DIR=/data/zim
      - TRANSLATION_ENABLED=${TRANSLATION_ENABLED}
      - EXP_SHARED_SECRET=${EXP_SHARED_SECRET}
    volumes:
      - ${ENXAME_DIR}/core:/app/core:ro
      - ${ENXAME_DIR}/agentes:/app/agentes:ro
      - ./data/docs:/data/docs
      - ./data/zim:/data/zim
      - ./data/qdrant:/data/qdrant
    depends_on:
      - ollama-bibliotecario
      - redis-bibliotecario
      - qdrant-bibliotecario
    restart: always
    networks:
      - enxame-network
    extra_hosts:
      - "host.docker.internal:host-gateway"

networks:
  enxame-network:
    external: true
    name: enxame-network
EOF

# 7. Criar script de gerenciamento
log_info "Criando script de gerenciamento..."
cat > "$BIBLIOTECARIO_DIR/manage.sh" << EOF
#!/bin/bash
# Gerenciamento do Bibliotecário

BIBLIOTECARIO_DIR="\$(dirname "\$0")"
cd "\$BIBLIOTECARIO_DIR"

case "\$1" in
    start)
        echo "Iniciando Bibliotecário..."
        docker compose up -d
        ;;
    stop)
        echo "Parando Bibliotecário..."
        docker compose down
        ;;
    restart)
        echo "Reiniciando Bibliotecário..."
        docker compose restart
        ;;
    status)
        echo "Status do Bibliotecário:"
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
chmod +x "$BIBLIOTECARIO_DIR/manage.sh"

# 8. Criar rede Docker se não existir
log_info "Configurando rede Docker..."
docker network create enxame-network 2>/dev/null || true

# 9. Iniciar Bibliotecário
log_info "Iniciando Bibliotecário..."
cd "$BIBLIOTECARIO_DIR"
docker compose up -d

# Aguardar inicialização
sleep 5

# 10. Mostrar informações finais
IP_ADDRESS=$(hostname -I | awk '{print $1}' | head -1)

echo ""
echo "============================================================"
echo -e "${GREEN}  BIBLIOTECÁRIO INSTALADO COM SUCESSO!${NC}"
echo "============================================================"
echo ""
echo "📚 ID: ${NODE_ID}"
echo "🌐 API: http://${IP_ADDRESS}:${BIB_PORT}"
echo "🔗 WebSocket: ws://${IP_ADDRESS}:${BIB_PORT}/exp"
echo ""
echo "📁 Diretório: $BIBLIOTECARIO_DIR"
echo "📂 Documentos: $BIBLIOTECARIO_DIR/data/docs"
echo "📂 ZIM Files: $BIBLIOTECARIO_DIR/data/zim"
echo "🔧 Gerenciar: $BIBLIOTECARIO_DIR/manage.sh"
echo ""
echo "Comandos úteis:"
echo "  $BIBLIOTECARIO_DIR/manage.sh start   - Iniciar Bibliotecário"
echo "  $BIBLIOTECARIO_DIR/manage.sh stop    - Parar Bibliotecário"
echo "  $BIBLIOTECARIO_DIR/manage.sh status  - Ver status"
echo "  $BIBLIOTECARIO_DIR/manage.sh logs    - Ver logs"
echo ""
echo "Para adicionar documentos:"
echo "  Coloque arquivos PDF, TXT, MD em: $BIBLIOTECARIO_DIR/data/docs"
echo ""
echo "============================================================"
