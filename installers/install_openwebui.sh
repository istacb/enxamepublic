#!/bin/bash
# =============================================================================
# ENXAME v5 - Instalador do OpenWebUI Integrado
# Instalação automática do OpenWebUI com frontend do Enxame
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
OPENWEBUI_DIR="${ENXAME_DIR}/openwebui"
BACKEND_DIR="${ENXAME_DIR}/backend"
FRONTEND_DIR="${ENXAME_DIR}/src"

# Variáveis de ambiente
OPENWEBUI_PORT="${OPENWEBUI_PORT:-3000}"
JUIZ_URL="${JUIZ_URL:-http://localhost:7700}"
SECRET_KEY="${SECRET_KEY:-$(openssl rand -hex 32)}"

echo "============================================================"
echo "  ENXAME v5 - Instalador do OpenWebUI Integrado"
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
mkdir -p "$OPENWEBUI_DIR/data"
mkdir -p "$OPENWEBUI_DIR/models"
mkdir -p "$BACKEND_DIR"

# 3. Copiar backend do OpenWebUI
log_info "Configurando backend do OpenWebUI..."
if [ -d "/workspace/backend/open_webui" ]; then
    cp -r /workspace/backend/open_webui/* "$BACKEND_DIR/" 2>/dev/null || true
elif [ -d "$ENXAME_DIR/backend/open_webui" ]; then
    cp -r "$ENXAME_DIR/backend/open_webui"/* "$BACKEND_DIR/" 2>/dev/null || true
fi

# 4. Copiar frontend do Enxame para o OpenWebUI
log_info "Integrando frontend do Enxame ao OpenWebUI..."
if [ -d "/workspace/src" ]; then
    # Copiar componentes customizados do Enxame
    mkdir -p "$BACKEND_DIR/static/custom"
    cp -r /workspace/src/lib "$BACKEND_DIR/static/custom/" 2>/dev/null || true
    cp -r /workspace/src/routes "$BACKEND_DIR/static/custom/" 2>/dev/null || true
    cp /workspace/src/app.css "$BACKEND_DIR/static/custom/" 2>/dev/null || true
fi

# 5. Criar arquivo .env do OpenWebUI
log_info "Criando configuração do OpenWebUI..."
cat > "$OPENWEBUI_DIR/.env" << EOF
# OpenWebUI Configuration for ENXAME
WEBUI_NAME=Enxame WebUI
WEBUI_PORT=${OPENWEBUI_PORT}
SECRET_KEY=${SECRET_KEY}

# Enxame Integration
ENXAME_JUIZ_URL=${JUIZ_URL}
ENXAME_ENABLED=true

# Ollama
OLLAMA_BASE_URL=http://ollama:11434

# Database
DATABASE_URL=postgresql://postgres:postgres@openwebui-db:5432/openwebui

# CORS
CORS_ALLOW_ORIGIN=*

# Features
ENABLE_SIGNUP=true
DEFAULT_USER_ROLE=user

# RAG
RAG_ENABLED=true
CHUNK_SIZE=500
CHUNK_OVERLAP=100
EOF

# 6. Criar docker-compose.yml para OpenWebUI
log_info "Criando configuração Docker..."
cat > "$OPENWEBUI_DIR/docker-compose.yml" << EOF
version: '3.8'

services:
  openwebui-db:
    image: postgres:15-alpine
    container_name: enxame-openwebui-db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: openwebui
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
    restart: always
    networks:
      - enxame-network

  openwebui:
    build:
      context: ${BACKEND_DIR}
      dockerfile: Dockerfile.openwebui
    container_name: enxame-openwebui
    ports:
      - "\${OPENWEBUI_PORT:-3000}:8080"
    environment:
      - WEBUI_NAME=Enxame WebUI
      - SECRET_KEY=${SECRET_KEY}
      - ENXAME_JUIZ_URL=${JUIZ_URL}
      - ENXAME_ENABLED=true
      - OLLAMA_BASE_URL=http://ollama:11434
      - DATABASE_URL=postgresql://postgres:postgres@openwebui-db:5432/openwebui
    volumes:
      - ./data/openwebui:/app/backend/data
      - ./models:/app/backend/models
    depends_on:
      - openwebui-db
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

# 7. Criar Dockerfile para OpenWebUI customizado
log_info "Criando Dockerfile customizado..."
cat > "$BACKEND_DIR/Dockerfile.openwebui" << 'EOF'
FROM ghcr.io/open-webui/open-webui:main

USER root

# Copiar integrações do Enxame
COPY static/custom /app/static/custom
COPY open_webui/enxame /app/backend/open_webui/enxame

# Instalar dependências adicionais se necessário
RUN pip install --no-cache-dir fastapi websockets zeroconf || true

USER nobody

EXPOSE 8080
CMD ["bash", "-c", "exec python -m uvicorn open_webui.main:app --host 0.0.0.0 --port 8080"]
EOF

# 8. Criar script de atualização
log_info "Criando script de atualização..."
cat > "$OPENWEBUI_DIR/update.sh" << 'EOF'
#!/bin/bash
# Script de atualização do OpenWebUI com repositório original

OPENWEBUI_DIR="$(dirname "$0")"
cd "$OPENWEBUI_DIR"

echo "Atualizando OpenWebUI do repositório original..."

# Parar containers
docker compose down

# Pull da imagem mais recente
docker compose pull openwebui

# Recriar containers
docker compose up -d

echo "Atualização concluída!"
EOF
chmod +x "$OPENWEBUI_DIR/update.sh"

# 9. Criar rede Docker se não existir
log_info "Configurando rede Docker..."
docker network create enxame-network 2>/dev/null || true

# 10. Iniciar OpenWebUI
log_info "Iniciando OpenWebUI..."
cd "$OPENWEBUI_DIR"
docker compose up -d

# Aguardar inicialização
sleep 5

# 11. Mostrar informações finais
echo ""
echo "============================================================"
echo -e "${GREEN}  OPENWEBUI INSTALADO COM SUCESSO!${NC}"
echo "============================================================"
echo ""
echo "🌐 Acesso: http://localhost:${OPENWEBUI_PORT}"
echo "📁 Dados: $OPENWEBUI_DIR/data"
echo "🔧 Atualizar: $OPENWEBUI_DIR/update.sh"
echo ""
echo "============================================================"
