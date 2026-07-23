#!/bin/bash
# =============================================================================
# ENXAME v5 - Instalador de Workers/Agentes
# Instalação modular com opção de função primária ou genérica
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
WORKERS_DIR="${ENXAME_DIR}/workers"
AGENTES_DIR="${ENXAME_DIR}/agentes"

# Variáveis de ambiente
WORKER_ID="${WORKER_ID:-worker-$(hostname)}"
JUIZ_URL="${JUIZ_URL:-ws://localhost:7700/exp}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
WORKER_ROLE="${WORKER_ROLE:-generic}"  # generic, programador, medico, engenheiro, tradutor, matematico, jurista, redator
WORKER_POOL_SIZE="${WORKER_POOL_SIZE:-4}"
WORKER_MAX_QUEUE="${WORKER_MAX_QUEUE:-128}"
HEARTBEAT_INTERVAL="${HEARTBEAT_INTERVAL:-5}"
MODEL="${MODEL:-qwen2.5:1.5b}"

# Função para mostrar uso
usage() {
    cat << EOF
Uso: $(basename "$0") [OPÇÕES]

Opções:
  --role <funcao>       Função primária do worker (padrão: generic)
                        Opções: generic, programador, medico, engenheiro, 
                                tradutor, matematico, jurista, redator
  --pool-size <N>       Tamanho do pool de workers (padrão: 4)
  --model <modelo>      Modelo Ollama (padrão: qwen2.5:1.5b)
  --juiz-url <url>      URL do Juiz (padrão: ws://localhost:7700/exp)
  --ollama-url <url>    URL do Ollama (padrão: http://localhost:11434)
  --help                Mostrar esta ajuda

Exemplos:
  $(basename "$0") --role programador --pool-size 8
  $(basename "$0") --role generic --model llama3.1:8b
  $(basename "$0") --role tradutor --juiz-url ws://192.168.1.100:7700/exp
EOF
    exit 0
}

# Parse de argumentos
while [[ $# -gt 0 ]]; do
    case $1 in
        --role)
            WORKER_ROLE="$2"
            shift 2
            ;;
        --pool-size)
            WORKER_POOL_SIZE="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
            ;;
        --juiz-url)
            JUIZ_URL="$2"
            shift 2
            ;;
        --ollama-url)
            OLLAMA_URL="$2"
            shift 2
            ;;
        --help)
            usage
            ;;
        *)
            log_error "Opção desconhecida: $1"
            usage
            ;;
    esac
done

echo "============================================================"
echo "  ENXAME v5 - Instalador de Workers/Agentes"
echo "  Função: ${WORKER_ROLE}"
echo "============================================================"
echo ""

# Validar função
VALID_ROLES=("generic" "programador" "medico" "engenheiro" "tradutor" "matematico" "jurista" "redator")
if [[ ! " ${VALID_ROLES[@]} " =~ " ${WORKER_ROLE} " ]]; then
    log_error "Função inválida: ${WORKER_ROLE}"
    echo "Funções válidas: ${VALID_ROLES[*]}"
    exit 1
fi

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
mkdir -p "$WORKERS_DIR/data"
mkdir -p "$WORKERS_DIR/logs"
mkdir -p "$WORKERS_DIR/plugins"

# 3. Copiar arquivos dos agentes
log_info "Copiando arquivos dos agentes..."
if [ -d "/workspace/agentes" ]; then
    cp -r /workspace/agentes/* "$AGENTES_DIR/" 2>/dev/null || true
elif [ -d "$ENXAME_DIR/agentes" ]; then
    : # Já existe
else
    mkdir -p "$AGENTES_DIR"
fi

# 4. Copiar plugins específicos da função
log_info "Configurando plugins para função: ${WORKER_ROLE}..."
if [ "$WORKER_ROLE" != "generic" ]; then
    PLUGIN_FILE="/workspace/agentes/plugins/${WORKER_ROLE}.py"
    if [ -f "$PLUGIN_FILE" ]; then
        cp "$PLUGIN_FILE" "$WORKERS_DIR/plugins/" 2>/dev/null || true
        log_info "Plugin ${WORKER_ROLE}.py instalado."
    else
        log_warn "Plugin ${WORKER_ROLE}.py não encontrado. Usando plugin base."
    fi
else
    log_info "Worker genérico configurado. Pode ser reconfigurado depois."
fi

# 5. Criar arquivo .env do worker
log_info "Criando configuração do worker..."
cat > "$WORKERS_DIR/.env" << EOF
# Worker Configuration
NODE_ID=${WORKER_ID}
ROLE=${WORKER_ROLE}
CLUSTER_ROLE=agente

# Connection
JUIZ_URL=${JUIZ_URL}
OLLAMA_URL=${OLLAMA_URL}

# Model
AGENT_MODEL=${MODEL}

# Performance
WORKER_POOL_SIZE=${WORKER_POOL_SIZE}
WORKER_MAX_QUEUE=${WORKER_MAX_QUEUE}
HEARTBEAT_INTERVAL=${HEARTBEAT_INTERVAL}
PLUGIN_REFRESH_INTERVAL=2

# Directories
NODE_DOCS_DIR=/data/docs
NODE_ZIM_DIR=/data/zim
EXP_SHARED_SECRET=${EXP_SHARED_SECRET:-enxame-secret-key}
EOF

# 6. Criar docker-compose.yml para o worker
log_info "Criando configuração Docker..."
cat > "$WORKERS_DIR/docker-compose.yml" << EOF
version: '3.8'

services:
  ollama-worker:
    image: ollama/ollama:latest
    container_name: enxame-ollama-${WORKER_ID}
    volumes:
      - ./ollama-data:/root/.ollama
    restart: always
    networks:
      - enxame-network

  worker-${WORKER_ROLE}:
    build:
      context: ${AGENTES_DIR}
      dockerfile: Dockerfile
    container_name: enxame-worker-${WORKER_ID}
    environment:
      - NODE_ID=${WORKER_ID}
      - ROLE=${WORKER_ROLE}
      - CLUSTER_ROLE=agente
      - JUIZ_URL=${JUIZ_URL}
      - OLLAMA_URL=${OLLAMA_URL}
      - AGENT_MODEL=${MODEL}
      - WORKER_POOL_SIZE=${WORKER_POOL_SIZE}
      - WORKER_MAX_QUEUE=${WORKER_MAX_QUEUE}
      - HEARTBEAT_INTERVAL=${HEARTBEAT_INTERVAL}
      - PLUGIN_REFRESH_INTERVAL=2
      - EXP_SHARED_SECRET=${EXP_SHARED_SECRET:-enxame-secret-key}
      - NODE_DOCS_DIR=/data/docs
      - NODE_ZIM_DIR=/data/zim
    volumes:
      - ./data/docs:/data/docs:ro
      - ./data/zim:/data/zim:ro
      - ./plugins:/app/agentes/plugins/custom:ro
    depends_on:
      - ollama-worker
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

# 7. Criar script de reconfiguração (para workers genéricos)
log_info "Criando script de reconfiguração..."
cat > "$WORKERS_DIR/reconfigure.sh" << 'EOF'
#!/bin/bash
# Script para reconfigurar worker genérico

WORKERS_DIR="$(dirname "$0")"
ENV_FILE="$WORKERS_DIR/.env"

echo "Reconfigurar Worker"
echo "==================="
echo ""
echo "Funções disponíveis:"
echo "  1) programador"
echo "  2) medico"
echo "  3) engenheiro"
echo "  4) tradutor"
echo "  5) matematico"
echo "  6) jurista"
echo "  7) redator"
echo "  8) generic (genérico)"
echo ""
read -p "Escolha a nova função (1-8): " choice

case $choice in
    1) NEW_ROLE="programador" ;;
    2) NEW_ROLE="medico" ;;
    3) NEW_ROLE="engenheiro" ;;
    4) NEW_ROLE="tradutor" ;;
    5) NEW_ROLE="matematico" ;;
    6) NEW_ROLE="jurista" ;;
    7) NEW_ROLE="redator" ;;
    8) NEW_ROLE="generic" ;;
    *) echo "Opção inválida"; exit 1 ;;
esac

echo "Atualizando função para: $NEW_ROLE"
sed -i "s/^ROLE=.*/ROLE=$NEW_ROLE/" "$ENV_FILE"

echo "Reiniciando worker..."
cd "$WORKERS_DIR"
docker compose restart worker-*

echo "Reconfiguração concluída!"
EOF
chmod +x "$WORKERS_DIR/reconfigure.sh"

# 8. Criar script de gerenciamento
log_info "Criando script de gerenciamento..."
cat > "$WORKERS_DIR/manage.sh" << EOF
#!/bin/bash
# Gerenciamento do Worker ${WORKER_ID}

WORKERS_DIR="\$(dirname "\$0")"
cd "\$WORKERS_DIR"

case "\$1" in
    start)
        echo "Iniciando worker..."
        docker compose up -d
        ;;
    stop)
        echo "Parando worker..."
        docker compose down
        ;;
    restart)
        echo "Reiniciando worker..."
        docker compose restart
        ;;
    status)
        echo "Status do worker:"
        docker compose ps
        ;;
    logs)
        docker compose logs -f
        ;;
    reconfigure)
        ./reconfigure.sh
        ;;
    *)
        echo "Uso: \$0 {start|stop|restart|status|logs|reconfigure}"
        exit 1
        ;;
esac
EOF
chmod +x "$WORKERS_DIR/manage.sh"

# 9. Criar rede Docker se não existir
log_info "Configurando rede Docker..."
docker network create enxame-network 2>/dev/null || true

# 10. Baixar modelo se necessário
log_info "Verificando modelo ${MODEL}..."
if command -v ollama &> /dev/null; then
    if ! ollama list | grep -q "^${MODEL}"; then
        log_info "Baixando modelo ${MODEL}..."
        ollama pull "$MODEL" || log_warn "Falha ao baixar modelo. O worker tentará quando iniciar."
    else
        log_info "Modelo ${MODEL} já está disponível."
    fi
fi

# 11. Iniciar worker
log_info "Iniciando worker..."
cd "$WORKERS_DIR"
docker compose up -d

# Aguardar inicialização
sleep 3

# 12. Mostrar informações finais
echo ""
echo "============================================================"
echo -e "${GREEN}  WORKER INSTALADO COM SUCESSO!${NC}"
echo "============================================================"
echo ""
echo "🤖 ID: ${WORKER_ID}"
echo "🎯 Função: ${WORKER_ROLE}"
echo "🧠 Modelo: ${MODEL}"
echo "🔗 Juiz: ${JUIZ_URL}"
echo ""
echo "📁 Diretório: $WORKERS_DIR"
echo "🔧 Gerenciar: $WORKERS_DIR/manage.sh"
if [ "$WORKER_ROLE" = "generic" ]; then
    echo "🔄 Reconfigurar: $WORKERS_DIR/reconfigure.sh"
fi
echo ""
echo "Comandos úteis:"
echo "  $WORKERS_DIR/manage.sh start    - Iniciar worker"
echo "  $WORKERS_DIR/manage.sh stop     - Parar worker"
echo "  $WORKERS_DIR/manage.sh status   - Ver status"
echo "  $WORKERS_DIR/manage.sh logs     - Ver logs"
if [ "$WORKER_ROLE" = "generic" ]; then
    echo "  $WORKERS_DIR/manage.sh reconfigure - Mudar função"
fi
echo ""
echo "============================================================"
