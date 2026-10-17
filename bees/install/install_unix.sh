#!/usr/bin/env bash
# ============================================================
# Instalador Enxame - macOS / Linux (next-next-finish)
# ============================================================
set -euo pipefail

ENXAME_DIR="$HOME/enxame"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENXAME_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "============================================================"
echo "  Instalador Enxame - IA de enxame para maquinas antigas"
echo "============================================================"
echo

# Verificar Python
if ! command -v python3 &>/dev/null; then
    echo "[!] Python3 nao encontrado."
    echo "    Instale o Python 3.10+ e tente novamente."
    exit 1
fi
echo "[OK] Python3 encontrado: $(python3 --version)"

# Diretorio de instalacao
mkdir -p "$ENXAME_DIR"
echo "[OK] Diretorio: $ENXAME_DIR"

# Instalar dependencias
echo
echo "[.] Instalando dependencias (pip)... isso pode demorar."
python3 -m pip install -r "$ENXAME_ROOT/requirements.txt"
echo "[OK] Dependencias instaladas."

# Perguntar papel do no
echo
echo "Escolha o papel deste computador:"
echo "  1) Juiz (coordenador - fica ligado, distribui trabalho)"
echo "  2) Agente (trabalhador - ajuda o Juiz nas tarefas)"
read -rp "Digite 1 ou 2 [2]: " ROLE
ROLE="${ROLE:-2}"
if [ "$ROLE" = "1" ]; then ROLE="juiz"; else ROLE="agente"; fi

# Criar node.toml (politica de doacao)
echo
echo "[.] Criando configuracao de doacao..."
cat > "$ENXAME_DIR/node.toml" <<EOF
[donation]
enabled = true
max_cpu_pct = 70
min_free_ram_gb = 1.5
max_concurrent = 1
run_when = "idle"
pause_on_battery = true
EOF
echo "[OK] Configuracao criada em $ENXAME_DIR/node.toml"

# Criar scripts de inicio
echo
echo "[.] Criando scripts de inicio..."
cat > "$ENXAME_DIR/iniciar_juiz.sh" <<EOF
#!/usr/bin/env bash
export ENXAME_ROOT="$ENXAME_ROOT"
export NODE_ID=juiz-01
export JUIZ_URL=ws://localhost:7700/exp
export JUIZ_HTTP_URL=http://localhost:7700
exec python3 -m juiz
EOF
chmod +x "$ENXAME_DIR/iniciar_juiz.sh"

cat > "$ENXAME_DIR/iniciar_agente.sh" <<EOF
#!/usr/bin/env bash
export ENXAME_ROOT="$ENXAME_ROOT"
export NODE_ID=ag-\$(hostname)
export JUIZ_URL=ws://localhost:7700/exp
export JUIZ_HTTP_URL=http://localhost:7700
exec python3 -m agentes
EOF
chmod +x "$ENXAME_DIR/iniciar_agente.sh"
echo "[OK] Scripts criados."

echo
echo "============================================================"
echo "  Instalacao concluida!"
echo "============================================================"
echo
echo "Para iniciar o Juiz:  bash $ENXAME_DIR/iniciar_juiz.sh"
echo "Para iniciar um Agente: bash $ENXAME_DIR/iniciar_agente.sh"
echo "Acesse a UI em:       http://localhost:7700"
echo
