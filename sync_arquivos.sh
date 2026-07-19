#!/bin/bash
# ============================================================================
# ENXAME v3 - sync_arquivos.sh
# Roda em cada worker/artista periodicamente (chamado pelo agente_universal.py).
# Pergunta ao Juiz "quais .zim/.pmtiles eu deveria ter?" e usa rsync sobre SSH
# para buscar o que falta a partir do nó que já tem o arquivo (informado
# pelo Juiz junto com o plano).
# ============================================================================
set -e
source "$HOME/enxame/.env"

PLANO_URL="http://$IP_JUIZ:$JUIZ_PORTA/api/v1/particionamento?node_id=$NODE_ID"
PLANO=$(curl -s --max-time 10 "$PLANO_URL")

if [ -z "$PLANO" ] || [ "$PLANO" = "null" ]; then
  echo "[Sync] Juiz não retornou plano. Nada a fazer."
  exit 0
fi

# PLANO esperado (JSON): [{"origem_ip":"192.168.1.30","origem_user":"user","caminho":"/home/user/enxame/data/zim/wikipedia_pt.zim","destino":"zim"}, ...]
echo "$PLANO" | python3 -c "
import json, sys
itens = json.load(sys.stdin)
for it in itens:
    print(f\"{it['origem_ip']}|{it.get('origem_user','user')}|{it['caminho']}|{it['destino']}\")
" > /tmp/enxame_plano_sync.txt

while IFS='|' read -r ip user caminho destino; do
  [ -z "$ip" ] && continue
  DESTINO_LOCAL="$HOME/enxame/data/$destino/"
  mkdir -p "$DESTINO_LOCAL"
  echo "[Sync] Buscando $(basename "$caminho") de $ip ..."
  rsync -avz --partial --progress \
    -e "ssh -o StrictHostKeyChecking=accept-new" \
    "$user@$ip:$caminho" "$DESTINO_LOCAL" \
    && echo "[Sync] OK: $(basename "$caminho")" \
    || echo "[Sync] Falhou: $(basename "$caminho") (nó pode estar offline, tenta de novo depois)"
done < /tmp/enxame_plano_sync.txt

# Depois de sincronizar, reindexar localmente
"$HOME/enxame/venv/bin/python" "$HOME/enxame/indexador.py" --once
