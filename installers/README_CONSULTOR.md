# 🐝 ENXAME v5 - Instalador do CONSULTOR

## 📋 Visão Geral

O **Consultor** é a interface amigável e inteligente do Enxame, projetada para ser o "rosto bonito" do sistema. Sua função principal é fornecer uma experiência de usuário excepcional enquanto monitora a saúde do cluster e auxilia os workers em períodos de ociosidade.

## ✨ Funcionalidades Principais

### 1. 🎯 Interface Amigável (Frontend)
- Dashboard web moderno e intuitivo
- Visualização em tempo real do status do cluster
- Acesso direto ao OpenWebUI personalizado
- Monitoramento de carga dos workers

### 2. 👁️ Monitoramento de Heartbeats
- Verificação contínua de todos os componentes
- Juiz, Bibliotecário, Workers e OpenWebUI
- Logs detalhados de status
- Alertas visuais no dashboard

### 3. 🤖 Auxílio Inteligente em Ociosidade
- Detecta automaticamente quando os workers estão sobrecarregados
- Utiliza Ollama com modelo LLM >1.5B localmente
- Processa tarefas pendentes quando ocioso
- Integração automática com o Juiz para receber tarefas

## 🚀 Instalação Rápida

### Instalação Automática (Recomendada)

```bash
# Como root
sudo ./install_consultor.sh
```

### Instalação Personalizada

```bash
# Variáveis de ambiente opcionais
export CONSULTOR_PORT=7720           # Porta da interface
export OPENWEBUI_PORT=3000           # Porta do OpenWebUI
export JUIZ_URL=http://192.168.1.100:7700  # URL do Juiz
export OLLAMA_MODEL=llama3.2:3b      # Modelo LLM (>1.5B)
export INSTALL_DIR=/opt/enxame/consultor

sudo ./install_consultor.sh
```

### Instalação via Script Principal

```bash
# Incluído automaticamente no install_all.sh
export INSTALL_CONSULTOR=true
sudo ./install_all.sh
```

## 📦 Componentes Instalados

| Componente | Descrição | Porta |
|------------|-----------|-------|
| Consultor Service | Interface web principal | 7720 |
| Heartbeat Monitor | Monitor de saúde do cluster | - |
| Idle Helper | Auxiliar de tarefas em ociosidade | - |
| Ollama | Motor de IA local | 11434 |
| Modelo LLM | llama3.2:3b (ou configurado) | - |

## 🔧 Gerenciamento de Serviços

### Systemd Services

```bash
# Status do Consultor
systemctl status enxame-consultor

# Status do Monitor de Heartbeats
systemctl status enxame-consultor-heartbeat

# Status do Auxiliar em Ociosidade
systemctl status enxame-consultor-idle

# Logs em tempo real
journalctl -u enxame-consultor -f

# Reiniciar serviços
systemctl restart enxame-consultor
systemctl restart enxame-consultor-heartbeat
systemctl restart enxame-consultor-idle

# Parar serviços
systemctl stop enxame-consultor
systemctl stop enxame-consultor-heartbeat
systemctl stop enxame-consultor-idle
```

### Comando Unificado

```bash
# Usando o comando 'enxame'
enxame start consultor
enxame stop consultor
enxame restart consultor
enxame status consultor
enxame logs consultor
```

## 🌐 Acessos

| Serviço | URL | Descrição |
|---------|-----|-----------|
| Consultor Dashboard | http://localhost:7720 | Interface principal |
| OpenWebUI | http://localhost:3000 | Chat com IA |
| Juiz API | http://localhost:7700 | Coordenador |
| Ollama | http://localhost:11434 | Motor LLM |

## ⚙️ Configuração

Arquivo de configuração: `/opt/enxame/consultor/config/consultor.env`

```bash
# Configurações principais
CONSULTOR_PORT=7720
OPENWEBUI_PORT=3000
JUIZ_URL=http://localhost:7700
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
INSTALL_DIR=/opt/enxame/consultor

# Thresholds
HEARTBEAT_INTERVAL=10        # Intervalo de verificação (segundos)
IDLE_THRESHOLD=80            # Carga dos workers para ativar auxílio (%)
```

## 🤝 Como Funciona o Auxílio em Ociosidade

### Fluxo de Decisão

```
1. Monitor verifica carga dos workers via API do Juiz
   ↓
2. Se carga > 80% E consultor está ocioso
   ↓
3. Solicita tarefa pendente ao Juiz
   ↓
4. Processa tarefa usando Ollama local
   ↓
5. Envia resultado de volta ao Juiz
   ↓
6. Retorna ao estado de monitoramento
```

### Critérios de Ativação

- ✅ Carga média dos workers > 80%
- ✅ Consultor com < 2 requisições ativas
- ✅ Tarefas pendentes disponíveis no Juiz
- ✅ Ollama operacional e modelo carregado

## 📊 Dashboard do Consultor

O dashboard fornece:

- **Status em Tempo Real**: Cards coloridos para cada componente
- **Medidor de Carga**: Barra visual com porcentagem de uso
- **Contagem de Workers**: Número de workers ativos
- **Acesso Rápido**: Botões para OpenWebUI e Logs
- **Atualização Automática**: Refresh a cada 5-10 segundos

## 🔍 Troubleshooting

### Consultor não inicia

```bash
# Verificar logs
journalctl -u enxame-consultor -n 50

# Verificar se porta está disponível
netstat -tlnp | grep 7720

# Reiniciar serviço
systemctl restart enxame-consultor
```

### Ollama não responde

```bash
# Verificar status
systemctl status ollama

# Reiniciar Ollama
systemctl restart ollama

# Testar modelo
ollama run llama3.2:3b "Teste"
```

### Heartbeat falhando

```bash
# Verificar conectividade com componentes
curl http://localhost:7700/health
curl http://localhost:7710/health
curl http://localhost:3000/health

# Verificar logs do monitor
tail -f /opt/enxame/consultor/logs/heartbeats.log
```

### Auxílio em ociosidade não funciona

```bash
# Verificar threshold
cat /opt/enxame/consultor/config/consultor.env | grep IDLE_THRESHOLD

# Verificar logs do idle helper
tail -f /opt/enxame/consultor/logs/idle_helper.log

# Testar comunicação com Juiz
curl http://localhost:7700/api/workers/status
```

## 🔄 Atualização

### Atualizar Modelo LLM

```bash
# Baixar nova versão do modelo
ollama pull llama3.2:3b

# Ou instalar modelo diferente
ollama pull mistral:7b

# Atualizar configuração
echo "OLLAMA_MODEL=mistral:7b" >> /opt/enxame/consultor/config/consultor.env

# Reiniciar serviço
systemctl restart enxame-consultor-idle
```

### Atualizar Interface

```bash
# Reinstalar consultor (preserva configuração)
sudo ./install_consultor.sh
```

## 📁 Estrutura de Diretórios

```
/opt/enxame/consultor/
├── config/
│   └── consultor.env          # Configurações
├── logs/
│   ├── consultor.log          # Logs principais
│   ├── heartbeats.log         # Logs de monitoramento
│   └── idle_helper.log        # Logs de auxílio
├── scripts/
│   ├── monitor_heartbeats.sh  # Script de monitoramento
│   └── idle_helper.sh         # Script de auxílio
├── data/                       # Dados locais
└── index.html                  # Dashboard web
```

## 🎯 Casos de Uso

### Cenário 1: Escritório Corporativo
- **Função**: Interface única para todos os usuários
- **Vantagem**: Monitoramento centralizado + auxílio automático
- **Configuração**: Modelo maior (llama3.2:8b) para tarefas complexas

### Cenário 2: Home Office
- **Função**: Acesso remoto ao cluster
- **Vantagem**: Dashboard simples e intuitivo
- **Configuração**: Modelo leve (llama3.2:3b) para economia de recursos

### Cenário 3: Ambiente de Desenvolvimento
- **Função**: Debug e monitoramento detalhado
- **Vantagem**: Logs em tempo real + teste de carga
- **Configuração**: Threshold mais baixo (60%) para mais auxílio

## 🔐 Segurança

### Firewall

```bash
# Regras automáticas (se ufw ativo)
ufw allow 7720/tcp comment "ENXAME Consultor"
ufw allow 11434/tcp comment "ENXAME Ollama"
```

### Acesso Remoto

Para acesso remoto seguro:

```bash
# SSH Tunnel
ssh -L 7720:localhost:7720 usuario@servidor

# Depois acessar
http://localhost:7720
```

## 📈 Performance

### Requisitos Mínimos

- **CPU**: 4 cores
- **RAM**: 8GB (16GB recomendado para modelos >3B)
- **Armazenamento**: 20GB livres
- **Rede**: 100 Mbps

### Otimizações

- Use modelos quantizados (q4_K_M) para menos RAM
- Ajuste `IDLE_THRESHOLD` conforme necessidade
- Monitore uso de RAM do Ollama

## 📞 Suporte

- **Documentação Completa**: `/workspace/installers/README_INSTALACAO.md`
- **Logs**: `/opt/enxame/consultor/logs/`
- **GitHub**: https://github.com/istacb/enxamepublic

---

**ENXAME v5** - Inteligência Coletiva Descentralizada 🐝
