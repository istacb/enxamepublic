#!/bin/bash
# ENXAME Launcher para Linux/macOS
# =================================
# Duplo clique neste arquivo (ou execute ./run_enxame.sh) para iniciar o Enxame

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detecta o diretório do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  ENXAME - Inicializando...${NC}"
echo -e "${BLUE}========================================${NC}"
echo

# Verifica se Python está disponível
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 não encontrado${NC}"
    echo "   Instale Python 3.10+ no seu sistema"
    exit 1
fi

# Verifica se está no diretório correto
if [ ! -f "run_enxame.py" ]; then
    echo -e "${RED}❌ Arquivo run_enxame.py não encontrado${NC}"
    echo "   Execute este script a partir da pasta raiz do Enxame"
    exit 1
fi

# Verifica se Ollama está rodando
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
if curl -s -f -o /dev/null --max-time 2 "$OLLAMA_URL/api/tags" 2>/dev/null; then
    echo -e "${GREEN}✅ Ollama detectado e respondendo${NC}"
else
    echo -e "${YELLOW}⚠️  Ollama não detectado em $OLLAMA_URL${NC}"
    echo "   O Enxame funcionará apenas com embeddings locais (modo offline)"
    echo "   Para usar modelos LLM, instale Ollama: https://ollama.com"
fi

echo
echo -e "${GREEN}🚀 Iniciando Enxame Kernel...${NC}"
echo

# Inicia o Enxame (passa todos os argumentos)
python3 run_enxame.py "$@"

echo
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Enxame finalizado${NC}"
echo -e "${BLUE}========================================${NC}"