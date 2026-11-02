#!/bin/bash
# =============================================================================
# ENXAME - Instalador Linux (Ubuntu/Debian e similares)
# =============================================================================
# Fluxo interativo:
#   1. Pergunta a pasta de instalação (padrão: /opt/enxame)
#   2. Pergunta se inicia junto ao boot (systemd)
#   3. Pergunta a função do node (via node_role_setup.py)
#   4. Instala o código, cria serviço em segundo plano e atalho na área de trabalho
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENXAME_ROOT="$(dirname "$SCRIPT_DIR")"

# Cores para terminal
C_RESET='\033[0m'
C_BOLD='\033[1m'
C_GREEN='\033[32m'
C_YELLOW='\033[33m'
C_BLUE='\033[34m'
C_RED='\033[31m'

echo ""
echo -e "${C_BOLD}╔═══════════════════════════════════════════════════════════════╗${C_RESET}"
echo -e "${C_BOLD}║         ENXAME - Instalador Linux (Ubuntu/Debian)            ║${C_RESET}"
echo -e "${C_BOLD}╚═══════════════════════════════════════════════════════════════╝${C_RESET}"
echo ""

# Verifica root
if [ "$EUID" -ne 0 ]; then
    echo -e "${C_RED}Erro: execute como root (sudo). Exemplo:${C_RESET}"
    echo "  sudo bash api/install/install-linux.sh"
    exit 1
fi

# Detecta ambiente de desktop para criar atalho
DESKTOP_ENV=""
if [ -n "$XDG_CURRENT_DESKTOP" ]; then
    DESKTOP_ENV="$XDG_CURRENT_DESKTOP"
elif [ -n "$DESKTOP_SESSION" ]; then
    DESKTOP_ENV="$DESKTOP_SESSION"
fi

# ---------------------------------------------------------------------------
# PASSO 1: Perguntar a pasta de instalação
# ---------------------------------------------------------------------------
echo -e "${C_BLUE}>>> PASSO 1/6: Pasta de instalação${C_RESET}"
echo ""
DEFAULT_INSTALL_DIR="/opt/enxame"
read -r -p "Onde deseja instalar o Enxame? [${DEFAULT_INSTALL_DIR}]: " INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"
# Remove barra final
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

# Cria a pasta de instalação
mkdir -p "$INSTALL_DIR"

# Copia o repositório para a pasta de instalação (excluindo .git e venv)
echo "Copiando arquivos do Enxame para $INSTALL_DIR..."
rsync -a --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
    "$ENXAME_ROOT/" "$INSTALL_DIR/" 2>/dev/null || \
    cp -r "$ENXAME_ROOT/." "$INSTALL_DIR/"
echo "  ✓ Arquivos copiados"

# Diretórios de dados, logs e config (fora da pasta de código, para preservar em updates)
DATA_DIR="/var/lib/enxame/data"
LOG_DIR="/var/log/enxame"
CONFIG_DIR="/etc/enxame"

mkdir -p "$DATA_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$CONFIG_DIR"
echo "  ✓ Diretórios de sistema criados:"
echo "       Dados:   $DATA_DIR"
echo "       Logs:    $LOG_DIR"
echo "       Config:  $CONFIG_DIR"

# Permissões
chown -R root:root "$INSTALL_DIR" "$DATA_DIR" "$LOG_DIR" "$CONFIG_DIR"
chmod 755 "$INSTALL_DIR" "$DATA_DIR" "$LOG_DIR" "$CONFIG_DIR"
chmod +x "$INSTALL_DIR/api/install/run_node.py"
chmod +x "$INSTALL_DIR/api/install/node_role_setup.py"
echo "  ✓ Permissões configuradas"

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

# Banco de dados inicial
DB_PATH="$DATA_DIR/enxame.db"
if [ ! -f "$DB_PATH" ]; then
    touch "$DB_PATH"
    chmod 644 "$DB_PATH"
    echo "  ✓ Banco de dados inicial criado em $DB_PATH"
fi

# ---------------------------------------------------------------------------
# PASSO 6: Serviço systemd (segundo plano + boot) e atalho da área de trabalho
# ---------------------------------------------------------------------------
echo ""
echo -e "${C_BLUE}>>> PASSO 6/6: Serviço em segundo plano e atalho${C_RESET}"
echo ""

SERVICE_FILE="/etc/systemd/system/enxame.service"
ENV_FOR_SERVICE="$ENV_FILE"

# Porta baseada no role
case "$NODE_ROLE" in
    juiz)      NODE_PORT=7700 ;;
    bibliotecario) NODE_PORT=7701 ;;
    *)         NODE_PORT=0 ;;
esac

cat > "$SERVICE_FILE" <<EOFUNIT
[Unit]
Description=Enxame Node ($NODE_ROLE)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$ENV_FOR_SERVICE
ExecStart=/usr/bin/env python3 $INSTALL_DIR/api/install/run_node.py --env-file $ENV_FOR_SERVICE
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOFUNIT

chmod 644 "$SERVICE_FILE"

if command -v systemctl &>/dev/null; then
    systemctl daemon-reload
    systemctl enable enxame.service >/dev/null 2>&1 || true
    if [ "$ENABLE_BOOT" = "true" ]; then
        echo "  ✓ Serviço systemd criado e configurado para iniciar junto ao boot."
    else
        echo "  ✓ Serviço systemd criado (não iniciará junto ao boot por sua opção)."
    fi
    systemctl start enxame.service || true
    echo "  ✓ Serviço iniciado em segundo plano."
else
    echo "  ! systemctl não disponível. Serviço não instalado via systemd."
fi

# Atalho na área de trabalho (Linux .desktop)
DESKTOP_DIR=""
if [ -n "$SUDO_USER" ]; then
    DESKTOP_DIR=$(getent passwd "$SUDO_USER" | cut -d: -f6)/Desktop
else
    DESKTOP_DIR="$HOME/Desktop"
fi
mkdir -p "$DESKTOP_DIR"

SHORTCUT="$DESKTOP_DIR/Enxame.desktop"
cat > "$SHORTCUT" <<EOFSHORTCUT
[Desktop Entry]
Name=Enxame
GenericName=Enxame - IA Descentralizada
Comment=Reiniciar serviço e abrir o Enxame no navegador
Exec=$INSTALL_DIR/api/install/enxame-desktop $INSTALL_DIR $ENV_FILE
Icon=$INSTALL_DIR/web/icon.svg
Terminal=false
Type=Application
Categories=Network;WebBrowser;
StartupNotify=true
EOFSHORTCUT

chmod +x "$SHORTCUT"
# Tenta definir ícone se existir
if [ -f "$INSTALL_DIR/web/icon.png" ]; then
    chmod 644 "$INSTALL_DIR/web/icon.png"
fi
echo "  ✓ Atalho criado na área de trabalho: $SHORTCUT"

# Script wrapper do atalho (verifica processo e abre navegador na Web UI, porta 8765)
cat > "$INSTALL_DIR/api/install/enxame-desktop" <<EOFDESKTOP
#!/bin/bash
# =============================================================================
# ENXAME - Atalho da Área de Trabalho
# Ao duplo-clicar: inicia/reinicia o kernel Enxame (porta 8765, Web UI)
# e abre o navegador. Se já estiver rodando, apenas abre o navegador.
# =============================================================================
set -e

INSTALL_DIR="$1"
ENV_FILE="$2"

if [ -z "$INSTALL_DIR" ]; then
    INSTALL_DIR="/opt/enxame"
fi
if [ -z "$ENV_FILE" ]; then
    ENV_FILE="/etc/enxame/.env"
fi

# Porta da Web UI (kernel evoluído, servida por run_enxame.py)
PORT="8765"
URL="http://localhost:\${PORT}/"

# Tenta detectar o navegador padrão
BROWSER="xdg-open"
if command -v xdg-open &>/dev/null; then
    BROWSER="xdg-open"
elif command -v sensible-browser &>/dev/null; then
    BROWSER="sensible-browser"
elif command -v firefox &>/dev/null; then
    BROWSER="firefox"
elif command -v chromium-browser &>/dev/null; then
    BROWSER="chromium-browser"
elif command -v google-chrome &>/dev/null; then
    BROWSER="google-chrome"
fi

# Se o kernel não estiver rodando, inicia em segundo plano (nohup)
if ! pgrep -f "run_enxame.py" >/dev/null 2>&1; then
    echo "Iniciando o Enxame em segundo plano (Web UI em $URL)..."
    nohup /usr/bin/env python3 "$INSTALL_DIR/run_enxame.py" \
        --no-browser >"$INSTALL_DIR/enxame-nohup.log" 2>&1 &
    # Aguarda ficar pronto (até 30s)
    for i in \$(seq 1 30); do
        if curl -s --max-time 1 http://localhost:\${PORT}/health >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
else
    echo "Enxame já está rodando em segundo plano."
fi

# Abre o navegador na Web UI
if command -v "\$BROWSER" &>/dev/null; then
    "\$BROWSER" "\$URL" &
else
    echo "Não foi possível detectar um navegador. Acesse manualmente: $URL"
fi

exit 0
EOFDESKTOP
chmod +x "$INSTALL_DIR/api/install/enxame-desktop"

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
echo "  • Serviço em segundo plano: ativo (systemd)"
echo ""
echo "Como usar:"
echo "  • Duplo-clique no atalho 'Enxame' na área de trabalho para"
echo "    iniciar/reiniciar o serviço e abrir o navegador."
echo "  • Acesse também em: http://localhost:7700/  (ou :7701 para Bibliotecário)"
echo ""
echo "Para desinstalar:"
echo "  sudo bash api/install/uninstall"
echo ""
