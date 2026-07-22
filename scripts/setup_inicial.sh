#!/usr/bin/env bash
set -euo pipefail

# Gera configuração inicial do ENXAME para 3 nós:
# - segredo compartilhado HMAC
# - CA e certificados TLS por nó (air-gapped)
# - arquivos .env por nó

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/deploy"
EXP_SECRET_FILE="${OUT_DIR}/secrets/exp_shared_secret"
CERTS_DIR="${OUT_DIR}/certs"
ENVS_DIR="${OUT_DIR}/env"

NODE1_IP="192.168.1.10"
NODE2_IP="192.168.1.11"
NODE3_IP="192.168.1.12"
JUIZ_PORT="7700"
FORCE="0"

usage() {
  cat <<EOF
Uso: $(basename "$0") [opções]

Opções:
  --node1-ip <ip>      IP do nó 1 (Juiz). Padrão: ${NODE1_IP}
  --node2-ip <ip>      IP do nó 2 (Bibliotecário). Padrão: ${NODE2_IP}
  --node3-ip <ip>      IP do nó 3 (Agentes). Padrão: ${NODE3_IP}
  --juiz-port <porta>  Porta HTTP do Juiz. Padrão: ${JUIZ_PORT}
  --out-dir <path>     Diretório de saída. Padrão: ${OUT_DIR}
  --force              Regenera segredos/certificados já existentes
  -h, --help           Mostra esta ajuda

Exemplo:
  ./scripts/setup_inicial.sh --node1-ip 10.10.10.10 --node2-ip 10.10.10.11 --node3-ip 10.10.10.12
EOF
}

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --node1-ip) NODE1_IP="$2"; shift 2 ;;
    --node2-ip) NODE2_IP="$2"; shift 2 ;;
    --node3-ip) NODE3_IP="$2"; shift 2 ;;
    --juiz-port) JUIZ_PORT="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --force) FORCE="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERRO] Opção inválida: $1" >&2; usage; exit 1 ;;
  esac
done

EXP_SECRET_FILE="${OUT_DIR}/secrets/exp_shared_secret"
CERTS_DIR="${OUT_DIR}/certs"
ENVS_DIR="${OUT_DIR}/env"

validate_dependencies() {
  for cmd in openssl awk; do
    if ! command -v "${cmd}" >/dev/null 2>&1; then
      echo "[ERRO] Dependência não encontrada: ${cmd}" >&2
      exit 1
    fi
  done
}

prepare_dirs() {
  mkdir -p "${OUT_DIR}/secrets" "${CERTS_DIR}" "${ENVS_DIR}"
  chmod 700 "${OUT_DIR}/secrets" "${CERTS_DIR}" || true
}

generate_secret() {
  if [[ -f "${EXP_SECRET_FILE}" && "${FORCE}" != "1" ]]; then
    log "Segredo HMAC já existe em ${EXP_SECRET_FILE} (mantido)."
    return
  fi

  log "Gerando segredo compartilhado HMAC..."
  openssl rand -hex 32 > "${EXP_SECRET_FILE}"
  chmod 600 "${EXP_SECRET_FILE}"
}

generate_ca() {
  if [[ -f "${CERTS_DIR}/ca.crt" && -f "${CERTS_DIR}/ca.key" && "${FORCE}" != "1" ]]; then
    log "CA já existe em ${CERTS_DIR} (mantida)."
    return
  fi

  log "Gerando CA interna para rede air-gapped..."
  openssl genrsa -out "${CERTS_DIR}/ca.key" 4096
  openssl req -x509 -new -nodes \
    -key "${CERTS_DIR}/ca.key" \
    -sha256 -days 3650 \
    -subj "/C=BR/ST=MT/L=Cuiaba/O=ENXAME/OU=AirGapped/CN=enxame-ca" \
    -out "${CERTS_DIR}/ca.crt"
  chmod 600 "${CERTS_DIR}/ca.key"
  chmod 644 "${CERTS_DIR}/ca.crt"
}

issue_node_cert() {
  local node_name="$1"
  local node_ip="$2"
  local node_cn="$3"

  local key_file="${CERTS_DIR}/${node_name}.key"
  local csr_file="${CERTS_DIR}/${node_name}.csr"
  local crt_file="${CERTS_DIR}/${node_name}.crt"
  local ext_file="${CERTS_DIR}/${node_name}.ext"

  if [[ -f "${crt_file}" && -f "${key_file}" && "${FORCE}" != "1" ]]; then
    log "Certificado ${node_name} já existe (mantido)."
    return
  fi

  log "Gerando certificado TLS para ${node_name} (${node_ip})..."
  openssl genrsa -out "${key_file}" 2048

  cat > "${ext_file}" <<EOF
subjectAltName=DNS:${node_cn},DNS:${node_name},IP:${node_ip}
extendedKeyUsage=serverAuth,clientAuth
keyUsage=digitalSignature,keyEncipherment
EOF

  openssl req -new -key "${key_file}" \
    -subj "/C=BR/ST=MT/L=Cuiaba/O=ENXAME/CN=${node_cn}" \
    -out "${csr_file}"

  openssl x509 -req -in "${csr_file}" \
    -CA "${CERTS_DIR}/ca.crt" \
    -CAkey "${CERTS_DIR}/ca.key" \
    -CAcreateserial \
    -out "${crt_file}" \
    -days 825 -sha256 \
    -extfile "${ext_file}"

  rm -f "${csr_file}" "${ext_file}"
  chmod 600 "${key_file}"
  chmod 644 "${crt_file}"
}

generate_env_files() {
  local exp_secret
  exp_secret="$(<"${EXP_SECRET_FILE}")"

  local juiz_http_url="http://${NODE1_IP}:${JUIZ_PORT}"
  local juiz_ws_url="ws://${NODE1_IP}:${JUIZ_PORT}/exp"

  log "Gerando arquivos de ambiente por nó em ${ENVS_DIR}..."

  cat > "${ENVS_DIR}/node1.env" <<EOF
# ENXAME - Nó 1 (Juiz)
NODE_INDEX=1
NODE_ROLE=juiz
NODE_ID=juiz-01
NODE_IP=${NODE1_IP}
JUIZ_HOST_IP=${NODE1_IP}
ENXAME_JUIZ_URL=${juiz_http_url}
JUIZ_WS_URL=${juiz_ws_url}
EXP_SHARED_SECRET=${exp_secret}
TLS_CA_CERT=/etc/enxame/certs/ca.crt
TLS_CERT=/etc/enxame/certs/node1-juiz.crt
TLS_KEY=/etc/enxame/certs/node1-juiz.key
TZ=America/Cuiaba
EOF

  cat > "${ENVS_DIR}/node2.env" <<EOF
# ENXAME - Nó 2 (Bibliotecário)
NODE_INDEX=2
NODE_ROLE=bibliotecario
NODE_ID=bib-01
NODE_IP=${NODE2_IP}
JUIZ_HOST_IP=${NODE1_IP}
ENXAME_JUIZ_URL=${juiz_http_url}
JUIZ_WS_URL=${juiz_ws_url}
EXP_SHARED_SECRET=${exp_secret}
TLS_CA_CERT=/etc/enxame/certs/ca.crt
TLS_CERT=/etc/enxame/certs/node2-bibliotecario.crt
TLS_KEY=/etc/enxame/certs/node2-bibliotecario.key
TZ=America/Cuiaba
EOF

  cat > "${ENVS_DIR}/node3.env" <<EOF
# ENXAME - Nó 3 (Agentes)
NODE_INDEX=3
NODE_ROLE=agentes
NODE_ID=ag-dyn-cluster
NODE_IP=${NODE3_IP}
JUIZ_HOST_IP=${NODE1_IP}
ENXAME_JUIZ_URL=${juiz_http_url}
JUIZ_WS_URL=${juiz_ws_url}
EXP_SHARED_SECRET=${exp_secret}
TLS_CA_CERT=/etc/enxame/certs/ca.crt
TLS_CERT=/etc/enxame/certs/node3-agentes.crt
TLS_KEY=/etc/enxame/certs/node3-agentes.key
TZ=America/Cuiaba
EOF

  chmod 600 "${ENVS_DIR}"/*.env
}

summary() {
  cat <<EOF

Configuração inicial concluída.

Arquivos gerados:
- Segredo HMAC: ${EXP_SECRET_FILE}
- Certificados: ${CERTS_DIR}/ca.crt + node*.crt/node*.key
- Envs por nó: ${ENVS_DIR}/node1.env, node2.env, node3.env

Próximo passo em cada máquina:
1) Copiar o arquivo .env correspondente para o nó.
2) Copiar certificados para /etc/enxame/certs.
3) Executar ./scripts/deploy_3nos.sh (com auto detecção) no nó.
EOF
}

main() {
  validate_dependencies
  prepare_dirs
  generate_secret
  generate_ca

  issue_node_cert "node1-juiz" "${NODE1_IP}" "enxame-node1-juiz"
  issue_node_cert "node2-bibliotecario" "${NODE2_IP}" "enxame-node2-bibliotecario"
  issue_node_cert "node3-agentes" "${NODE3_IP}" "enxame-node3-agentes"

  generate_env_files
  summary
}

main "$@"
