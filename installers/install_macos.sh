#!/bin/bash
# =============================================================================
# ENXAME v5 - Instalador Automático para macOS
# Instalação "Next > Next > Finish" - sem perguntas ao usuário
# Requer: macOS 10.15+ e Homebrew instalado (ou será instalado)
# Inclui: Backend Python, Frontend Svelte/OpenWebUI, Ollama e configuração completa
# =============================================================================

set -e

echo "============================================================"
echo "  ENXAME v5 - Instalador Automatico (macOS)"
echo "  Sistema de comunicacao descentralizada com IA"
echo "============================================================"
echo ""

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[AVISO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERRO]${NC} $1"
}

# Verificar se é root ou usar sudo
if [ "$EUID" -ne 0 ]; then 
    log_error "Por favor execute com sudo (sudo ./install_macos.sh)"
    exit 1
fi

# Diretório de instalação
ENXAME_DIR="/opt/enxame"
USER_ENXAME_DIR="$HOME/.enxame"
OPENWEBUI_DIR="$ENXAME_DIR/openwebui"

log_info "Instalando ENXAME v5 em $ENXAME_DIR..."

# 1. Verificar/Instalar Homebrew
log_info "Verificando Homebrew..."
if ! command -v brew &> /dev/null; then
    log_warn "Homebrew nao encontrado. Instalando..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Adicionar Homebrew ao PATH para Apple Silicon
    if [ "$(uname -m)" = "arm64" ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    else
        eval "$(/usr/local/bin/brew shellenv)"
    fi
else
    log_info "Homebrew ja esta instalado."
    eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null || true
fi

# 2. Instalar Python e Node.js via Homebrew
log_info "Instalando Python e Node.js via Homebrew..."
brew install python@3.11 --quiet || true
brew install node --quiet || true

# 3. Criar diretórios
log_info "Criando estrutura de diretorios..."
mkdir -p "$ENXAME_DIR"
mkdir -p "$USER_ENXAME_DIR/logs"
mkdir -p "$USER_ENXAME_DIR/memory"
mkdir -p "$USER_ENXAME_DIR/guardian"
mkdir -p "$USER_ENXAME_DIR/failover"
mkdir -p "$USER_ENXAME_DIR/data/kb_contabil"
mkdir -p "$USER_ENXAME_DIR/data/kb_engenharia"
mkdir -p "$USER_ENXAME_DIR/data/kb_rh_trabalhista"
mkdir -p "$USER_ENXAME_DIR/data/kb_vendas"
mkdir -p "$USER_ENXAME_DIR/data/kb_seguranca"
mkdir -p "$USER_ENXAME_DIR/perfis"
mkdir -p "$OPENWEBUI_DIR"

# 4. Copiar arquivos do projeto
log_info "Copiando arquivos do projeto..."
cd "$(dirname "$0")/.."

# Copiar backend Python
cp -r backend/ "$ENXAME_DIR/" 2>/dev/null || true
cp -r agentes/ "$ENXAME_DIR/" 2>/dev/null || true
cp -r bibliotecario/ "$ENXAME_DIR/" 2>/dev/null || true
cp -r juiz/ "$ENXAME_DIR/" 2>/dev/null || true
cp -r guardian/ "$ENXAME_DIR/" 2>/dev/null || true
cp -r scripts/ "$ENXAME_DIR/" 2>/dev/null || true
cp requirements.txt "$ENXAME_DIR/" 2>/dev/null || true

# Copiar frontend SvelteKit (OpenWebUI + Enxame)
log_info "Copiando frontend SvelteKit (OpenWebUI + Enxame)..."
cp -r src/ "$OPENWEBUI_DIR/" 2>/dev/null || true
cp package.json "$OPENWEBUI_DIR/" 2>/dev/null || true
cp package-lock.json "$OPENWEBUI_DIR/" 2>/dev/null || true
cp svelte.config.js "$OPENWEBUI_DIR/" 2>/dev/null || true
cp vite.config.ts "$OPENWEBUI_DIR/" 2>/dev/null || true
cp tsconfig.json "$OPENWEBUI_DIR/" 2>/dev/null || true
cp .npmrc "$OPENWEBUI_DIR/" 2>/dev/null || true
cp -r static/ "$OPENWEBUI_DIR/" 2>/dev/null || true

# Copiar perfis JSON
if [ -d "perfis" ]; then
    cp perfis/*.json "$USER_ENXAME_DIR/perfis/" 2>/dev/null || true
fi

# 5. Criar ambiente virtual Python
log_info "Criando ambiente virtual Python..."
python3 -m venv "$ENXAME_DIR/venv"

# 6. Instalar dependências Python
log_info "Instalando dependencias Python..."
source "$ENXAME_DIR/venv/bin/activate"
pip install --upgrade pip -q
pip install fastapi uvicorn pydantic httpx websockets zeroconf typer rich numpy -q

# Instalar dependências do OpenWebUI backend
log_info "Instalando dependencias do OpenWebUI backend..."
cd "$ENXAME_DIR/backend"
pip install -r requirements.txt -q 2>/dev/null || true

# 7. Instalar Node.js dependencies e build do frontend
log_info "Instalando dependencias Node.js e build do frontend..."
cd "$OPENWEBUI_DIR"

# Instalar dependências npm
npm install --legacy-peer-deps -q 2>/dev/null || npm install -q 2>/dev/null || true

# Build do frontend
log_info "Compilando frontend SvelteKit..."
npm run build -q 2>/dev/null || true

# 8. Instalar Ollama
log_info "Verificando Ollama..."
if ! command -v ollama &> /dev/null; then
    log_warn "Ollama nao encontrado. Instalando..."
    brew install --cask ollama --quiet
    
    # Iniciar Ollama
    launchctl load /Library/LaunchDaemons/com.ollama.ollama.plist 2>/dev/null || true
else
    log_info "Ollama ja esta instalado."
fi

# 9. Verificar e instalar modelos mínimos (apenas se necessário)
log_info "Verificando modelos de IA instalados..."

# Função para verificar modelos existentes
check_existing_models() {
    local model_count=$(ollama list 2>/dev/null | grep -v "^NAME" | wc -l)
    echo $model_count
}

EXISTING_MODELS=$(check_existing_models)

if [ "$EXISTING_MODELS" -eq 0 ]; then
    log_warn "Nenhum modelo encontrado. Instalando modelos minimos recomendados..."
    
    # Instalar apenas modelos >= 1.5B
    log_info "Baixando qwen2.5:1.5b (minimo 1.5B parametros)..."
    ollama pull qwen2.5:1.5b 2>/dev/null || true
    
    log_info "Baixando nomic-embed-text (modelo de embedding)..."
    ollama pull nomic-embed-text 2>/dev/null || true
    
    log_info "Modelos basicos instalados. Usuario pode adicionar mais modelos manualmente."
else
    log_info "$EXISTING_MODELS modelo(s) ja instalado(s). Nenhum modelo sera modificado."
    log_info "Para adicionar modelos adicionais, execute: ollama pull <nome-do-modelo>"
    log_info "Nota: Apenas modelos com >= 1.5B parametros sao recomendados para producao."
fi

# 10. Criar arquivo de configuração
log_info "Criando arquivo de configuracao..."
cat > "$USER_ENXAME_DIR/.env" << EOF
# Configuração ENXAME v5
NODE_ID=$(scutil --get HostName)
IP_JUIZ=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")
JUIZ_PORTA=7700
BIBLIOTECARIO_PORTA=7710
GUARDIAN_PORTA=7720
OLLAMA_URL=http://localhost:11434
OPENWEBUI_URL=http://localhost:8080
ENXAME_DIR=$USER_ENXAME_DIR
EOF

# 11. Criar script de inicialização rápida
cat > /usr/local/bin/enxame << 'EOF'
#!/bin/bash
# Script de linha de comando do ENXAME v5 para macOS

case "$1" in
    status)
        echo "=== Status do ENXAME ==="
        launchctl list | grep enxame || echo "Nenhum servico ENXAME rodando"
        launchctl list | grep openwebui || echo "Servico OpenWebUI nao listado"
        ;;
    start)
        echo "Iniciando servicos ENXAME..."
        # Iniciar Juiz em background
        cd /opt/enxame && source venv/bin/activate && nohup python juiz.py > ~/.enxame/logs/juiz.log 2>&1 &
        # Iniciar Guardian em background
        cd /opt/enxame && source venv/bin/activate && nohup python guardian/guardian.py > ~/.enxame/logs/guardian.log 2>&1 &
        # Iniciar OpenWebUI em background
        cd /opt/enxame/openwebui && source ../venv/bin/activate && nohup python -m uvicorn backend.open_webui.main:app --host 0.0.0.0 --port 8080 > ~/.enxame/logs/openwebui.log 2>&1 &
        echo "Servicos iniciados."
        ;;
    stop)
        echo "Parando servicos ENXAME..."
        pkill -f "python.*juiz.py" || true
        pkill -f "python.*guardian.py" || true
        pkill -f "uvicorn.*open_webui" || true
        echo "Servicos parados."
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    logs)
        tail -f ~/.enxame/logs/*.log
        ;;
    rebuild-frontend)
        echo "Recompilando frontend..."
        cd /opt/enxame/openwebui
        npm install --legacy-peer-deps
        npm run build
        $0 restart
        echo "Frontend recompilado e servicos reiniciados."
        ;;
    *)
        echo "Uso: enxame {status|start|stop|restart|logs|rebuild-frontend}"
        exit 1
        ;;
esac
EOF
chmod +x /usr/local/bin/enxame

# 12. Criar LaunchAgents para inicialização automática
log_info "Configurando inicializacao automatica..."

# LaunchAgent para o Juiz
cat > /Library/LaunchDaemons/com.enxame.juiz.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.enxame.juiz</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/enxame/venv/bin/python</string>
        <string>/opt/enxame/juiz.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/opt/enxame</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$USER_ENXAME_DIR/logs/juiz.log</string>
    <key>StandardErrorPath</key>
    <string>$USER_ENXAME_DIR/logs/juiz.err</string>
</dict>
</plist>
EOF

# LaunchAgent para o Guardian
cat > /Library/LaunchDaemons/com.enxame.guardian.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.enxame.guardian</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/enxame/venv/bin/python</string>
        <string>/opt/enxame/guardian/guardian.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/opt/enxame</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$USER_ENXAME_DIR/logs/guardian.log</string>
    <key>StandardErrorPath</key>
    <string>$USER_ENXAME_DIR/logs/guardian.err</string>
</dict>
</plist>
EOF

# LaunchAgent para o OpenWebUI
cat > /Library/LaunchDaemons/com.enxame.openwebui.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.enxame.openwebui</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/enxame/venv/bin/python</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>backend.open_webui.main:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8080</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/opt/enxame/openwebui</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$USER_ENXAME_DIR/logs/openwebui.log</string>
    <key>StandardErrorPath</key>
    <string>$USER_ENXAME_DIR/logs/openwebui.err</string>
</dict>
</plist>
EOF

# Carregar LaunchAgents
launchctl load /Library/LaunchDaemons/com.enxame.juiz.plist 2>/dev/null || true
launchctl load /Library/LaunchDaemons/com.enxame.guardian.plist 2>/dev/null || true
launchctl load /Library/LaunchDaemons/com.enxame.openwebui.plist 2>/dev/null || true

# 13. Configurar firewall do macOS
log_info "Configurando firewall do macOS..."
if command -v /usr/libexec/ApplicationFirewall/socketfilterfw &> /dev/null; then
    # Adicionar Python ao firewall (necessário para os serviços aceitarem conexões)
    /usr/libexec/ApplicationFirewall/socketfilterfw --add /opt/enxame/venv/bin/python 2>/dev/null || true
    /usr/libexec/ApplicationFirewall/socketfilterfw --unblock /opt/enxame/venv/bin/python 2>/dev/null || true
fi

# 14. Mostrar informações finais
echo ""
echo "============================================================"
echo -e "${GREEN}  INSTALACAO CONCLUIDA COM SUCESSO!${NC}"
echo "============================================================"
echo ""
echo "📦 ENXAME v5 foi instalado em: $ENXAME_DIR"
echo "📁 Diretorio do usuario: $USER_ENXAME_DIR"
echo "🌐 Frontend OpenWebUI: $OPENWEBUI_DIR"
echo ""
echo "🚀 Serviços configurados:"
echo "   - Juiz (porta 7700)"
echo "   - Guardian (porta 7720)"
echo "   - OpenWebUI com Enxame (porta 8080)"
echo ""
echo "🔧 Comandos úteis:"
echo "   enxame status           - Ver status dos serviços"
echo "   enxame logs             - Ver logs em tempo real"
echo "   enxame restart          - Reiniciar serviços"
echo "   enxame rebuild-frontend - Recompilar frontend após alterações"
echo ""
echo "🌐 Acesse o painel web:"
echo "   OpenWebUI + Enxame: http://localhost:8080"
echo "   Mission Control:    http://localhost:8080/enxame"
echo ""
echo "📖 Documentação: https://github.com/istacb/enxamepublic"
echo ""
echo "============================================================"
