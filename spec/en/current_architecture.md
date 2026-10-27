# Arquitetura Atual do ENXAME

## Visão Geral

O ENXAME é um sistema descentralizado de comunicação entre nós com IA, operando em arquitetura peer-to-peer com papéis dinâmicos.

## Módulos Principais

### 1. Core (`/core`)

Módulos fundamentais do protocolo EXP (ENXAME Protocol):

- **`exp/`**: Protocolo de comunicação
  - `envelope.py`: Envelopes de mensagem EXP com assinatura HMAC
  - `security.py`: Segurança e autenticação
  - `types.py`: Tipos de mensagem EXP (HELLO, HEARTBEAT, TASK_*, etc.)
  - `server.py`, `http.py`: Servidores de comunicação

- **`cluster/`**: Gerenciamento de cluster
  - `failover.py`: Detecção de falhas e redistribuição de papéis
  - `election.py`: Eleição de líderes baseada em benchmark
  - `benchmark.py`: Benchmark de hardware
  - `local_search.py`: Busca local distribuída
  - `sandbox.py`: Isolamento de execução

- **`discovery/`**: Descoberta de nós
  - `advertiser.py`: Anúncio de presença na rede
  - `browser.py`: Navegação e descoberta de nós

- **`memory/`**: Memória do usuário
  - `usuario_memory.py`: Persistência de estado do usuário

- **`ollama/`**: Cliente Ollama
  - `client.py`: Integração com modelos locais

### 2. Juiz (`/juiz`)

Orquestrador central do sistema:

- **Responsabilidades**:
  - Receber prompts dos usuários
  - Distribuir tarefas para agentes
  - Sintetizar respostas finais
  - Definir papéis por benchmark
  - Monitorar heartbeats
  - Gerenciar eleições de failover

- **Arquivos principais**:
  - `service.py`: Serviço principal com WebSocket
  - `app.py`: API FastAPI

### 3. Bibliotecário (`/bibliotecario`)

Serviço de indexação e recuperação de conhecimento:

- **Responsabilidades**:
  - Indexar documentos locais e arquivos ZIM
  - Pesquisa vetorial e full-text
  - Fallback para busca web
  - Tradução PT-BR
  - Cache de respostas

- **Arquivos principais**:
  - `search_service.py`: Pipeline de pesquisa
  - `indexer.py`: Indexação de documentos
  - `qdrant_store.py`: Armazenamento vetorial
  - `embeddings.py`: Geração de embeddings
  - `zim_reader.py`: Leitura de arquivos ZIM
  - `web_client.py`: Busca web fallback

### 4. Agentes (`/agentes`)

Workers polimórficos com hot-load de plugins:

- **Responsabilidades**:
  - Executar tarefas especializadas
  - Hot-load de plugins de especialidade
  - Pool interno de workers
  - Métricas de desempenho
  - Busca local integrada

- **Plugins disponíveis**:
  - `engenheiro.py`: Engenharia
  - `jurista.py`: Jurídico
  - `matematico.py`: Matemática
  - `medico.py`: Medicina
  - `programador.py`: Programação
  - `redator.py`: Redação
  - `tradutor.py`: Tradução

- **Arquivos principais**:
  - `service.py`: Serviço do agente
  - `plugin_manager.py`: Gerenciamento de plugins
  - `worker_pool.py`: Pool de workers
  - `metrics.py`: Coleta de métricas

### 5. Guardião (`/guardian`)

Segurança e monitoramento:

- **Responsabilidades**:
  - Detectar prompt injection
  - Monitorar comportamento anômalo
  - Isolar nós suspeitos (quarentena)
  - Verificar integridade de arquivos
  - Modo sentinela contínuo

- **Arquivos principais**:
  - `guardian.py`: Implementação principal

### 6. Interface Web (`/web`)

Interface web mínima do Enxame:

- **Responsabilidades**:
  - Enviar mensagens para o Juiz
  - Receber respostas em tempo real
  - Exibir histórico de conversas

- **Arquivos principais**:
  - `index.html`: Estrutura HTML
  - `app.js`: Lógica de UI
  - `style.css`: Estilização

## Comunicação

### Protocolo EXP

- **Transporte**: WebSocket para comunicação em tempo real
- **Envelope**: Estrutura padronizada com:
  - `msg_id`: Identificador único
  - `correlation_id`: Correlação de mensagens
  - `source/target`: Origem e destino
  - `type`: Tipo de mensagem (EXPMessageType)
  - `priority`: Prioridade (1-10)
  - `ttl_ms`: Time-to-live
  - `signature`: Assinatura HMAC
  - `payload`: Dados da mensagem

### Tipos de Mensagem

- `HELLO` / `HELLO_ACK`: Registro de nós
- `HEARTBEAT`: Monitoramento de vitalidade
- `ROLE_ASSIGN` / `ROLE_ACK` / `ROLE_CHANGE`: Atribuição de papéis
- `ELECTION_PROPOSE` / `ELECTION_VOTE`: Eleições
- `TASK_SUBMIT` / `TASK_DISPATCH` / `TASK_RESULT` / `TASK_RETRY` / `TASK_CANCEL`: Ciclo de tarefas
- `QUERY` / `QUERY_RESULT`: Consultas
- `JUDGE_SCORE`: Avaliação do Juiz
- `FINAL_RESULT`: Resultado final
- `NODE_LOST`: Detecção de perda de nó
- `ERROR`: Tratamento de erros

## Fluxo de Execução

### 1. Inicialização do Sistema

```
1. Juiz inicia e anuncia presença
2. Agentes se conectam via WebSocket
3. Troca de HELLO/HELLO_ACK com capacidades
4. Eleição inicial de papéis baseada em benchmark
5. Início de heartbeats periódicos
```

### 2. Processamento de Tarefa

```
1. Usuário envia prompt → Juiz
2. Juiz valida com Guardião
3. Bibliotecário recupera contexto
4. Juiz divide em sub-tarefas
5. Sub-tarefas dispatchadas para Agentes especializados
6. Agentes executam com pool interno de workers
7. Resultados retornam ao Juiz
8. Juiz sintetiza resposta final
9. Resposta entregue ao usuário
```

### 3. Failover

```
1. Heartbeat deixa de ser recebido
2. Nó marcado como suspeito → inativo
3. Eleição automática para papel vacante
4. Candidatos baseados em score + confiabilidade
5. Novo nó assume papel
6. Estado migrado suavemente
7. Demais nós notificados
```

## Dependências

### Python (principais)

- `fastapi`: API backend
- `websockets`: Comunicação WebSocket
- `pydantic`: Validação de dados
- `httpx`: Cliente HTTP assíncrono
- `langchain`: Framework de IA
- `chromadb`, `qdrant-client`: Vetores
- `transformers`, `sentence-transformers`: Modelos
- `redis`: Cache e sessões

### Frontend

- HTML5, CSS3, JavaScript (Vanilla)

### Infraestrutura

- `Ollama`: Modelos de linguagem locais
- `SQLite`, `PostgreSQL`: Bancos de dados
- `Redis`: Cache e sessões

## Implantação

### Serviços Systemd (Linux)

- `enxame-juiz.service`
- `enxame-guardian.service`
- `enxame-bibliotecario.service`
- `enxame-agente.service`

## Estrutura de Diretórios

```
/workspace
├── core/                 # Módulos fundamentais
│   ├── exp/             # Protocolo EXP
│   ├── cluster/         # Gerenciamento de cluster
│   ├── discovery/       # Descoberta de nós
│   ├── memory/          # Memória do usuário
│   └── ollama/          # Cliente Ollama
├── juiz/                # Orquestrador
├── bibliotecario/       # Indexação e pesquisa
├── agentes/             # Workers polimórficos
├── guardian/            # Segurança
├── web/                 # Interface web mínima
└── spec/                # Especificações arquiteturais
```
