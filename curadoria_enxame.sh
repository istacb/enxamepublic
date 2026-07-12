#!/bin/bash
# ============================================================================
# ENXAME v3 - Automação do Bibliotecário
# ============================================================================

# Configurações dos Workers (ajuste o usuário 'user' se for diferente)
USER_WORKER="user"
IP_ENGENHARIA="192.168.1.10"
IP_CONTABIL="192.168.1.20"

# Pastas locais no HD de 750GB
DIR_BASE="/mnt/Arquivos/project-nomad/data"
PASTA_ENG="$DIR_BASE/kb_engenharia"
PASTA_CONT="$DIR_BASE/kb_contabil"
PASTA_OK="$DIR_BASE/processados"

# Criar pastas caso não existam
mkdir -p "$PASTA_ENG" "$PASTA_CONT" "$PASTA_OK"

echo "=== Iniciando Processamento Automático: $(date) ==="

# 1. PROCESSAR ENGENHARIA
if [ "$(ls -A $PASTA_ENG)" ]; then
    echo "Arquivos encontrados para Engenharia. Enviando para $IP_ENGENHARIA..."
    # Envia via rsync para a pasta correspondente no worker remoto
    rsync -avz --progress "$PASTA_ENG/" "$USER_WORKER@$IP_ENGENHARIA:~/enxame/data/kb_engenharia/"
    
    # Move os arquivos enviados para a pasta de histórico local para limpar a fila
    mv "$PASTA_ENG"/* "$PASTA_OK/"
    echo "Arquivos de engenharia processados."
fi

# 2. PROCESSAR CONTÁBIL
if [ "$(ls -A $PASTA_CONT)" ]; then
    echo "Arquivos encontrados para Contábil. Enviando para $IP_CONTABIL..."
    rsync -avz --progress "$PASTA_CONT/" "$USER_WORKER@$IP_CONTABIL:~/enxame/data/kb_contabil/"
    
    mv "$PASTA_CONT"/* "$PASTA_OK/"
    echo "Arquivos contábeis processados."
fi

echo "=== Processamento concluído ==="
