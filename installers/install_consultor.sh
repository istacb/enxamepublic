#!/bin/bash
# ============================================================================
# ENXAME v5 - Instalador do CONSULTOR
# ============================================================================
# Função: Interface amigável (frontend) do Enxame
# - Acessa o enxame via OpenWebUI personalizado
# - Monitora heartbeats de todos os componentes
# - Em ociosidade, ajuda workers com demanda excessiva
# - Instala Ollama + modelo >1.5B automaticamente
# ============================================================================

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Variáveis de configuração
CONSULTOR_PORT="${CONSULTOR_PORT:-7720}"
OPENWEBUI_PORT="${OPENWEBUI_PORT:-3000}"
JUIZ_URL="${JUIZ_URL:-http://localhost:7700}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:3b}"
INSTALL_DIR="${INSTALL_DIR:-/opt/enxame/consultor}"
SYSTEMD_DIR="/etc/systemd/system"

# Banner
echo -e "${CYAN}"
cat << 'EOF'
╔═══════════════════════════════════════════════════════════╗
║           ENXAME v5 - Instalador do CONSULTOR             ║
║                                                           ║
║  🎯 Função: Interface amigável do Enxame                  ║
║  👁️  Monitoramento: Heartbeats em tempo real              ║
║  🤖 IA Local: Ollama + Modelo >1.5B (auxílio em ociosidade)║
╚═══════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Detectar sistema operacional
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt &> /dev/null; then
            OS="ubuntu"
        elif command -v yum &> /dev/null || command -v dnf &> /dev/null; then
            OS="fedora"
        else
            OS="linux"
        fi
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        OS="windows"
    else
        OS="unknown"
    fi
    echo $OS
}

OS=$(detect_os)
echo -e "${BLUE}📌 Sistema detectado:${NC} $OS"

# Verificar se é root (necessário para systemd)
if [[ "$EUID" -ne 0 && "$OS" != "macos" ]]; then
    echo -e "${RED}❌ Erro: Este script precisa ser executado como root (sudo)${NC}"
    exit 1
fi

# Função para instalar dependências
install_dependencies() {
    echo -e "\n${YELLOW}📦 Instalando dependências...${NC}"
    
    case $OS in
        ubuntu|debian)
            apt-get update -qq
            apt-get install -y -qq curl wget git jq netcat-openbsd systemd
            ;;
        fedora|centos|rhel)
            yum install -y -q curl wget git jq netcat systemd
            ;;
        macos)
            if ! command -v brew &> /dev/null; then
                echo -e "${YELLOW}Homebrew não encontrado. Instalando...${NC}"
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            fi
            brew install curl wget git jq
            ;;
        *)
            echo -e "${RED}❌ Sistema operacional não suportado: $OS${NC}"
            exit 1
            ;;
    esac
    
    echo -e "${GREEN}✅ Dependências instaladas${NC}"
}

# Função para instalar Ollama
install_ollama() {
    echo -e "\n${YELLOW}🦙 Instalando Ollama...${NC}"
    
    # Verificar se já está instalado
    if command -v ollama &> /dev/null; then
        echo -e "${GREEN}✅ Ollama já está instalado${NC}"
        return 0
    fi
    
    case $OS in
        ubuntu|debian|fedora|centos|rhel)
            curl -fsSL https://ollama.com/install.sh | sh
            ;;
        macos)
            brew install ollama
            ;;
        *)
            echo -e "${RED}❌ Instalação automática do Ollama não suportada para $OS${NC}"
            echo -e "${YELLOW}⚠️  Instale manualmente em: https://ollama.com${NC}"
            return 1
            ;;
    esac
    
    echo -e "${GREEN}✅ Ollama instalado com sucesso${NC}"
}

# Função para instalar modelo LLM
install_llm_model() {
    local model=$1
    echo -e "\n${YELLOW}🤖 Instalando modelo LLM: ${model}${NC}"
    
    # Verificar se o modelo já está instalado
    if ollama list | grep -q "^${model%%:*}"; then
        echo -e "${GREEN}✅ Modelo ${model} já está instalado${NC}"
        return 0
    fi
    
    # Iniciar Ollama se não estiver rodando
    if ! pgrep -x "ollama" > /dev/null; then
        echo -e "${YELLOW}⚠️  Iniciando serviço Ollama...${NC}"
        systemctl start ollama 2>/dev/null || ollama serve &
        sleep 3
    fi
    
    # Baixar modelo (modelos >1.5B para tarefas auxiliares)
    echo -e "${YELLOW}⏳ Baixando modelo... (pode demorar alguns minutos)${NC}"
    ollama pull $model
    
    echo -e "${GREEN}✅ Modelo ${model} instalado com sucesso${NC}"
}

# Função para criar diretórios
create_directories() {
    echo -e "\n${YELLOW}📁 Criando diretórios...${NC}"
    
    mkdir -p $INSTALL_DIR/{config,logs,data,scripts}
    
    echo -e "${GREEN}✅ Diretórios criados${NC}"
}

# Função para criar configuração
create_config() {
    echo -e "\n${YELLOW}⚙️  Criando configuração...${NC}"
    
    cat > $INSTALL_DIR/config/consultor.env << EOF
# Configuração do Consultor ENXAME v5
CONSULTOR_PORT=${CONSULTOR_PORT}
OPENWEBUI_PORT=${OPENWEBUI_PORT}
JUIZ_URL=${JUIZ_URL}
OLLAMA_URL=${OLLAMA_URL}
OLLAMA_MODEL=${OLLAMA_MODEL}
INSTALL_DIR=${INSTALL_DIR}
HEARTBEAT_INTERVAL=10
IDLE_THRESHOLD=80
EOF
    
    echo -e "${GREEN}✅ Configuração criada${NC}"
}

# Função para criar serviço de monitoramento de heartbeats
create_heartbeat_service() {
    echo -e "\n${YELLOW}💓 Criando serviço de monitoramento de heartbeats...${NC}"
    
    cat > $INSTALL_DIR/scripts/monitor_heartbeats.sh << 'EOF'
#!/bin/bash
# Monitor de Heartbeats do Consultor

source /opt/enxame/consultor/config/consultor.env

LOG_FILE="$INSTALL_DIR/logs/heartbeats.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> $LOG_FILE
}

check_heartbeat() {
    local name=$1
    local url=$2
    local timeout=5
    
    if curl -s --max-time $timeout "$url/health" > /dev/null 2>&1; then
        log "✅ $name: ONLINE"
        return 0
    else
        log "❌ $name: OFFLINE"
        return 1
    fi
}

# Componentes para monitorar
COMPONENTS=(
    "Juiz:${JUIZ_URL}"
    "Bibliotecario:http://localhost:7710"
    "OpenWebUI:http://localhost:${OPENWEBUI_PORT}"
)

while true; do
    log "=== Verificando heartbeats ==="
    
    for component in "${COMPONENTS[@]}"; do
        name="${component%%:*}"
        url="${component##*:}"
        check_heartbeat "$name" "$url"
    done
    
    sleep $HEARTBEAT_INTERVAL
done
EOF
    
    chmod +x $INSTALL_DIR/scripts/monitor_heartbeats.sh
    
    echo -e "${GREEN}✅ Serviço de heartbeat criado${NC}"
}

# Função para criar serviço de auxílio em ociosidade
create_idle_helper_service() {
    echo -e "\n${YELLOW}🤝 Criando serviço de auxílio em ociosidade...${NC}"
    
    cat > $INSTALL_DIR/scripts/idle_helper.sh << 'EOF'
#!/bin/bash
# Auxiliar de Tarefas em Ociosidade

source /opt/enxame/consultor/config/consultor.env

LOG_FILE="$INSTALL_DIR/logs/idle_helper.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> $LOG_FILE
}

get_worker_load() {
    # Obter carga dos workers via API do Juiz
    local response=$(curl -s --max-time 5 "$JUIZ_URL/api/workers/status" 2>/dev/null)
    
    if [ -z "$response" ]; then
        echo "0"
        return
    fi
    
    # Calcular média de carga
    local total_load=$(echo "$response" | jq -r '.workers[].load // 0' | awk '{sum+=$1} END {print sum/NR}')
    echo "${total_load:-0}"
}

is_consultor_idle() {
    # Verificar se o consultor está ocioso (sem requisições ativas)
    local active_requests=$(curl -s --max-time 5 "http://localhost:${CONSULTOR_PORT}/api/stats" 2>/dev/null | jq -r '.active_requests // 0')
    
    if [ "${active_requests:-0}" -lt 2 ]; then
        return 0  # Está ocioso
    else
        return 1  # Está ocupado
    fi
}

help_with_task() {
    local task_type=$1
    local task_data=$2
    
    log "🤖 Auxiliando com tarefa: $task_type"
    
    # Usar Ollama para processar tarefa
    local result=$(ollama run $OLLAMA_MODEL "Tarefa: $task_type. Dados: $task_data" 2>/dev/null)
    
    # Enviar resultado de volta ao Juiz
    curl -s -X POST "$JUIZ_URL/api/tasks/complete" \
        -H "Content-Type: application/json" \
        -d "{\"worker\":\"consultor\",\"result\":\"$result\"}" \
        >> $LOG_FILE 2>&1
    
    log "✅ Tarefa completada"
}

# Loop principal
while true; do
    worker_load=$(get_worker_load)
    
    # Se carga dos workers > threshold E consultor ocioso
    if (( $(echo "$worker_load > $IDLE_THRESHOLD" | bc -l 2>/dev/null || echo 0) )); then
        if is_consultor_idle; then
            log "📈 Carga alta dos workers ($worker_load%), consultor ocioso. Auxiliando..."
            
            # Solicitar tarefa pendente
            pending_task=$(curl -s --max-time 5 "$JUIZ_URL/api/tasks/pending" 2>/dev/null)
            
            if [ -n "$pending_task" ]; then
                task_type=$(echo "$pending_task" | jq -r '.type // "unknown"')
                task_data=$(echo "$pending_task" | jq -r '.data // ""')
                help_with_task "$task_type" "$task_data"
            fi
        fi
    fi
    
    sleep 30
done
EOF
    
    chmod +x $INSTALL_DIR/scripts/idle_helper.sh
    
    echo -e "${GREEN}✅ Serviço de auxílio em ociosidade criado${NC}"
}

# Função para criar serviço systemd do Consultor
create_systemd_service() {
    echo -e "\n${YELLOW}🔧 Criando serviço systemd...${NC}"
    
    cat > $SYSTEMD_DIR/enxame-consultor.service << EOF
[Unit]
Description=ENXAME v5 - Consultor Service
After=network.target enxame-juiz.service enxame-openwebui.service
Wants=enxame-juiz.service enxame-openwebui.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/config/consultor.env
ExecStart=/bin/bash -c 'source $INSTALL_DIR/config/consultor.env && python3 -m http.server \$CONSULTOR_PORT --directory $INSTALL_DIR'
Restart=always
RestartSec=5
StandardOutput=append:$INSTALL_DIR/logs/consultor.log
StandardError=append:$INSTALL_DIR/logs/consultor.error.log

[Install]
WantedBy=multi-user.target
EOF

    # Serviço de monitoramento de heartbeats
    cat > $SYSTEMD_DIR/enxame-consultor-heartbeat.service << EOF
[Unit]
Description=ENXAME v5 - Consultor Heartbeat Monitor
After=enxame-consultor.service
Wants=enxame-consultor.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/scripts/monitor_heartbeats.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Serviço de auxílio em ociosidade
    cat > $SYSTEMD_DIR/enxame-consultor-idle.service << EOF
[Unit]
Description=ENXAME v5 - Consultor Idle Helper
After=enxame-consultor.service
Wants=enxame-consultor.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/scripts/idle_helper.sh
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF
    
    # Recarregar systemd
    systemctl daemon-reload
    
    echo -e "${GREEN}✅ Serviços systemd criados${NC}"
}

# Função para integrar com OpenWebUI
integrate_openwebui() {
    echo -e "\n${YELLOW}🌐 Integrando com OpenWebUI...${NC}"
    
    # Criar página inicial personalizada do Consultor
    cat > $INSTALL_DIR/index.html << EOF
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ENXAME v5 - Consultor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 900px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 { color: #667eea; margin-bottom: 10px; }
        .subtitle { color: #666; margin-bottom: 30px; }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .status-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }
        .status-card.online { border-left: 4px solid #28a745; }
        .status-card.offline { border-left: 4px solid #dc3545; }
        .status-icon { font-size: 2em; margin-bottom: 10px; }
        .btn {
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 15px 30px;
            border-radius: 8px;
            text-decoration: none;
            margin: 10px;
            transition: transform 0.2s;
        }
        .btn:hover { transform: translateY(-2px); }
        .btn-secondary { background: #6c757d; }
        .load-meter {
            background: #e9ecef;
            border-radius: 10px;
            height: 20px;
            margin: 10px 0;
            overflow: hidden;
        }
        .load-bar {
            background: linear-gradient(90deg, #28a745, #ffc107, #dc3545);
            height: 100%;
            transition: width 0.5s;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🐝 ENXAME v5 - Consultor</h1>
        <p class="subtitle">Interface Inteligente do Seu Cluster de IA</p>
        
        <div class="status-grid" id="statusGrid">
            <div class="status-card online">
                <div class="status-icon">🧠</div>
                <h3>Juiz</h3>
                <p id="juiz-status">Verificando...</p>
            </div>
            <div class="status-card online">
                <div class="status-icon">📚</div>
                <h3>Bibliotecário</h3>
                <p id="bibliotecario-status">Verificando...</p>
            </div>
            <div class="status-card online">
                <div class="status-icon">🤖</div>
                <h3>Workers</h3>
                <p id="workers-status">Verificando...</p>
            </div>
            <div class="status-card online">
                <div class="status-icon">💬</div>
                <h3>OpenWebUI</h3>
                <p id="openwebui-status">Verificando...</p>
            </div>
        </div>
        
        <h3>Carga do Cluster</h3>
        <div class="load-meter">
            <div class="load-bar" id="loadBar" style="width: 0%"></div>
        </div>
        <p id="loadText">Calculando...</p>
        
        <div style="text-align: center; margin-top: 30px;">
            <a href="http://localhost:${OPENWEBUI_PORT}" class="btn" target="_blank">
                💬 Acessar OpenWebUI
            </a>
            <a href="http://localhost:${CONSULTOR_PORT}/logs" class="btn btn-secondary">
                📊 Ver Logs
            </a>
        </div>
    </div>
    
    <script>
        async function checkStatus() {
            const components = [
                {id: 'juiz-status', url: '${JUIZ_URL}/health'},
                {id: 'bibliotecario-status', url: 'http://localhost:7710/health'},
                {id: 'openwebui-status', url: 'http://localhost:${OPENWEBUI_PORT}/health'}
            ];
            
            for (const comp of components) {
                try {
                    const response = await fetch(comp.url, {method: 'HEAD'});
                    document.getElementById(comp.id).textContent = response.ok ? '✅ Online' : '❌ Offline';
                } catch {
                    document.getElementById(comp.id).textContent = '❌ Offline';
                }
            }
        }
        
        async function loadClusterStats() {
            try {
                const response = await fetch('${JUIZ_URL}/api/cluster/stats');
                const data = await response.json();
                const load = data.average_load || 0;
                
                document.getElementById('loadBar').style.width = load + '%';
                document.getElementById('loadText').textContent = 
                    'Carga atual: ' + load.toFixed(1) + '% (' + data.active_workers + ' workers ativos)';
            } catch {
                document.getElementById('loadText').textContent = 'Não foi possível carregar estatísticas';
            }
        }
        
        checkStatus();
        loadClusterStats();
        
        setInterval(checkStatus, 10000);
        setInterval(loadClusterStats, 5000);
    </script>
</body>
</html>
EOF
    
    echo -e "${GREEN}✅ Interface OpenWebUI integrada${NC}"
}

# Função para habilitar e iniciar serviços
enable_services() {
    echo -e "\n${YELLOW}🚀 Habilitando e iniciando serviços...${NC}"
    
    # Habilitar serviços
    systemctl enable enxame-consultor.service
    systemctl enable enxame-consultor-heartbeat.service
    systemctl enable enxame-consultor-idle.service
    
    # Iniciar serviços
    systemctl start enxame-consultor.service
    systemctl start enxame-consultor-heartbeat.service
    systemctl start enxame-consultor-idle.service
    
    echo -e "${GREEN}✅ Serviços habilitados e iniciados${NC}"
}

# Função para mostrar resumo
show_summary() {
    echo -e "\n${GREEN}"
    cat << EOF
╔═══════════════════════════════════════════════════════════╗
║     ✅ INSTALAÇÃO DO CONSULTOR CONCLUÍDA COM SUCESSO!     ║
╚═══════════════════════════════════════════════════════════╝

📋 RESUMO DA INSTALAÇÃO:

🎯 Função:
   • Interface amigável do Enxame (Frontend)
   • Monitoramento de heartbeats em tempo real
   • Auxílio automático em períodos de ociosidade

🔧 Componentes Instalados:
   • Consultor Service (Porta: ${CONSULTOR_PORT})
   • Monitor de Heartbeats
   • Auxiliar de Tarefas (Idle Helper)
   • Ollama + Modelo: ${OLLAMA_MODEL}
   • Interface Web Personalizada

📁 Diretório: ${INSTALL_DIR}

🌐 Acessos:
   • Interface Consultor: http://localhost:${CONSULTOR_PORT}
   • OpenWebUI: http://localhost:${OPENWEBUI_PORT}
   • Juiz: ${JUIZ_URL}

🛠️ Comandos Úteis:
   • Status:      systemctl status enxame-consultor
   • Logs:        journalctl -u enxame-consultor -f
   • Parar:       systemctl stop enxame-consultor
   • Reiniciar:   systemctl restart enxame-consultor
   
   • Gerenciar tudo: /opt/enxame/manage.sh consultor start|stop|restart|status

📝 Próximos Passos:
   1. Acesse http://localhost:${CONSULTOR_PORT} para ver o painel
   2. Clique em "Acessar OpenWebUI" para usar a interface
   3. O consultor ajudará automaticamente quando ocioso

EOF
    echo -e "${NC}"
}

# ============================================================================
# EXECUÇÃO PRINCIPAL
# ============================================================================

echo -e "${YELLOW}⏳ Iniciando instalação do Consultor...${NC}\n"

# Passo 1: Instalar dependências
install_dependencies

# Passo 2: Instalar Ollama
install_ollama

# Passo 3: Instalar modelo LLM
install_llm_model $OLLAMA_MODEL

# Passo 4: Criar diretórios
create_directories

# Passo 5: Criar configuração
create_config

# Passo 6: Criar serviços
create_heartbeat_service
create_idle_helper_service

# Passo 7: Integrar com OpenWebUI
integrate_openwebui

# Passo 8: Criar serviços systemd
create_systemd_service

# Passo 9: Habilitar e iniciar serviços
enable_services

# Passo 10: Mostrar resumo
show_summary

exit 0
