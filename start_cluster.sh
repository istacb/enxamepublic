#!/bin/bash

echo "=========================================="
echo "  INICIANDO CLUSTER ENXAME (LINUX/MAC)"
echo "=========================================="

# 1. Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "[ERRO] Python3 não encontrado. Instale o Python 3.10+."
    exit 1
fi

# 2. Instalar Dependências
echo "[INFO] Instalando/atualizando dependências..."
pip3 install -q -r requirements.txt
pip3 install -q -r bibliotecario/requirements.txt

# Função para rodar em background e logar
run_service() {
    local name=$1
    local script=$2
    echo "[INFO] Iniciando $name..."
    nohup python3 "$script" > "logs/${name}.log" 2>&1 &
    echo $! > "logs/${name}.pid"
    sleep 3 # Aguarda inicialização básica
}

# Criar pasta de logs se não existir
mkdir -p logs

# 3. Iniciar Bibliotecário
run_service "Bibliotecario" "bibliotecario/main.py"

# 4. Iniciar Juiz
run_service "Juiz" "juiz/app.py"

# 5. Iniciar Workers
run_service "Workers" "agentes/cluster_worker.py"

echo "=========================================="
echo "  CLUSTER ONLINE!"
echo "  - Bibliotecário: Indexando e busca híbrida ativa"
echo "  - Juiz: Ouvindo requisições na porta 8000"
echo "  - Workers: Aguardando tarefas"
echo "  Logs disponíveis na pasta ./logs/"
echo "=========================================="
echo "Para parar o cluster, execute: ./stop_cluster.sh"
