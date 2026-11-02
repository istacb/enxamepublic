#!/bin/bash
# =============================================================================
# ENXAME - Instalador macOS
# =============================================================================
# Fluxo interativo:
#   1. Pergunta a pasta de instalação (padrão: /Applications/Enxame)
#   2. Pergunta se inicia junto ao boot (LaunchAgent)
#   3. Pergunta a função do node
#   4. Instala o código, cria serviço em segundo plano e atalho na área de trabalho
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENXAME_ROOT="$(dirname "$SCRIPT_DIR")"

C_RESET='\033[0m'
C_BOLD='\033[1m'
C_GREEN='\033[32m'
C_YELLOW='\033[33m'
C_BLUE='\033[34m'
C_RED='\033[31m'

echo ""
echo -e "${C_BOLD}╔═══════════════════════════════════════════════════════════════╗${C_RESET}"
echo -e "${C_BOLD}║           ENXAME - Instalador macOS                          ║${C_RESET}"
echo -e "${C_BOLD}╚═══════════════════════════════════════════════════════════════╝${C_RESET}"
echo ""

# Verifica sudo (macOS precisa de root para /Applications e /etc)
if [ "$EUID" -ne 0 ]; then
    echo -e "${C_RED}Erro: execute com sudo. Exemplo:${C_RESET}"
    echo "  sudo bash api/install/install-macos.sh"
    exit 1
fi

# Detecta o usuário real que executou o sudo (para área de trabalho e LaunchAgent)
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)
DESKTOP_DIR="$REAL_HOME/Desktop"
LAUNCHAGENTS_DIR="$REAL_HOME/Library/LaunchAgents"

# ---------------------------------------------------------------------------
# PASSO 1: Perguntar a pasta de instalação
# ---------------------------------------------------------------------------
echo -e "${C_BLUE}>>> PASSO 1/6: Pasta de instalação${C_RESET}"
echo ""
DEFAULT_INSTALL_DIR="/Applications/Enxame"
read -r -p "Onde deseja instalar o Enxame? [${DEFAULT_INSTALL_DIR}]: " INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"
INSTALL_DIR="${INSTALL_DIR%/}"
echo ""
echo -e "${C_GREEN}Pasta de instalação: ${INSTALL_DIR}${C_RESET}"
echo ""

# ---------------------------------------------------------------------------
# PASSO 2: Perguntar iniciar junto ao boot
# ---------------------------------------------------------------------------
echo -e "${C_BLUE}>>> PASSO 2/6: Iniciar junto ao boot${C_RESET}"
echo ""
echo "Deseja que o Enxame inicie automaticamente junto ao boot da máquina?"
echo "  [s] Sim - inicia sozinho sempre que ligar o computador (recomendado)"
echo "  [n] Não - você iniciará manualmente ou pelo atalho da área de trabalho"
read -r -p "Opção (s/n) [padrão: s]: " START_ON_BOOT
START_ON_BOOT="${START_ON_BOOT:-s}"
START_ON_BOOT_LOWER="$(echo "$START_ON_BOOT" | tr '[:upper:]' '[:lower:]')"
if [ "$START_ON_BOOT_LOWER" = "s" ] || [ "$START_ON_BOOT_LOWER" = "sim" ] || [ "$START_ON_BOOT_LOWER" = "y" ] || [ "$START_ON_BOOT_LOWER" = "yes" ]; then
    ENABLE_BOOT="true"
else
    ENABLE_BOOT="false"
fi
echo ""
if [ "$ENABLE_BOOT" = "true" ]; then
    echo -e "${C_GREEN}Iniciar junto ao boot: SIM${C_RESET}"
else
    echo -e "${C_YELLOW}Iniciar junto ao boot: NÃO${C_RESET}"
fi
echo ""

# ---------------------------------------------------------------------------
# PASSO 3: Perguntar role do node
# ---------------------------------------------------------------------------
echo -e "${C_BLUE}>>> PASSO 3/6: Função do node${C_RESET}"
echo ""
echo "Qual a função inicial deste node?"
echo "  [1] Juiz         - orquestração, validação e auditoria (porta 7700)"
echo "  [2] Bibliotecário - busca e gestão de conhecimento (porta 7701)"
echo "  [3] Agente        - worker com todas as especialidades"
echo "  [4] Automático    - deixar o Enxame decidir pelo hardware"
read -r -p "Escolha (1-4) [padrão: 4]: " ROLE_CHOICE
ROLE_CHOICE="${ROLE_CHOICE:-4}"
case "$ROLE_CHOICE" in
    1) NODE_ROLE="juiz" ;;
    2) NODE_ROLE="bibliotecario" ;;
    3) NODE_ROLE="agente" ;;
    4) NODE_ROLE="auto" ;;
    *) NODE_ROLE="auto" ;;
esac
echo ""
echo -e "${C_GREEN}Função do node: ${NODE_ROLE}${C_RESET}"
echo ""

# ---------------------------------------------------------------------------
# PASSO 4: Preparar diretórios e copiar código
# ---------------------------------------------------------------------------
echo -e "${C_BLUE}>>> PASSO 4/6: Instalando arquivos${C_RESET}"
echo ""

mkdir -p "$INSTALL_DIR"
echo "Copiando arquivos do Enxame para $INSTALL_DIR..."
rsync -a --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
    "$ENXAME_ROOT/" "$INSTALL_DIR/" 2>/dev/null || \
    cp -r "$ENXAME_ROOT/." "$INSTALL_DIR/"
echo "  ✓ Arquivos copiados"

DATA_DIR="$REAL_HOME/Library/Application Support/Enxame/data"
LOG_DIR="$REAL_HOME/Library/Logs/Enxame"
CONFIG_DIR="$REAL_HOME/Library/Preferences/Enxame"

mkdir -p "$DATA_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$CONFIG_DIR"
chown -R "$REAL_USER:staff" "$INSTALL_DIR" "$DATA_DIR" "$LOG_DIR" "$CONFIG_DIR" 2>/dev/null || true
echo "  ✓ Diretórios de sistema criados:"
echo "       Dados:   $DATA_DIR"
echo "       Logs:    $LOG_DIR"
echo "       Config:  $CONFIG_DIR"

# ---------------------------------------------------------------------------
# PASSO 5: Criar arquivo .env
# ---------------------------------------------------------------------------
echo ""
echo -e "${C_BLUE}>>> PASSO 5/6: Configuração (.env)${C_RESET}"
echo ""

ENV_FILE="$CONFIG_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    echo "  ! Arquivo .env já existe. Mantendo valores existentes."
else
    cat > "$ENV_FILE" <<EOF
# Configuração do Enxame
ENXAME_ENV=production
ENXAME_HOST=0.0.0.0
ENXAME_INSTALL_DIR=$INSTALL_DIR
ENXAME_DATA_PATH=$DATA_DIR
ENXAME_LOG_PATH=$LOG_DIR
ENXAME_NODE_ROLE=$NODE_ROLE
OLLAMA_URL=http://localhost:11434
EOF
    echo "  ✓ Arquivo .env criado em $ENV_FILE"
fi
chmod 644 "$ENV_FILE"
chown "$REAL_USER:staff" "$ENV_FILE" 2>/dev/null || true

DB_PATH="$DATA_DIR/enxame.db"
if [ ! -f "$DB_PATH" ]; then
    touch "$DB_PATH"
    chmod 644 "$DB_PATH"
    chown "$REAL_USER:staff" "$DB_PATH" 2>/dev/null || true
    echo "  ✓ Banco de dados inicial criado em $DB_PATH"
fi

# ---------------------------------------------------------------------------
# PASSO 6: LaunchAgent (segundo plano + boot) e atalho da área de trabalho
# ---------------------------------------------------------------------------
echo ""
echo -e "${C_BLUE}>>> PASSO 6/6: Serviço em segundo plano e atalho${C_RESET}"
echo ""

case "$NODE_ROLE" in
    juiz)      NODE_PORT=7700 ;;
    bibliotecario) NODE_PORT=7701 ;;
    *)         NODE_PORT=0 ;;
esac

PLIST_FILE="$LAUNCHAGENTS_DIR/com.enxame.app.plist"
mkdir -p "$LAUNCHAGENTS_DIR"

cat > "$PLIST_FILE" <<EOFPLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.enxame.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$INSTALL_DIR/run_enxame.py</string>
        <string>--no-browser</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>
    <key>RunAtLoad</key>
    <$([ "$ENABLE_BOOT" = "true" ] && echo "true" || echo "false")/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/enxame.out.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/enxame.err.log</string>
</dict>
</plist>
EOFPLIST

chown "$REAL_USER:staff" "$PLIST_FILE" 2>/dev/null || true
chmod 644 "$PLIST_FILE"

# Carrega o LaunchAgent como o usuário real (não root)
if command -v launchctl &>/dev/null; then
    su - "$REAL_USER" -c "launchctl load '$PLIST_FILE' 2>/dev/null || true" || true
    if [ "$ENABLE_BOOT" = "true" ]; then
        echo "  ✓ LaunchAgent criado e configurado para iniciar junto ao boot."
    else
        echo "  ✓ LaunchAgent criado (não iniciará junto ao boot por sua opção)."
    fi
    su - "$REAL_USER" -c "launchctl start com.enxame.app 2>/dev/null || true" || true
    echo "  ✓ Serviço iniciado em segundo plano."
else
    echo "  ! launchctl não disponível."
fi

# Atalho na área de trabalho (macOS .app wrapper)
mkdir -p "$DESKTOP_DIR"
SHORTCUT="$DESKTOP_DIR/Enxame.app"
APP_CONTENTS="$SHORTCUT/Contents"
MACOS_DIR="$APP_CONTENTS/MacOS"
RESOURCES_DIR="$APP_CONTENTS/Resources"

rm -rf "$SHORTCUT"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"

# Info.plist do app
cat > "$APP_CONTENTS/Info.plist" <<'APPINFO'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Enxame</string>
    <key>CFBundleDisplayName</key>
    <string>Enxame</string>
    <key>CFBundleIdentifier</key>
    <string>com.enxame.app</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
APPINFO

# Script executável do app
cat > "$MACOS_DIR/Enxame" <<APPEXEC
#!/bin/bash
INSTALL_DIR="$INSTALL_DIR"
ENV_FILE="$ENV_FILE"
PORT="8765"
URL="http://localhost:\${PORT}/"

# Se o LaunchAgent não estiver rodando, inicia
if command -v launchctl &>/dev/null; then
    if ! su - "$REAL_USER" -c "launchctl list com.enxame.app 2>/dev/null | grep -q com.enxame.app"; then
        echo "Iniciando o Enxame em segundo plano..."
        su - "$REAL_USER" -c "launchctl start com.enxame.app 2>/dev/null || true" || true
        for i in \$(seq 1 30); do
            if curl -s --max-time 1 "http://localhost:\${PORT}/health" >/dev/null 2>&1; then
                break
            fi
            sleep 1
        done
    fi
else
    if ! pgrep -f "run_enxame.py" >/dev/null 2>&1; then
        nohup /usr/bin/python3 "$INSTALL_DIR/run_enxame.py" --no-browser >"$LOG_DIR/enxame-nohup.log" 2>&1 &
        for i in \$(seq 1 30); do
            if curl -s --max-time 1 "http://localhost:\${PORT}/health" >/dev/null 2>&1; then
                break
            fi
            sleep 1
        done
    fi
fi

open "\$URL"
exit 0
APPEXEC

chmod +x "$MACOS_DIR/Enxame"
chown -R "$REAL_USER:staff" "$SHORTCUT" 2>/dev/null || true
echo "  ✓ Atalho criado na área de trabalho: $SHORTCUT"

echo ""
echo -e "${C_GREEN}╔═══════════════════════════════════════════════════════════════╗${C_RESET}"
echo -e "${C_GREEN}║           INSTALAÇÃO CONCLUÍDA COM SUCESSO!                  ║${C_RESET}"
echo -e "${C_GREEN}╚═══════════════════════════════════════════════════════════════╝${C_RESET}"
echo ""
echo "Resumo da instalação:"
echo "  • Pasta de instalação: $INSTALL_DIR"
echo "  • Dados:               $DATA_DIR"
echo "  • Config:              $ENV_FILE"
echo "  • Logs:                $LOG_DIR"
echo "  • Função do node:      $NODE_ROLE"
echo "  • Iniciar junto ao boot: $([ "$ENABLE_BOOT" = "true" ] && echo "SIM" || echo "NÃO")"
echo "  • Serviço em segundo plano: ativo (LaunchAgent)"
echo ""
echo "Como usar:"
echo "  • Duplo-clique no app 'Enxame' na área de trabalho para"
echo "    iniciar/reiniciar o serviço e abrir o navegador."
echo "  • Acesse também em: http://localhost:8765/ (Web UI)"
echo ""
echo "Para desinstalar:"
echo "  sudo bash api/install/uninstall"
echo ""
