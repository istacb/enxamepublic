#!/bin/bash
# ============================================================================
# ENXAME v3 - bootstrap_node.sh
# Roda em QUALQUER máquina (Linux nativo ou WSL2). Idempotente: pode rodar
# de novo a qualquer momento, só instala o que estiver faltando.
#
# Uso:
#   ./bootstrap_node.sh --juiz 192.168.1.30 --perfil worker_engenharia
#   ./bootstrap_node.sh --juiz 192.168.1.30 --perfil worker_contabil
#   ./bootstrap_node.sh --juiz 192.168.1.30 --perfil artista_midia
#   ./bootstrap_node.sh --juiz 192.168.1.30 --perfil bibliotecario
#   ./bootstrap_node.sh --perfil juiz                    (configura este nó como Juiz)
# ============================================================================
set -e

JUIZ_IP=""
PERFIL=""
ENXAME_DIR="$HOME/enxame"
FORCAR_MODELO=""
FORCAR_MODELO_VISAO=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --juiz) JUIZ_IP="$2"; shift 2 ;;
    --perfil) PERFIL="$2"; shift 2 ;;
    --modelo) FORCAR_MODELO="$2"; shift 2 ;;
    --modelo-visao) FORCAR_MODELO_VISAO="$2"; shift 2 ;;
    *) shift ;;
  esac
done

PERFIS_VALIDOS="juiz bibliotecario worker_engenharia worker_contabil artista_midia"
if [ -z "$PERFIL" ] || ! echo "$PERFIS_VALIDOS" | grep -qw "$PERFIL"; then
  echo "Uso: $0 [--juiz <IP>] --perfil <juiz|bibliotecario|worker_engenharia|worker_contabil|artista_midia>"
  exit 1
fi
if [ "$PERFIL" != "juiz" ] && [ -z "$JUIZ_IP" ]; then
  echo "Perfis que não são 'juiz' precisam de --juiz <IP_DO_JUIZ>"
  exit 1
fi

VERDE='\033[0;32m'; AMARELO='\033[1;33m'; VERMELHO='\033[0;31m'; AZUL='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${AZUL}[INFO]${NC} $1"; }
ok()   { echo -e "${VERDE}[OK]${NC} $1"; }
warn() { echo -e "${AMARELO}[AVISO]${NC} $1"; }
err()  { echo -e "${VERMELHO}[ERRO]${NC} $1"; }

log "========================================================"
log " ENXAME v3 - Bootstrap deste nó"
log " Perfil: $PERFIL | Juiz: ${JUIZ_IP:-'(este nó)'}"
log "========================================================"

mkdir -p "$ENXAME_DIR"/{data/kb_geral,data/kb_engenharia,data/kb_contabil,data/kb_midia,data/acervo,logs,venv}

# ---------------------------------------------------------------------------
# 1) BENCHMARK DE HARDWARE (idempotente: só mede, não instala nada aqui)
# ---------------------------------------------------------------------------
log "[1/8] Medindo capacidade de hardware..."

SO="$(uname -s)"
EH_MACOS=0
[ "$SO" = "Darwin" ] && EH_MACOS=1

if [ "$EH_MACOS" = "1" ]; then
  CPUS=$(sysctl -n hw.ncpu 2>/dev/null || echo 2)
  RAM_MB=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 2147483648) / 1024 / 1024 ))
else
  CPUS=$(nproc 2>/dev/null || echo 2)
  RAM_MB=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}'); [ -z "$RAM_MB" ] && RAM_MB=2048
fi

TEM_GPU_NVIDIA=0; GPU_VRAM_MB=0
if command -v nvidia-smi &>/dev/null; then
  TEM_GPU_NVIDIA=1
  GPU_VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
fi
EH_WSL2=0; grep -qi microsoft /proc/version 2>/dev/null && EH_WSL2=1

# Nota: Macs Intel (como este MacBookPro8,1) não têm GPU compatível com
# Ollama -- ele roda 100% via CPU nessas máquinas. Macs Apple Silicon (M1+)
# teriam aceleração via Metal, mas a detecção de GPU acima é só pra NVIDIA
# (Linux/Windows); em Mac tratamos como CPU-only por segurança.
SCORE=$(( CPUS*4 + RAM_MB/512 ))
[ "$TEM_GPU_NVIDIA" = "1" ] && SCORE=$((SCORE + 40 + GPU_VRAM_MB/500))
log "  SO: $SO | CPUs: $CPUS | RAM: ${RAM_MB}MB | GPU: $TEM_GPU_NVIDIA (VRAM ${GPU_VRAM_MB}MB) | WSL2: $EH_WSL2 | Score: $SCORE"

# ---------------------------------------------------------------------------
# 2) OLLAMA (idempotente: só instala se faltar)
# ---------------------------------------------------------------------------
log "[2/8] Verificando Ollama..."

OLLAMA_URL_LOCAL="http://localhost:11434"

if [ "$EH_WSL2" = "1" ]; then
  IP_WINDOWS=$(ip route | grep default | awk '{print $3}')
  warn "WSL2 detectado. Usando Ollama nativo do Windows em $IP_WINDOWS:11434 (rode windows_ollama_setup.ps1 lá se ainda não fez)."
  OLLAMA_URL_LOCAL="http://$IP_WINDOWS:11434"
elif [ "$EH_MACOS" = "1" ]; then
  if ! command -v brew &>/dev/null; then
    log "Homebrew não encontrado. Instalando (precisa de internet e pode pedir confirmação)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || \
      warn "Instalação do Homebrew falhou ou precisou de interação manual. Rode manualmente se necessário: https://brew.sh"
    # Homebrew em Mac Intel fica em /usr/local, em Apple Silicon em /opt/homebrew
    eval "$(/usr/local/bin/brew shellenv 2>/dev/null || /opt/homebrew/bin/brew shellenv 2>/dev/null)"
  else
    ok "Homebrew já instalado."
  fi

  if ! command -v ollama &>/dev/null; then
    log "Instalando Ollama via Homebrew..."
    brew install ollama || warn "Falha ao instalar Ollama via brew. Instale manualmente: https://ollama.com/download/mac"
  else
    ok "Ollama já instalado."
  fi

  log "Iniciando Ollama como serviço (brew services -- reinicia sozinho no login)..."
  brew services start ollama 2>/dev/null || nohup ollama serve > "$ENXAME_DIR/logs/ollama.log" 2>&1 &
  sleep 2
else
  if ! command -v ollama &>/dev/null; then
    log "Instalando Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
  else
    ok "Ollama já instalado."
  fi
  if ! pgrep -f "ollama serve" >/dev/null; then
    nohup ollama serve > "$ENXAME_DIR/logs/ollama.log" 2>&1 &
    sleep 2
  fi
fi

# ---------------------------------------------------------------------------
# 3) ESCOLHA DE MODELO(S) -- REAPROVEITA O QUE JÁ EXISTE ANTES DE BAIXAR NOVO
# ---------------------------------------------------------------------------
# Regra pedida: se a máquina JÁ tem algum modelo (de uma configuração
# anterior, ou baixado manualmente), usar esse -- nunca baixar outro por
# cima. Isso também resolve o caso de workers sem internet: eles não
# conseguem baixar nada mesmo, então o que já está instalado localmente é
# a única fonte possível.
log "[3/8] Escolhendo modelo(s) para o perfil '$PERFIL'..."

MODELOS_JA_INSTALADOS=""
if [ "$EH_WSL2" != "1" ]; then
  MODELOS_JA_INSTALADOS=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}')
fi

primeiro_modelo_de_texto_existente() {
  # Ignora modelos de embedding/visão na hora de escolher um modelo de TEXTO
  echo "$MODELOS_JA_INSTALADOS" | grep -vi -E "embed|llava|moondream|bakllava" | head -1
}

escolher_modelo_texto() {
  if [ -n "$FORCAR_MODELO" ]; then echo "$FORCAR_MODELO"; return; fi
  local existente
  existente=$(primeiro_modelo_de_texto_existente)
  if [ -n "$existente" ]; then echo "$existente"; return; fi
  if [ "$TEM_GPU_NVIDIA" = "1" ] && [ "${GPU_VRAM_MB:-0}" -ge 4000 ] 2>/dev/null; then echo "qwen2.5:7b";
  elif [ "$TEM_GPU_NVIDIA" = "1" ] || [ "$SCORE" -ge 60 ]; then echo "qwen2.5:3b";
  elif [ "$SCORE" -ge 35 ]; then echo "qwen2.5:1.5b";
  else echo "qwen2.5:0.5b"; fi
}

escolher_modelo_visao() {
  if [ -n "$FORCAR_MODELO_VISAO" ]; then echo "$FORCAR_MODELO_VISAO"; return; fi
  local existente
  existente=$(echo "$MODELOS_JA_INSTALADOS" | grep -i -E "llava|moondream|bakllava" | head -1)
  if [ -n "$existente" ]; then echo "$existente"; return; fi
  if [ "${GPU_VRAM_MB:-0}" -ge 6000 ] 2>/dev/null; then echo "llava:13b";
  elif [ "$TEM_GPU_NVIDIA" = "1" ] || [ "$SCORE" -ge 60 ]; then echo "llava:7b";
  else echo "moondream"; fi
}

escolher_modelo_embedding() {
  local existente
  existente=$(echo "$MODELOS_JA_INSTALADOS" | grep -i "embed" | head -1)
  if [ -n "$existente" ]; then echo "$existente"; return; fi
  echo "nomic-embed-text"
}

MODELO=$(escolher_modelo_texto)
MODELO_VISAO=""
[ "$PERFIL" = "artista_midia" ] && MODELO_VISAO=$(escolher_modelo_visao)
MODELO_EMBEDDING="nomic-embed-text"
[ "$PERFIL" = "bibliotecario" ] && MODELO_EMBEDDING=$(escolher_modelo_embedding)

if echo "$MODELOS_JA_INSTALADOS" | grep -qw "$MODELO"; then
  ok "Modelo de texto: $MODELO (já estava instalado nesta máquina, reaproveitado)"
else
  ok "Modelo de texto: $MODELO (será baixado, se houver internet)"
fi
[ -n "$MODELO_VISAO" ] && ok "Modelo de visão (OCR/imagem): $MODELO_VISAO"
[ "$PERFIL" = "bibliotecario" ] && ok "Modelo de embeddings: $MODELO_EMBEDDING"

baixar_se_faltar() {
  local modelo="$1"
  if [ "$EH_WSL2" = "1" ]; then return; fi  # no WSL2 o download é feito no Windows
  if ollama list 2>/dev/null | grep -qw "$modelo"; then
    ok "  Modelo $modelo já presente -- não vai baixar de novo."
  else
    log "  Modelo $modelo não encontrado localmente. Tentando baixar..."
    if ollama pull "$modelo" 2>/dev/null; then
      ok "  $modelo baixado."
    else
      warn "  Falha ao baixar $modelo (sem internet nesta máquina?)."
      warn "  Se este nó não tem internet por design, baixe o modelo em outra"
      warn "  máquina com internet e copie ~/.ollama/models pra cá, ou rode"
      warn "  'ollama pull $modelo' aqui manualmente enquanto houver internet."
    fi
  fi
}

baixar_se_faltar "$MODELO"
[ -n "$MODELO_VISAO" ] && baixar_se_faltar "$MODELO_VISAO"
[ "$PERFIL" = "bibliotecario" ] && baixar_se_faltar "$MODELO_EMBEDDING"

# ---------------------------------------------------------------------------
# 4) PACOTES DE SISTEMA -- SÓ O QUE O PERFIL PRECISA (idempotente)
# ---------------------------------------------------------------------------
log "[4/8] Instalando pacotes de sistema específicos do perfil..."

if [ "$EH_MACOS" = "1" ]; then
  # macOS: curl/git/rsync/sqlite3/python3 já vêm com o sistema (via Xcode
  # Command Line Tools) na grande maioria das instalações -- só avisamos se
  # faltar algo, em vez de tentar instalar às cegas.
  for cmd in curl git rsync sqlite3 python3; do
    if command -v "$cmd" &>/dev/null; then
      ok "  $cmd já disponível."
    else
      warn "  $cmd não encontrado. Rode 'xcode-select --install' nesta máquina e execute o bootstrap de novo."
    fi
  done

  instalar_brew_se_faltar() {
    for pkg in "$@"; do
      if brew list "$pkg" &>/dev/null; then
        ok "  $pkg já instalado (brew)."
      else
        log "  Instalando $pkg via brew..."
        brew install "$pkg" 2>/dev/null || warn "  Falha ao instalar $pkg via brew."
      fi
    done
  }

  case "$PERFIL" in
    artista_midia)
      instalar_brew_se_faltar tesseract tesseract-lang ffmpeg
      ;;
    # bibliotecario: não precisa de nada extra do sistema no macOS --
    # RAG usa SQLite+numpy (Python puro), sem dependência de redis.
  esac
else
  sudo apt update -qq 2>/dev/null || true

  instalar_apt_se_faltar() {
    for pkg in "$@"; do
      if dpkg -s "$pkg" &>/dev/null; then
        ok "  $pkg já instalado."
      else
        log "  Instalando $pkg..."
        sudo apt install -y -qq "$pkg" 2>/dev/null || warn "  Falha ao instalar $pkg."
      fi
    done
  }

  instalar_apt_se_faltar python3-venv python3-pip sqlite3 rsync curl git

  case "$PERFIL" in
    artista_midia)
      instalar_apt_se_faltar tesseract-ocr tesseract-ocr-por ffmpeg
      ;;
    bibliotecario)
      # sshpass é usado pelo endpoint /api/v1/mover_para_worker, que empurra
      # arquivos curados pra pasta certa do worker via rsync/SSH.
      instalar_apt_se_faltar sshpass
      ;;
  esac
fi

# ---------------------------------------------------------------------------
# 5) PYTHON VENV + LIBS -- SÓ O QUE O PERFIL PRECISA
# ---------------------------------------------------------------------------
log "[5/8] Preparando ambiente Python..."
python3 -m venv "$ENXAME_DIR/venv" 2>/dev/null || true
source "$ENXAME_DIR/venv/bin/activate"
pip install --upgrade pip -q

LIBS_COMUNS="fastapi uvicorn httpx pydantic websockets"
pip install -q $LIBS_COMUNS 2>/dev/null || pip install -q --break-system-packages $LIBS_COMUNS

if [ "$PERFIL" = "bibliotecario" ]; then
  pip install -q numpy 2>/dev/null || pip install -q --break-system-packages numpy
fi
if [ "$PERFIL" = "artista_midia" ]; then
  pip install -q pytesseract pillow 2>/dev/null || pip install -q --break-system-packages pytesseract pillow
fi

# ---------------------------------------------------------------------------
# 6) CONFIGURAÇÃO (.env) -- gera token de admin só na primeira vez
# ---------------------------------------------------------------------------
log "[6/8] Gerando configuração..."
NODE_ID="$(hostname)-$(echo $RANDOM | md5sum | head -c4)"

# Preserva valores já configurados manualmente em .env existente (ex: se você
# ajustou KIWIX_URL/CADDY_URL/SSH_PASS depois do primeiro bootstrap, rodar de
# novo não deve apagar isso).
pegar_valor_existente() {
  local chave="$1" padrao="$2"
  if [ -f "$ENXAME_DIR/.env" ] && grep -q "^${chave}=" "$ENXAME_DIR/.env" 2>/dev/null; then
    grep "^${chave}=" "$ENXAME_DIR/.env" | head -1 | cut -d= -f2-
  else
    echo "$padrao"
  fi
}

ADMIN_TOKEN=$(pegar_valor_existente ADMIN_TOKEN "enxame-$(openssl rand -hex 8 2>/dev/null || echo $RANDOM$RANDOM)")
KIWIX_URL=$(pegar_valor_existente KIWIX_URL "http://localhost:7001")
CADDY_URL=$(pegar_valor_existente CADDY_URL "http://localhost:7002")
SSH_USER=$(pegar_valor_existente SSH_USER "user")
SSH_PASS=$(pegar_valor_existente SSH_PASS "123")

cat > "$ENXAME_DIR/.env" << EOF
IP_JUIZ=${JUIZ_IP:-127.0.0.1}
JUIZ_PORTA=7700
IP_DELL=${JUIZ_IP:-127.0.0.1}
NODE_ID=$NODE_ID
PERFIL=$PERFIL
MODELO=$MODELO
MODELO_VISAO=$MODELO_VISAO
MODELO_EMBEDDING=$MODELO_EMBEDDING
MODELO_GERACAO=$MODELO
OLLAMA_URL=$OLLAMA_URL_LOCAL
PORTA=9000
BIBLIOTECARIO_PORTA=7710
IP_BIBLIOTECARIO=
KIWIX_URL=$KIWIX_URL
CADDY_URL=$CADDY_URL
SSH_USER=$SSH_USER
SSH_PASS=$SSH_PASS
SCORE_HARDWARE=$SCORE
TEM_GPU=$TEM_GPU_NVIDIA
ADMIN_TOKEN=$ADMIN_TOKEN
BASES_CONHECIMENTO=data/kb_geral,data/kb_engenharia,data/kb_contabil,data/kb_midia
OCIOSIDADE_SEGUNDOS=300
SEARCH_API_URL=
EOF
ok ".env criado/atualizado. ADMIN_TOKEN salvo em $ENXAME_DIR/.env (guarde-o para autorizar movimentação de arquivos)."

# ---------------------------------------------------------------------------
# 7) SERVIÇO -- systemd se disponível, script certo por perfil
# ---------------------------------------------------------------------------
log "[7/8] Configurando serviço..."

case "$PERFIL" in
  juiz) SCRIPT_PRINCIPAL="juiz.py"; NOME_SERVICO="enxame-juiz" ;;
  bibliotecario) SCRIPT_PRINCIPAL="bibliotecario.py"; NOME_SERVICO="enxame-bibliotecario" ;;
  *) SCRIPT_PRINCIPAL="agente_universal.py"; NOME_SERVICO="enxame-agente" ;;
esac

if [ ! -f "$ENXAME_DIR/$SCRIPT_PRINCIPAL" ]; then
  err "$SCRIPT_PRINCIPAL não encontrado em $ENXAME_DIR. Copie o core/ antes de rodar este script."
  exit 1
fi

if command -v systemctl &>/dev/null && [ "$EH_WSL2" != "1" ]; then
  sudo tee /etc/systemd/system/${NOME_SERVICO}.service > /dev/null << EOF
[Unit]
Description=ENXAME - $PERFIL
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$ENXAME_DIR
EnvironmentFile=$ENXAME_DIR/.env
ExecStart=$ENXAME_DIR/venv/bin/python $ENXAME_DIR/$SCRIPT_PRINCIPAL
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable "$NOME_SERVICO" 2>/dev/null || true
  sudo systemctl restart "$NOME_SERVICO"
  ok "Serviço systemd '$NOME_SERVICO' ativo."
elif [ "$EH_MACOS" = "1" ]; then
  PLIST="$HOME/Library/LaunchAgents/com.enxame.${NOME_SERVICO}.plist"
  mkdir -p "$HOME/Library/LaunchAgents"
  launchctl unload "$PLIST" 2>/dev/null || true
  cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.enxame.${NOME_SERVICO}</string>
  <key>ProgramArguments</key>
  <array>
    <string>$ENXAME_DIR/venv/bin/python</string>
    <string>$ENXAME_DIR/$SCRIPT_PRINCIPAL</string>
  </array>
  <key>WorkingDirectory</key><string>$ENXAME_DIR</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$ENXAME_DIR/logs/${NOME_SERVICO}.log</string>
  <key>StandardErrorPath</key><string>$ENXAME_DIR/logs/${NOME_SERVICO}.log</string>
</dict>
</plist>
EOF
  launchctl load "$PLIST" && ok "Serviço launchd '$NOME_SERVICO' ativo (reinicia sozinho, inclusive após reiniciar o Mac)." \
    || warn "Falha ao carregar o launchd. Rodando via nohup como alternativa."
  if ! launchctl list | grep -q "com.enxame.${NOME_SERVICO}"; then
    nohup "$ENXAME_DIR/venv/bin/python" "$ENXAME_DIR/$SCRIPT_PRINCIPAL" \
      > "$ENXAME_DIR/logs/${NOME_SERVICO}.log" 2>&1 &
  fi
else
  pkill -f "$SCRIPT_PRINCIPAL" 2>/dev/null || true
  nohup "$ENXAME_DIR/venv/bin/python" "$ENXAME_DIR/$SCRIPT_PRINCIPAL" \
    > "$ENXAME_DIR/logs/${NOME_SERVICO}.log" 2>&1 &
  ok "Processo iniciado via nohup (WSL2/sem systemd). Log: $ENXAME_DIR/logs/${NOME_SERVICO}.log"
fi

# ---------------------------------------------------------------------------
# 8) INDEXAÇÃO INICIAL (não roda para o Juiz, que não tem base de conhecimento própria)
# ---------------------------------------------------------------------------
if [ "$PERFIL" != "juiz" ]; then
  log "[8/8] Indexação local inicial..."
  "$ENXAME_DIR/venv/bin/python" "$ENXAME_DIR/indexador.py" --once || warn "Indexação inicial falhou, será tentada de novo em loop."
else
  log "[8/8] Perfil 'juiz' não indexa arquivos locais (ele orquestra, não armazena base de conhecimento)."
fi

echo ""
ok "Nó pronto! NODE_ID=$NODE_ID  Perfil=$PERFIL  Modelo=$MODELO${MODELO_VISAO:+  Visão=$MODELO_VISAO}"
echo "Acompanhe: tail -f $ENXAME_DIR/logs/*.log"
