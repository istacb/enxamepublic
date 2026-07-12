#!/bin/bash
# ============================================================================
# ENXAME v3 - Triagem Automática Inicial (Corrigido)
# ============================================================================

ORIGEM="/mnt/Arquivos/project-nomad"
DEST_ENG="/mnt/Arquivos/project-nomad/data/kb_engenharia"
DEST_CONT="/mnt/Arquivos/project-nomad/data/kb_contabil"
DEST_GERAL="/mnt/Arquivos/project-nomad/data/kb_geral"

mkdir -p "$DEST_ENG" "$DEST_CONT" "$DEST_GERAL"

echo "=== Iniciando Triagem Inicial ==="

# 1. TRIAGEM ENGENHARIA (Busca termos técnicos de engenharia e obras)
echo "Triando arquivos de Engenharia..."
find "$ORIGEM" -not -path "*/data/*" -type f \( -name "*.pdf" -o -name "*.docx" -o -name "*.txt" -o -name "*.xlsx" \) | grep -iE "nbr|concreto|obra|projeto|calculo|estrutura|arquitetura|norma|laudo|nr18|nr-18" | while read -r arquivo; do
    echo "Movendo para Engenharia: $(basename "$arquivo")"
    mv "$arquivo" "$DEST_ENG/"
done

# 2. TRIAGEM CONTÁBIL (Busca termos fiscais, tributários e de departamento pessoal)
echo "Triando arquivos Contábeis..."
find "$ORIGEM" -not -path "*/data/*" -type f \( -name "*.pdf" -o -name "*.docx" -o -name "*.txt" -o -name "*.xlsx" \) | grep -iE "rfb|imposto|fiscal|contabil|tributo|declaracao|balanco|clt|trabalhista|fgts|receita|folha" | while read -r arquivo; do
    echo "Movendo para Contábil: $(basename "$arquivo")"
    mv "$arquivo" "$DEST_CONT/"
done

# 3. O RESTO VAI PARA O GERAL
echo "Movendo arquivos restantes para a base Geral..."
find "$ORIGEM" -not -path "*/data/*" -type f \( -name "*.pdf" -o -name "*.docx" -o -name "*.txt" -o -name "*.xlsx" \) | while read -r arquivo; do
    echo "Movendo para Geral: $(basename "$arquivo")"
    mv "$arquivo" "$DEST_GERAL/"
done

echo "=== Triagem concluída com sucesso! ==="
