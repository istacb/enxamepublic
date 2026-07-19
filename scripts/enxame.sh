#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_SCRIPT="${ROOT_DIR}/scripts/deploy_3nos.sh"

NODE_INDEX=""
NODE_ENV_FILE=""
ACTION="${1:-}"
LOG_LINES="200"
HEALTH_TIMEOUT="5"

usage() {
  cat <<EOF
Uso: $(basename "$0") <start|stop|restart|status|logs|health> [opções]

Comandos:
  start       Sobe os serviços do nó local
  stop        Para e remove os serviços do nó local
  restart     Reinicia os serviços do nó local
  status      Mostra status dos containers do nó local
  logs        Exibe logs centralizados do nó local
  health      Executa health check do nó local

Opções:
  --node <1|2|3>        Força o índice do nó
  --env-file <arquivo>  Arquivo .env (padrão: deploy/env/nodeX.env)
  --lines <N>           Número de linhas no comando logs (padrão: 200)
  --timeout <seg>       Timeout de health check (padrão: 5)
  -h, --help            Exibe esta ajuda
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

parse_args() {
  shift || true
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --node) NODE_INDEX="$2"; shift 2 ;;
      --env-file) NODE_ENV_FILE="$2"; shift 2 ;;
      --lines) LOG_LINES="$2"; shift 2 ;;
      --timeout) HEALTH_TIMEOUT="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) echo "[ERRO] Opção inválida: $1" >&2; usage; exit 1 ;;
    esac
  done
}

resolve_node_config() {
  if [[ -z "${NODE_INDEX}" ]]; then
    NODE_INDEX="$(detect_node_from_hostname)"
  fi

  if [[ -z "${NODE_INDEX}" ]]; then
    echo "[ERRO] Não foi possível detectar o nó automaticamente. Use --node 1|2|3." >&2
    exit 1
  fi

  case "${NODE_INDEX}" in
    1)
      NODE_ROLE="juiz"
      NODE_DIR="${ROOT_DIR}/node1-juiz"
      HEALTH_URL="http://127.0.0.1:7700/api/v1/health"
      ;;
    2)
      NODE_ROLE="bibliotecario"
      NODE_DIR="${ROOT_DIR}/node2-bibliotecario"
      HEALTH_URL="http://127.0.0.1:7710/api/v1/health"
      ;;
    3)
      NODE_ROLE="agentes"
      NODE_DIR="${ROOT_DIR}/node3-agentes"
      HEALTH_URL=""
      ;;
    *)
      echo "[ERRO] Nó inválido: ${NODE_INDEX}. Use 1, 2 ou 3." >&2
      exit 1
      ;;
  esac

  if [[ -z "${NODE_ENV_FILE}" ]]; then
    NODE_ENV_FILE="${ROOT_DIR}/deploy/env/node${NODE_INDEX}.env"
  fi

  if [[ ! -f "${NODE_ENV_FILE}" ]]; then
    echo "[ERRO] Arquivo de ambiente não encontrado: ${NODE_ENV_FILE}" >&2
    echo "Execute antes: ./scripts/setup_inicial.sh" >&2
    exit 1
  fi

  TMP_ENV_FILE="${NODE_DIR}/.env.runtime"
  cp "${NODE_ENV_FILE}" "${TMP_ENV_FILE}"
}

compose_cmd() {
  (cd "${NODE_DIR}" && docker compose --env-file "${TMP_ENV_FILE}" "$@")
}

cmd_start() {
  log "Iniciando nó ${NODE_INDEX} (${NODE_ROLE})..."
  "${DEPLOY_SCRIPT}" --node "${NODE_INDEX}" --env-file "${NODE_ENV_FILE}"
}

cmd_stop() {
  log "Parando nó ${NODE_INDEX} (${NODE_ROLE})..."
  compose_cmd down
}

cmd_restart() {
  cmd_stop
  cmd_start
}

cmd_status() {
  log "Status do nó ${NODE_INDEX} (${NODE_ROLE}):"
  compose_cmd ps
}

cmd_logs() {
  log "Logs centralizados do nó ${NODE_INDEX} (${NODE_ROLE}) [últimas ${LOG_LINES} linhas]:"
  compose_cmd logs --tail "${LOG_LINES}" --timestamps
}

cmd_health() {
  log "Executando health check do nó ${NODE_INDEX} (${NODE_ROLE})..."

  if [[ "${NODE_INDEX}" == "3" ]]; then
    # Nó de agentes não expõe HTTP próprio; valida via containers em execução
    local running
    running="$(compose_cmd ps --status running --services | wc -l | tr -d ' ')"
    if [[ "${running}" -ge 2 ]]; then
      echo "OK: ${running} serviços em execução no nó de agentes."
      return 0
    fi
    echo "FALHA: serviços insuficientes em execução no nó de agentes (${running})." >&2
    return 1
  fi

  if ! command -v curl >/dev/null 2>&1; then
    echo "[ERRO] curl não encontrado para health check." >&2
    return 1
  fi

  local http_code
  http_code="$(curl -sS -m "${HEALTH_TIMEOUT}" -o /tmp/enxame-health.out -w '%{http_code}' "${HEALTH_URL}" || true)"

  if [[ "${http_code}" == "200" ]]; then
    echo "OK: ${HEALTH_URL} respondeu 200"
    cat /tmp/enxame-health.out
    return 0
  fi

  echo "FALHA: health check retornou HTTP ${http_code} em ${HEALTH_URL}" >&2
  [[ -f /tmp/enxame-health.out ]] && cat /tmp/enxame-health.out >&2
  return 1
}

main() {
  if [[ -z "${ACTION}" ]]; then
    usage
    exit 1
  fi

  case "${ACTION}" in
    -h|--help) usage; exit 0 ;;
    start|stop|restart|status|logs|health) ;;
    *) echo "[ERRO] Ação inválida: ${ACTION}" >&2; usage; exit 1 ;;
  esac

  parse_args "$@"
  resolve_node_config

  case "${ACTION}" in
    start) cmd_start ;;
    stop) cmd_stop ;;
    restart) cmd_restart ;;
    status) cmd_status ;;
    logs) cmd_logs ;;
    health) cmd_health ;;
  esac
}

main "$@"
