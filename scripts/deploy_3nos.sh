#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="${ROOT_DIR}/deploy"
NODE_INDEX=""
SET_HOSTNAME="0"
SKIP_MODELS="0"

usage() {
  cat <<EOF
Uso: $(basename "$0") [opções]

Deploy automático do ENXAME para o nó local.

Opções:
  --node <1|2|3>         Força o índice do nó (senão tenta auto detectar)
  --env-file <arquivo>   Arquivo .env a usar no compose (padrão: deploy/env/nodeX.env)
  --set-hostname         Ajusta hostname para padrão enxame-nodeX-<role>
  --skip-models          Não executa pull dos modelos Ollama
  -h, --help             Mostra ajuda
EOF
}

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

detect_node_from_hostname() {
  local h
  h="$(hostname | tr '[:upper:]' '[:lower:]')"

  if [[ "${h}" =~ node1|juiz ]]; then
    echo "1"
  elif [[ "${h}" =~ node2|bibliotecario|bibliotecário|bib ]]; then
    echo "2"
  elif [[ "${h}" =~ node3|agente|agentes|worker ]]; then
    echo "3"
  else
    echo ""
  fi
}

NODE_ENV_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --node) NODE_INDEX="$2"; shift 2 ;;
    --env-file) NODE_ENV_FILE="$2"; shift 2 ;;
    --set-hostname) SET_HOSTNAME="1"; shift ;;
    --skip-models) SKIP_MODELS="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERRO] Opção inválida: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "${NODE_INDEX}" ]]; then
  NODE_INDEX="$(detect_node_from_hostname)"
fi

if [[ -z "${NODE_INDEX}" ]]; then
  echo "[ERRO] Não foi possível detectar o nó automaticamente." >&2
  echo "Use --node 1|2|3" >&2
  exit 1
fi

if [[ "${NODE_INDEX}" != "1" && "${NODE_INDEX}" != "2" && "${NODE_INDEX}" != "3" ]]; then
  echo "[ERRO] --node deve ser 1, 2 ou 3." >&2
  exit 1
fi

case "${NODE_INDEX}" in
  1)
    NODE_ROLE="juiz"
    NODE_DIR="${ROOT_DIR}/node1-juiz"
    MODEL_SCOPE="juiz"
    DEFAULT_HOSTNAME="enxame-node1-juiz"
    ;;
  2)
    NODE_ROLE="bibliotecario"
    NODE_DIR="${ROOT_DIR}/node2-bibliotecario"
    MODEL_SCOPE="bibliotecario"
    DEFAULT_HOSTNAME="enxame-node2-bibliotecario"
    ;;
  3)
    NODE_ROLE="agentes"
    NODE_DIR="${ROOT_DIR}/node3-agentes"
    MODEL_SCOPE="agentes"
    DEFAULT_HOSTNAME="enxame-node3-agentes"
    ;;
esac

if [[ -z "${NODE_ENV_FILE}" ]]; then
  NODE_ENV_FILE="${DEPLOY_DIR}/env/node${NODE_INDEX}.env"
fi

if [[ ! -f "${NODE_ENV_FILE}" ]]; then
  echo "[ERRO] Arquivo de ambiente não encontrado: ${NODE_ENV_FILE}" >&2
  echo "Execute antes: ./scripts/setup_inicial.sh" >&2
  exit 1
fi

if [[ ! -f "${NODE_DIR}/docker-compose.yml" ]]; then
  echo "[ERRO] docker-compose.yml não encontrado em ${NODE_DIR}" >&2
  exit 1
fi

LOCAL_IP="$(hostname -I | awk '{print $1}')"
JUIZ_HOST_IP="$(grep -E '^JUIZ_HOST_IP=' "${NODE_ENV_FILE}" | cut -d'=' -f2-)"

if [[ -z "${LOCAL_IP}" ]]; then
  echo "[ERRO] Não foi possível detectar IP local." >&2
  exit 1
fi

if [[ -n "${JUIZ_HOST_IP}" ]] && [[ "${NODE_INDEX}" != "1" ]]; then
  if command -v sudo >/dev/null 2>&1; then
    if ! grep -q "${JUIZ_HOST_IP}[[:space:]]\+enxame-juiz" /etc/hosts; then
      log "Adicionando entrada de host do Juiz em /etc/hosts..."
      echo "${JUIZ_HOST_IP} enxame-juiz" | sudo tee -a /etc/hosts >/dev/null
    fi
  fi
fi

if [[ "${SET_HOSTNAME}" == "1" ]]; then
  if command -v sudo >/dev/null 2>&1; then
    log "Configurando hostname para ${DEFAULT_HOSTNAME}..."
    sudo hostnamectl set-hostname "${DEFAULT_HOSTNAME}"
  else
    echo "[AVISO] sudo indisponível; hostname não alterado."
  fi
fi

TMP_ENV_FILE="${NODE_DIR}/.env.runtime"
cp "${NODE_ENV_FILE}" "${TMP_ENV_FILE}"

echo "NODE_ROLE=${NODE_ROLE}" >> "${TMP_ENV_FILE}"
echo "NODE_IP=${LOCAL_IP}" >> "${TMP_ENV_FILE}"

log "Nó detectado: ${NODE_INDEX} (${NODE_ROLE})"
log "Diretório de deploy: ${NODE_DIR}"
log "Arquivo de ambiente: ${TMP_ENV_FILE}"

(
  cd "${NODE_DIR}"
  docker compose --env-file "${TMP_ENV_FILE}" up -d --build
)

if [[ "${SKIP_MODELS}" != "1" ]]; then
  log "Baixando modelos Ollama para o perfil ${MODEL_SCOPE}..."
  (
    cd "${ROOT_DIR}"
    ./scripts/pull_models.sh "${MODEL_SCOPE}"
  )
fi

log "Executando inicialização automática de benchmark/eleição..."
(
  cd "${ROOT_DIR}"
  NODE_ROLE="${NODE_ROLE}" \
  ENXAME_JUIZ_URL="http://${JUIZ_HOST_IP:-127.0.0.1}:7700" \
  EXP_SHARED_SECRET="$(grep -E '^EXP_SHARED_SECRET=' "${TMP_ENV_FILE}" | cut -d'=' -f2-)" \
  python3 scripts/cluster_auto_init.py || true
)

log "Deploy concluído para nó ${NODE_INDEX} (${NODE_ROLE})."
