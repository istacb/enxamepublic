#!/bin/bash
# ============================================================================
# ENXAME v3 - ssh_provision_cluster.sh
# Roda NO JUIZ. Provisiona automaticamente cada máquina do inventário via
# SSH: copia o core certo (todos os arquivos, mas cada perfil só ativa o
# que precisa) e roda o bootstrap remoto já com o perfil correto.
#
# Uso:
#   ./ssh_provision_cluster.sh --inventory inventory.yaml
# ============================================================================
set -e

JUIZ_IP="$(hostname -I | awk '{print $1}')"
INVENTORY="inventory.yaml"
SSH_PASS_PADRAO="123"
CORE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --inventory) INVENTORY="$2"; shift 2 ;;
    --juiz) JUIZ_IP="$2"; shift 2 ;;
    *) shift ;;
  esac
done

VERDE='\033[0;32m'; AMARELO='\033[1;33m'; VERMELHO='\033[0;31m'; AZUL='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${AZUL}[INFO]${NC} $1"; }
ok()   { echo -e "${VERDE}[OK]${NC} $1"; }
warn() { echo -e "${AMARELO}[AVISO]${NC} $1"; }
err()  { echo -e "${VERMELHO}[ERRO]${NC} $1"; }

command -v sshpass &>/dev/null || sudo apt install -y -qq sshpass

log "Juiz identificado como: $JUIZ_IP"

if [ ! -f "$INVENTORY" ]; then
  err "inventory '$INVENTORY' não encontrado. Veja inventory.example.yaml."
  exit 1
fi

MAQUINAS=()
while IFS=';' read -r ip user pass perfil; do
  [[ "$ip" =~ ^#.*$ || -z "$ip" ]] && continue
  MAQUINAS+=("$ip;$user;$pass;$perfil")
done < <(grep -v '^\s*#' "$INVENTORY" | grep ';')

if [ ${#MAQUINAS[@]} -eq 0 ]; then
  warn "Nenhuma máquina no inventário."
  exit 0
fi

for entrada in "${MAQUINAS[@]}"; do
  IFS=';' read -r ip user pass perfil <<< "$entrada"
  perfil="${perfil:-worker_engenharia}"
  log "----------------------------------------"
  log "Provisionando $ip (usuário: $user, perfil: $perfil)"

  if ! sshpass -p "$pass" ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 \
       "$user@$ip" "echo ok" 2>/dev/null | grep -q ok; then
    err "  SSH falhou em $ip. Pulando."
    continue
  fi
  ok "  SSH OK"

  sshpass -p "$pass" ssh "$user@$ip" "mkdir -p ~/enxame ~/enxame/perfis" 2>/dev/null

  log "  Copiando core completo (mesmo binário serve qualquer perfil)..."
  sshpass -p "$pass" scp -o StrictHostKeyChecking=accept-new -q \
    "$CORE_DIR/core/agente_universal.py" \
    "$CORE_DIR/core/juiz.py" \
    "$CORE_DIR/core/bibliotecario.py" \
    "$CORE_DIR/core/indexador.py" \
    "$CORE_DIR/scripts/bootstrap_node.sh" \
    "$CORE_DIR/scripts/sync_arquivos.sh" \
    "$user@$ip:~/enxame/" 2>/dev/null
  sshpass -p "$pass" scp -o StrictHostKeyChecking=accept-new -rq \
    "$CORE_DIR/core/perfis/." \
    "$user@$ip:~/enxame/perfis/" 2>/dev/null

  log "  Rodando bootstrap remoto (perfil: $perfil)..."
  ARG_JUIZ=""
  [ "$perfil" != "juiz" ] && ARG_JUIZ="--juiz $JUIZ_IP"
  sshpass -p "$pass" ssh "$user@$ip" \
    "chmod +x ~/enxame/bootstrap_node.sh && ~/enxame/bootstrap_node.sh $ARG_JUIZ --perfil $perfil" \
    && ok "  $ip provisionado com sucesso!" \
    || err "  Bootstrap falhou em $ip (veja log remoto em ~/enxame/logs/)"
done

echo ""
ok "Provisionamento concluído. Verifique workers registrados em:"
echo "  curl http://$JUIZ_IP:7700/api/v1/workers"
