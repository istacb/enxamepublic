#!/bin/bash
# ============================================================================
# ENXAME v3 - curar_para_worker.sh
# Roda NO BIBLIOTECÁRIO. Envia um arquivo/pasta já organizado dentro de
# ~/enxame/data/kb_<tema> pro worker certo (via o endpoint autorizado
# /api/v1/mover_para_worker do bibliotecario.py).
#
# Uso:
#   ./curar_para_worker.sh data/kb_contabil/rfb_in_2023.pdf worker_contabil
#   ./curar_para_worker.sh data/kb_engenharia/nr18 worker_engenharia
# ============================================================================
set -e

ORIGEM="$1"
PERFIL_DESTINO="$2"

if [ -z "$ORIGEM" ] || [ -z "$PERFIL_DESTINO" ]; then
  echo "Uso: $0 <caminho_dentro_de_~/enxame> <perfil_destino>"
  echo "Perfis válidos: worker_engenharia | worker_contabil | artista_midia"
  exit 1
fi

source "$HOME/enxame/.env"

BIBLIO_URL="http://localhost:${BIBLIOTECARIO_PORTA:-7710}"

echo "Enviando '$ORIGEM' para o perfil '$PERFIL_DESTINO'..."

RESPOSTA=$(curl -s -X POST "$BIBLIO_URL/api/v1/mover_para_worker" \
  -H "Content-Type: application/json" \
  -d "{\"origem\": \"$ORIGEM\", \"perfil_destino\": \"$PERFIL_DESTINO\", \"admin_token\": \"$ADMIN_TOKEN\", \"solicitante\": \"$(whoami)\"}")

echo "$RESPOSTA" | python3 -m json.tool 2>/dev/null || echo "$RESPOSTA"
