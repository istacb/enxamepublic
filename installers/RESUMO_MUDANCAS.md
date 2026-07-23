# Resumo das Mudanças - Instaladores ENXAME v5

## O que foi feito

### 1. Sistema de Instalação Modular "Next > Next > Finish"

Foram criados instaladores separados para cada função do Enxame, permitindo instalação individual ou completa:

#### Scripts Criados:

| Script                     | Função                   | Descrição                                                      |
| -------------------------- | ------------------------ | -------------------------------------------------------------- |
| `install_all.sh`           | **Instalador Principal** | Instala todos os componentes de uma vez (Next > Next > Finish) |
| `install_juiz.sh`          | Juiz/Coordenador         | Instala o serviço coordenador do cluster                       |
| `install_bibliotecario.sh` | Bibliotecário/RAG        | Instala o serviço de base de conhecimento                      |
| `install_worker.sh`        | Workers/Agentes          | Instala workers com função específica ou genérica              |
| `install_openwebui.sh`     | OpenWebUI                | Instala interface web integrada                                |
| `install_consultor.sh`     | **Consultor** ⭐ NOVO    | Interface amigável + Monitoramento + Auxílio em ociosidade     |

### 2. Workers com Função Primária ou Genérica

O instalador de workers (`install_worker.sh`) agora suporta:

- **Funções Especializadas**: programador, medico, engenheiro, tradutor, matematico, jurista, redator
- **Função Genérica**: worker pode ser configurado como genérico e reconfigurado depois via CLI ou script interativo
- **Opções de Linha de Comando**:

  ```bash
  --role <funcao>       # Define função primária
  --pool-size <N>       # Tamanho do pool de workers
  --model <modelo>      # Modelo Ollama a usar
  --juiz-url <url>      # URL do Juiz
  --ollama-url <url>    # URL do Ollama
  ```

- **Script de Reconfiguração**: Workers genéricos incluem `reconfigure.sh` para mudar função depois

### 3. OpenWebUI Integrado

O instalador do OpenWebUI (`install_openwebui.sh`) inclui:

- **Frontend do Enxame Integrado**: Copia componentes customizados do `/src` para o OpenWebUI
- **Backend Atualizável**: Script `update.sh` que atualiza do repositório original do OpenWebUI
- **Instalação Conjunta**: Pode ser instalado juntamente com qualquer função
- **Configuração Automática**: Conecta automaticamente ao Juiz e configura rede Docker

### 3.5. Consultor - Interface + Monitoramento + Auxílio ⭐ NOVO

O instalador `install_consultor.sh` adiciona uma nova função ao Enxame:

- **Interface Amigável**: Dashboard web moderno para acesso ao cluster (porta 7720)
- **Monitoramento de Heartbeats**: Verifica continuamente todos os componentes (Juiz, Bibliotecário, Workers, OpenWebUI)
- **Auxílio em Ociosidade**: Quando ocioso e workers sobrecarregados (>80%), processa tarefas pendentes usando Ollama local
- **Ollama Integrado**: Instala automaticamente Ollama + modelo LLM >1.5B (padrão: llama3.2:3b)
- **Logs Centralizados**: Dashboard mostra status em tempo real e links para logs

**Funcionamento do Auxílio Inteligente:**

1. Monitora carga dos workers via API do Juiz
2. Se carga > 80% E consultor está ocioso (< 2 requisições ativas)
3. Solicita tarefa pendente ao Juiz
4. Processa usando Ollama com modelo local
5. Envia resultado de volta ao Juiz

**Serviços Criados:**

- `enxame-consultor.service` - Interface web principal
- `enxame-consultor-heartbeat.service` - Monitor de health checks
- `enxame-consultor-idle.service` - Auxiliar de tarefas em ociosidade

### 4. Comando Unificado `enxame`

Após instalação, disponível comando unificado:

```bash
enxame start all          # Iniciar tudo
enxame stop juiz          # Parar apenas Juiz
enxame status workers     # Ver status dos workers
enxame logs openwebui     # Ver logs do OpenWebUI
enxame restart bibliotecario
```

### 5. Gerenciamento Individual

Cada componente tem seu próprio script `manage.sh`:

- `/opt/enxame/juiz/manage.sh`
- `/opt/enxame/bibliotecario/manage.sh`
- `/opt/enxame/workers/manage.sh`
- `/opt/enxame/openwebui/manage.sh`

## Como Usar

### Instalação Completa (Recomendado)

```bash
cd /workspace/installers
sudo ./install_all.sh
```

### Instalação Personalizada

```bash
# Apenas Juiz e OpenWebUI
INSTALL_JUIZ=true INSTALL_OPENWEBUI=true \
INSTALL_BIBLIOTECARIO=false INSTALL_WORKERS=false \
sudo ./install_all.sh

# 5 workers programadores
WORKER_COUNT=5 WORKER_ROLE=programador sudo ./install_all.sh
```

### Instalação Modular

```bash
# Instalar apenas Juiz
sudo ./install_juiz.sh

# Instalar worker genérico (reconfigurável depois)
sudo ./install_worker.sh

# Instalar worker programador
sudo ./install_worker.sh --role programador --pool-size 8

# Instalar OpenWebUI
sudo ./install_openwebui.sh
```

## Estrutura de Diretórios Resultante

```
/opt/enxame/
├── juiz/              # Coordenador
│   ├── manage.sh
│   ├── docker-compose.yml
│   └── .env
├── bibliotecario/     # RAG/Knowledge Base
│   ├── manage.sh
│   ├── docker-compose.yml
│   └── .env
├── workers/           # Workers/Agentes
│   ├── manage.sh
│   ├── reconfigure.sh
│   ├── docker-compose.yml
│   ├── .env
│   └── plugins/
├── openwebui/         # Interface Web
│   ├── manage.sh
│   ├── update.sh
│   ├── docker-compose.yml
│   └── .env
├── core/              # Núcleo
├── agentes/           # Agentes
└── data/              # Dados
```

## Integrações Implementadas

### OpenWebUI + Frontend Enxame

- Componentes do `/src` copiados para `/opt/enxame/backend/static/custom`
- Rotas customizadas integradas
- CSS customizado aplicado

### OpenWebUI + Backend Original

- Dockerfile baseado em `ghcr.io/open-webui/open-webui:main`
- Script `update.sh` faz pull da imagem mais recente
- Configurações preservadas em volumes Docker

### Workers + Plugins

- Plugins específicos por função em `/opt/enxame/workers/plugins/`
- Worker genérico carrega plugin base
- Reconfiguração dinâmica via script

## Benefícios

1. **Instalação Simplificada**: Next > Next > Finish
2. **Flexibilidade**: Escolha quais componentes instalar
3. **Workers Versáteis**: Função primária ou genérica reconfigurável
4. **OpenWebUI Atualizável**: Mantém compatibilidade com repo original
5. **Gerenciamento Fácil**: Comando unificado + scripts individuais
6. **Documentação Completa**: README_INSTALACAO.md incluso

## Arquivos na Pasta /installers

- `install_all.sh` - Instalador principal completo
- `install_juiz.sh` - Instalador do Juiz
- `install_bibliotecario.sh` - Instalador do Bibliotecário
- `install_worker.sh` - Instalador de Workers
- `install_openwebui.sh` - Instalador do OpenWebUI
- `README_INSTALACAO.md` - Documentação completa
- `RESUMO_MUDANCAS.md` - Este arquivo

## Compatibilidade

- Ubuntu 20.04+
- Debian 11+
- Requer Docker e Docker Compose
- Root/sudo necessário
