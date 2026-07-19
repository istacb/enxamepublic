#!/usr/bin/env bash
set -euo pipefail

NODE_TYPE="${1:-all}"

pull_juiz() {
  echo "[juiz] baixando llama3"
  docker exec ollama-juiz ollama pull llama3
}

pull_bibliotecario() {
  echo "[bibliotecario] baixando gemma2:9b"
  docker exec ollama-bibliotecario ollama pull gemma2:9b
}

pull_agentes() {
  echo "[agentes] baixando gemma2:2b-it-qat"
  docker exec ollama-agentes ollama pull gemma2:2b-it-qat
}

case "$NODE_TYPE" in
  juiz)
    pull_juiz
    ;;
  bibliotecario)
    pull_bibliotecario
    ;;
  agentes)
    pull_agentes
    ;;
  all)
    pull_juiz
    pull_bibliotecario
    pull_agentes
    ;;
  *)
    echo "Uso: $0 [juiz|bibliotecario|agentes|all]"
    exit 1
    ;;
esac
