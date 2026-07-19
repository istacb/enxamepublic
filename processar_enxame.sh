#!/bin/bash
# ============================================================================
# ENXAME v3 - Automação Global (Correção de Sintaxe do Find)
# ============================================================================

# Onde você baixa os arquivos
PASTA_DOWNLOADS="$HOME/Downloads"

# Configurações dos Workers
USER_WORKER="user"
IP_ENGENHARIA="192.168.1.10"
IP_CONTABIL="192.168.1.20"

# Pastas locais no HD de 750GB
DIR_BASE="/mnt/Arquivos/project-nomad/data"
PASTA_ENG="$DIR_BASE/kb_engenharia"
PASTA_CONT="$DIR_BASE/kb_contabil"
PASTA_GERAL="$DIR_BASE/kb_geral"
PASTA_OK="$DIR_BASE/processados"

# --- PARTE 1: INTERCEPTAR E CATALOGAR DOWNLOADS NOVOS ---
if [ -d "$PASTA_DOWNLOADS" ]; then
    # Engenharia
    find "$PASTA_DOWNLOADS" -maxdepth 1 -type f \( -name "*.pdf" -o -name "*.docx" -o -name "*.txt" -o -name "*.xlsx" \) | grep -iE "nbr|concreto|obra|projeto|calculo|estrutura|arquitetura|norma|laudo|nr18|nr-18" | while read -r arquivo; do
        mv "$arquivo" "$PASTA_ENG/"
    done

    # Contábil
    find "$PASTA_DOWNLOADS" -maxdepth 1 -type f \( -name "*.pdf" -o -name "*.docx" -o -name "*.txt" -o -name "*.xlsx" \) | grep -iE "rfb|imposto|fiscal|contabil|tributo|declaracao|balanco|clt|trabalhista|fgts|receita|folha" | while read -r arquivo; do
        mv "$arquivo" "$PASTA_CONT/"
    done
fi

# --- PARTE 2: ENVIO AUTOMÁTICO PARA OS WORKERS ---

# 1. PROCESSAR ENGENHARIA
if [ "$(ls -A $PASTA_ENG 2>/dev/null)" ]; then
    rsync -avz "$PASTA_ENG/" "$USER_WORKER@$IP_ENGENHARIA:~/enxame/data/kb_engenharia/"
    mv "$PASTA_ENG"/* "$PASTA_OK/"
fi

# 2. PROCESSAR CONTÁBIL
if [ "$(ls -A $PASTA_CONT 2>/dev/null)" ]; then
    rsync -avz "$PASTA_CONT/" "$USER_WORKER@$IP_CONTABIL:~/enxame/data/kb_contabil/"
    mv "$PASTA_CONT"/* "$PASTA_OK/"
fi
