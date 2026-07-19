#!/usr/bin/env bash
set -euo pipefail

# Bootstrap para Ubuntu/Xubuntu 22.04+
# Instala: Docker + Compose, Ollama, Python 3.11+, Redis e imagem Qdrant.

if [[ "${EUID}" -eq 0 ]]; then
  echo "[ERRO] Não execute como root. Use um usuário com sudo." >&2
  exit 1
fi

if ! command -v sudo >/dev/null 2>&1; then
  echo "[ERRO] sudo não encontrado. Instale o sudo e tente novamente." >&2
  exit 1
fi

if [[ ! -f /etc/os-release ]]; then
  echo "[ERRO] Não foi possível identificar o sistema operacional." >&2
  exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != "ubuntu" && "${ID_LIKE:-}" != *"ubuntu"* ]]; then
  echo "[AVISO] Sistema não identificado como Ubuntu/Xubuntu. Continuando por sua conta e risco..."
fi

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

install_base_packages() {
  log "Atualizando índice APT..."
  sudo apt-get update -y

  log "Instalando pacotes base..."
  sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    software-properties-common \
    apt-transport-https \
    jq \
    openssl \
    redis-server
}

ensure_python_311_plus() {
  local py_ok
  py_ok="$(python3 - <<'PY'
import sys
print('ok' if sys.version_info >= (3,11) else 'no')
PY
  )"

  if [[ "${py_ok}" == "ok" ]]; then
    log "Python $(python3 --version 2>/dev/null) já atende (>=3.11)."
  else
    log "Python >=3.11 não encontrado. Instalando python3.11..."
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update -y
    sudo apt-get install -y python3.11 python3.11-venv python3.11-dev

    if ! command -v python3.11 >/dev/null 2>&1; then
      echo "[ERRO] python3.11 não foi instalado corretamente." >&2
      exit 1
    fi

    log "Configurando python3.11 como alternativa para python3..."
    sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 2
  fi

  log "Instalando pip e venv para Python..."
  sudo apt-get install -y python3-pip python3-venv
}

install_docker() {
  if command -v docker >/dev/null 2>&1; then
    log "Docker já instalado: $(docker --version)"
  else
    log "Instalando Docker Engine via script oficial..."
    curl -fsSL https://get.docker.com | sudo sh
  fi

  log "Habilitando e iniciando Docker..."
  sudo systemctl enable --now docker

  if docker compose version >/dev/null 2>&1; then
    log "Docker Compose plugin já disponível: $(docker compose version)"
  else
    log "Instalando Docker Compose plugin..."
    sudo apt-get install -y docker-compose-plugin
  fi

  if ! groups "${USER}" | grep -q '\bdocker\b'; then
    log "Adicionando usuário ${USER} ao grupo docker..."
    sudo usermod -aG docker "${USER}"
    log "IMPORTANTE: faça logout/login após o bootstrap para usar Docker sem sudo."
  fi
}

install_ollama() {
  if command -v ollama >/dev/null 2>&1; then
    log "Ollama já instalado: $(ollama --version 2>/dev/null || true)"
  else
    log "Instalando Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
  fi

  log "Habilitando e iniciando serviço do Ollama..."
  sudo systemctl enable --now ollama || true
}

install_redis_qdrant_assets() {
  log "Habilitando Redis local..."
  sudo systemctl enable --now redis-server

  log "Pré-baixando imagens Docker de Redis e Qdrant..."
  sudo docker pull redis:7-alpine
  sudo docker pull qdrant/qdrant:v1.10.1
}

pull_ollama_models() {
  local models=("llama3" "gemma2:9b" "gemma2:2b-it-qat")
  for model in "${models[@]}"; do
    log "Baixando modelo Ollama: ${model}"
    ollama pull "${model}"
  done
}

main() {
  log "Iniciando bootstrap do ENXAME..."
  install_base_packages
  ensure_python_311_plus
  install_docker
  install_ollama
  install_redis_qdrant_assets
  pull_ollama_models

  log "Bootstrap concluído com sucesso."
  log "Valide com: docker --version && docker compose version && python3 --version && ollama list"
}

main "$@"
