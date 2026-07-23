# ENXAME v5 - Guia de Instalação

## Visão Geral

O ENXAME v5 agora possui um sistema de instalação modular que permite instalar componentes individualmente ou todos de uma vez, seguindo o padrão "Next > Next > Finish".

## Componentes Disponíveis

| Componente        | Descrição                                                              | Porta     | Script                     |
| ----------------- | ---------------------------------------------------------------------- | --------- | -------------------------- |
| **Juiz**          | Coordenador do cluster, gerencia comunicação e distribuição de tarefas | 7700      | `install_juiz.sh`          |
| **Bibliotecário** | Sistema RAG (Retrieval-Augmented Generation) para base de conhecimento | 7710      | `install_bibliotecario.sh` |
| **Workers**       | Agentes/Workers especializados que executam tarefas                    | 9000-9999 | `install_worker.sh`        |
| **OpenWebUI**     | Interface web integrada com frontend do Enxame                         | 3000      | `install_openwebui.sh`     |
| **Consultor**     | Interface amigável + Monitoramento + Auxílio em ociosidade             | 7720      | `install_consultor.sh`     |

## Instalação Rápida (Tudo em Um)

Para instalar todos os componentes de uma vez:

```bash
cd /workspace/installers
sudo ./install_all.sh
```

### Opções de Configuração

Você pode personalizar a instalação usando variáveis de ambiente:

```bash
# Instalar apenas Juiz e OpenWebUI
INSTALL_JUIZ=true \
INSTALL_BIBLIOTECARIO=false \
INSTALL_WORKERS=false \
INSTALL_OPENWEBUI=true \
INSTALL_CONSULTOR=true \
sudo ./install_all.sh

# Instalar 5 workers com função de programador
WORKER_COUNT=5 \
WORKER_ROLE=programador \
sudo ./install_all.sh

# Instalar tudo exceto Consultor (se já existir)
INSTALL_CONSULTOR=false \
sudo ./install_all.sh
```

## Instalação Modular

### 1. Instalar o Juiz (Coordenador)

```bash
sudo ./install_juiz.sh
```

Variáveis de ambiente opcionais:

- `NODE_ID`: ID do nó (padrão: juiz-hostname)
- `JUIZ_PORT`: Porta do serviço (padrão: 7700)
- `OLLAMA_URL`: URL do Ollama (padrão: http://localhost:11434)

### 2. Instalar o Bibliotecário (RAG)

```bash
sudo ./install_bibliotecario.sh
```

Variáveis de ambiente opcionais:

- `NODE_ID`: ID do nó (padrão: bibliotecario-hostname)
- `BIB_PORT`: Porta do serviço (padrão: 7710)
- `JUIZ_URL`: URL do Juiz (padrão: ws://localhost:7700/exp)
- `REDIS_URL`: URL do Redis (padrão: redis://redis-bibliotecario:6379/0)
- `QDRANT_URL`: URL do Qdrant (padrão: http://qdrant-bibliotecario:6333)

### 3. Instalar Workers/Agentes

```bash
sudo ./install_worker.sh --role programador --pool-size 8
```

#### Funções Disponíveis para Workers:

| Função        | Descrição                                       |
| ------------- | ----------------------------------------------- |
| `generic`     | Worker genérico (pode ser reconfigurado depois) |
| `programador` | Especialista em programação e código            |
| `medico`      | Especialista em saúde e medicina                |
| `engenheiro`  | Especialista em engenharia                      |
| `tradutor`    | Especialista em tradução de idiomas             |
| `matematico`  | Especialista em matemática e cálculos           |
| `jurista`     | Especialista em direito e legislação            |
| `redator`     | Especialista em redação e conteúdo              |

#### Opções de Linha de Comando:

```bash
--role <funcao>       # Função primária (padrão: generic)
--pool-size <N>       # Tamanho do pool (padrão: 4)
--model <modelo>      # Modelo Ollama (padrão: qwen2.5:1.5b)
--juiz-url <url>      # URL do Juiz
--ollama-url <url>    # URL do Ollama
```

#### Exemplos:

```bash
# Worker genérico (reconfigurável depois)
sudo ./install_worker.sh

# Worker programador com pool de 8
sudo ./install_worker.sh --role programador --pool-size 8

# Worker tradutor com modelo específico
sudo ./install_worker.sh --role tradutor --model llama3.1:8b

# Worker conectado a Juiz remoto
sudo ./install_worker.sh --role engenheiro --juiz-url ws://192.168.1.100:7700/exp
```

### 4. Instalar OpenWebUI Integrado

```bash
sudo ./install_openwebui.sh
```

**Funcionalidades:**

- Frontend personalizado do Enxame integrado
- Backend atualizável do repositório original
- Instalação conjunta com qualquer função

**Opções:**

```bash
--port <porta>        # Porta do OpenWebUI (padrão: 3000)
--juiz-url <url>      # URL do Juiz para integração
```

### 5. Instalar Consultor (Interface + Monitoramento) ⭐ NOVO

```bash
sudo ./install_consultor.sh
```

**Funcionalidades:**

- 🎯 Interface amigável (frontend) do Enxame
- 👁️ Monitoramento de heartbeats em tempo real
- 🤖 Auxílio automático em períodos de ociosidade
- 🦙 Ollama + modelo LLM >1.5B instalado automaticamente

**O que o Consultor faz:**

1. **Interface Principal**: Dashboard web moderno para acesso ao cluster
2. **Monitoramento**: Verifica continuamente Juiz, Bibliotecário, Workers e OpenWebUI
3. **Auxílio Inteligente**: Quando ocioso e workers sobrecarregados (>80%), ajuda processando tarefas pendentes

**Opções de Configuração:**

```bash
CONSULTOR_PORT=7720           # Porta da interface (padrão: 7720)
OPENWEBUI_PORT=3000           # Porta do OpenWebUI (padrão: 3000)
JUIZ_URL=http://localhost:7700  # URL do Juiz
OLLAMA_MODEL=llama3.2:3b      # Modelo LLM >1.5B (padrão: llama3.2:3b)
IDLE_THRESHOLD=80             # Carga dos workers para ativar auxílio (%)
```

**Exemplos:**

```bash
# Instalação padrão
sudo ./install_consultor.sh

# Com configuração personalizada
export CONSULTOR_PORT=8080
export OLLAMA_MODEL=mistral:7b
export IDLE_THRESHOLD=60
sudo ./install_consultor.sh

# Conectado a Juiz remoto
JUIZ_URL=http://192.168.1.100:7700 sudo ./install_consultor.sh
```

**Comandos de Gerenciamento:**

```bash
# Systemd
systemctl status enxame-consultor
journalctl -u enxame-consultor -f

# Comando unificado
enxame start consultor
enxame status consultor
enxame logs consultor
```

**Acessos:**

- Dashboard: http://localhost:7720
- OpenWebUI: http://localhost:3000
- Logs: /opt/enxame/consultor/logs/

O OpenWebUI é instalado com:

- Frontend customizado do Enxame integrado
- Backend atualizável do repositório original
- Conexão automática com o Juiz

#### Atualizar OpenWebUI:

```bash
cd /opt/enxame/openwebui
./update.sh
```

## Gerenciamento dos Serviços

### Comando Unificado

Após a instalação, use o comando `enxame`:

```bash
enxame start all          # Iniciar todos os componentes
enxame stop all           # Parar todos os componentes
enxame restart all        # Reiniciar todos os componentes
enxame status all         # Ver status de todos

# Gerenciar componentes individuais
enxame start juiz
enxame stop bibliotecario
enxame logs workers
enxame restart openwebui
enxame status consultor      # Ver status do Consultor
enxame logs consultor        # Logs do Consultor
```

### Scripts Individuais

Cada componente tem seu próprio script de gerenciamento:

```bash
# Juiz
/opt/enxame/juiz/manage.sh start
/opt/enxame/juiz/manage.sh stop
/opt/enxame/juiz/manage.sh status
/opt/enxame/juiz/manage.sh logs

# Bibliotecário
/opt/enxame/bibliotecario/manage.sh start

# Workers
/opt/enxame/workers/manage.sh start
/opt/enxame/workers/manage.sh reconfigure  # Apenas workers genéricos

# OpenWebUI
/opt/enxame/openwebui/manage.sh start

# Consultor
/opt/enxame/consultor/manage.sh start
/opt/enxame/consultor/manage.sh stop
/opt/enxame/consultor/manage.sh status
/opt/enxame/consultor/manage.sh logs
```

## Reconfigurar Worker Genérico

Se você instalou um worker com função `generic`, pode reconfigurá-lo:

```bash
cd /opt/enxame/workers
./manage.sh reconfigure
```

Ou manualmente:

```bash
# Editar arquivo .env
nano /opt/enxame/workers/.env

# Mudar ROLE=generic para ROLE=programador
# Reiniciar worker
docker compose restart worker-*
```

## Acessos

Após a instalação, acesse:

- **Juiz**: http://<seu-ip>:7700
- **Bibliotecário**: http://<seu-ip>:7710
- **OpenWebUI**: http://<seu-ip>:3000

## Requisitos do Sistema

### Mínimos:

- Docker e Docker Compose
- 4GB RAM (por worker)
- 20GB disco
- Ubuntu 20.04+ ou Debian 11+

### Recomendados:

- 8GB+ RAM
- 4+ CPUs
- SSD 50GB+
- GPU (opcional, para aceleração de IA)

## Estrutura de Diretórios

```
/opt/enxame/
├── juiz/              # Serviço coordenador
│   ├── manage.sh
│   ├── docker-compose.yml
│   └── .env
├── bibliotecario/     # Serviço RAG
│   ├── manage.sh
│   ├── docker-compose.yml
│   └── .env
├── workers/           # Workers/Agentes
│   ├── manage.sh
│   ├── reconfigure.sh
│   ├── docker-compose.yml
│   ├── .env
│   └── plugins/       # Plugins específicos
├── openwebui/         # Interface Web
│   ├── manage.sh
│   ├── update.sh
│   ├── docker-compose.yml
│   └── .env
├── core/              # Núcleo do Enxame
├── agentes/           # Código dos agentes
└── data/              # Dados e conhecimentos
```

## Troubleshooting

### Verificar logs:

```bash
enxame logs workers
docker logs enxame-juiz
docker logs enxame-openwebui
```

### Verificar status:

```bash
enxame status all
docker ps | grep enxame
```

### Reiniciar serviços:

```bash
enxame restart all
```

### Rede Docker:

```bash
# Recriar rede se necessário
docker network create enxame-network
```

## Segurança

- As senhas e chaves secretas são geradas automaticamente
- Configure firewall para permitir apenas portas necessárias
- Use HTTPS em produção (configure reverse proxy)

## Próximos Passos

1. Acesse o OpenWebUI em http://<seu-ip>:3000
2. Configure sua conta de administrador
3. Conecte ao Ollama e adicione modelos
4. Comece a usar o Enxame!

## Suporte

- Documentação: https://github.com/istacb/enxamepublic
- Issues: https://github.com/istacb/enxamepublic/issues
