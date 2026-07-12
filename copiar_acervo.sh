#!/bin/bash
# ============================================================================
# ENXAME v3 - copiar_acervo.sh
# Uso pelo ARTISTA: copia arquivos de interesse (planilhas, livros, normas,
# imagens, músicas) para o acervo compartilhado do enxame.
# NUNCA copia instaladores (.exe .msi .apk .AppImage .dmg .deb .rpm .iso) --
# mesmo que estejam dentro da pasta de origem, são pulados automaticamente.
#
# Uso:
#   ./copiar_acervo.sh /caminho/de/origem
#   ./copiar_acervo.sh "/mnt/c/Users/voce/Documents"
# ============================================================================
set -e
ORIGEM="$1"
ACERVO_DIR="$HOME/enxame/data/acervo"

if [ -z "$ORIGEM" ] || [ ! -d "$ORIGEM" ]; then
  echo "Uso: $0 <pasta_de_origem>"
  exit 1
fi

mkdir -p "$ACERVO_DIR"

echo "Copiando arquivos de interesse de '$ORIGEM' para o acervo do enxame..."
echo "(planilhas, livros, normas/pdf, imagens, músicas -- instaladores são ignorados)"
echo ""

rsync -avz --progress \
  --include="*.xlsx" --include="*.xls" --include="*.csv" \
  --include="*.pdf" --include="*.epub" --include="*.docx" --include="*.txt" --include="*.md" \
  --include="*.jpg" --include="*.jpeg" --include="*.png" \
  --include="*.mp3" --include="*.flac" --include="*.wav" \
  --include="*/" \
  --exclude="*.exe" --exclude="*.msi" --exclude="*.apk" --exclude="*.AppImage" \
  --exclude="*.dmg" --exclude="*.deb" --exclude="*.rpm" --exclude="*.iso" \
  --exclude="*" \
  "$ORIGEM"/ "$ACERVO_DIR"/

echo ""
echo "Feito. Reindexando acervo..."
"$HOME/enxame/venv/bin/python" "$HOME/enxame/indexador.py" --once
echo "Acervo atualizado e catalogado."
