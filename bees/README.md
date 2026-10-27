# Bees — Abelhas Standalone do Enxame

## Visão Geral

O diretório `/bees` contém a implementação completa de uma **Abelha Standalone** conforme a especificação **BEE-0001**.

Uma Abelha é uma unidade autônoma que:
- ✅ Funciona **isolada** (standalone) sem depender de outras Abelhas
- ✅ Opera **offline-first**: memória local → RAG local → peers → web (fallback)
- ✅ Descobre peers automaticamente via **mDNS/Zeroconf**
- ✅ Comunica-se via **protocolo BEE** (WebSocket + HMAC)
- ✅ Mantém **identidade própria**, memória persistente e índice vetorial
- ✅ É **multiplataforma**: Linux, macOS, Windows

## Estrutura

```
bees/
├── __init__.py              # Exports públicos
├── cli.py                   # CLI `bee` (start, query, discover, status, identity, config)
├── service.py               # Serviço principal BeeService
├── config.py                # Configuração cross-platform (BeeConfig)
├── librarian.py             # LocalBeeLibrarian (RAG offline-first)
├── memory.py                # BeeMemory (SQLite persistente)
├── discovery.py             # BeeDiscoveryService (mDNS)
├── protocol/                # Protocolo BEE
│   ├── __init__.py
│   ├── envelope.py          # BeeEnvelope (serialização)
│   ├── handler.py           # BeeProtocolHandler (processamento)
│   └── messages.py          # Tipos de mensagem (HELLO, QUERY, HEARTBEAT, etc.)
├── capabilities/            # Descoberta de capacidades (BEE-0003)
│   ├── discovery.py         # Scan hardware/Ollama/local
│   ├── selector.py          # Recomendação de modelo
│   └── provider.py          # Abstração LLM Provider
├── install/                 # Instaladores
│   ├── install_bee.py       # Instalador principal
│   ├── uninstall_bee.py     # Desinstalador
│   └── README.md
├── spec/                    # Especificações
│   ├── BEE-0001-ABELHA.md   # Conceito de Abelha
│   └── BEE-0002-PROTOCOLO.md # Protocolo de comunicação
└── tests/                   # Testes
    ├── test_protocol.py
    └── test_capabilities.py
```

## Instalação Rápida

```bash
# Instalar dependências
pip install -r requirements.txt

# Ou usar instalador automático
cd bees/install
python install_bee.py
```

## Uso via CLI

```bash
# Gerar identidade
bee identity generate

# Iniciar Abelha
bee start --data-dir ~/.enxame/bee --model llama3.2:3b

# Fazer query local
bee query "O que é RAG?"

# Descobrir peers na rede
bee discover

# Ver status
bee status

# Configuração
bee config show
bee config save
```

## Configuração

A configuração é carregada na ordem:
1. **Defaults** (sensíveis)
2. **Arquivo** `~/.enxame/bee/config.json`
3. **Variáveis de ambiente** `BEE_*`
4. **Argumentos CLI** (`--host`, `--port`, `--model`, etc.)

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `BEE_NODE_ID` | UUID aleatório | Identidade única |
| `BEE_HOST` | `0.0.0.0` | Host de escuta |
| `BEE_PORT` | `8765` | Porta HTTP/WebSocket |
| `BEE_OLLAMA_URL` | `http://localhost:11434` | URL do Ollama |
| `BEE_MODEL` | `llama3.2:3b` | Modelo Ollama |
| `BEE_DATA_DIR` | `~/.enxame/bee` | Diretório de dados |
| `BEE_ALLOW_WEB` | `false` | Permitir fallback web |
| `BEE_SHARED_SECRET` | - | Segredo HMAC para auth |
| `BEE_LOG_LEVEL` | `INFO` | Nível de log |

### Arquivo de Configuração

```json
{
  "node_id": "550e8400-e29b-41d4-a716-446655440000",
  "host": "0.0.0.0",
  "port": 8765,
  "ollama_base_url": "http://localhost:11434",
  "model": "llama3.2:3b",
  "data_dir": "/home/user/.enxame/bee",
  "allow_web": false,
  "confidence_threshold_enxame": 0.7,
  "confidence_threshold_web": 0.8,
  "heartbeat_interval": 5.0,
  "heartbeat_timeout": 15.0
}
```

## Pipeline de Busca (Offline-First)

```
Query
  │
  ▼
┌─────────────────┐
│ 1. Cache Memória│ ──► Hit? ──► Resposta
└────────┬────────┘
         │ Miss
         ▼
┌─────────────────┐
│ 2. Memória      │ ──► Confiança>0.75? ──► Resposta
│    Semântica    │
└────────┬────────┘
         │ Miss
         ▼
┌─────────────────┐
│ 3. LanceDB      │ ──► Hit? ──► RAG + Síntese ──► Resposta
│    (Vetorial)   │
└────────┬────────┘
         │ Miss
         ▼
┌─────────────────┐
│ 4. Arquivos     │ ──► Hit? ──► RAG + Síntese ──► Resposta
│    Locais       │
└────────┬────────┘
         │ Miss
         ▼
┌─────────────────┐
│ 5. ZIM          │ ──► Hit? ──► RAG + Síntese ──► Resposta
│    (Offline)    │
└────────┬────────┘
         │ Miss
         ▼
┌─────────────────┐
│ 6. Web          │ ──► Se allow_web=true ──► Resposta
│    (Fallback)   │
└────────┬────────┘
         │ Miss
         ▼
    Fallback: "Não encontrei..."
```

## Protocolo BEE

Comunicação peer-to-peer via WebSocket:

1. **Discovery**: mDNS `_enxame._tcp.local.`
2. **Handshake**: `HELLO` ↔ `HELLO_ACK` (troca de manifestos)
3. **Heartbeat**: `HEARTBEAT` (5s) / `HEARTBEAT_ACK`
4. **Queries**:
   - `KNOWLEDGE_QUERY` - "Você sabe sobre X?" (rápido, 2s)
   - `RESEARCH_REQUEST` - "Pesquise X" (completo, 30s)
   - `MODEL_REQUEST` - "Gere resposta" (inferência, 60s)
5. **Capability**: `CAPABILITY_QUERY` - "Tem capability X?"

### Segurança

- **HMAC-SHA256** com segredo compartilhado (`BEE_SHARED_SECRET`)
- **Timestamp** em todas as mensagens (janela 60s)
- **Nonce** no handshake (prevenção replay)
- **Sanitização** de inputs (reutiliza `core/exp/input_sanitizer.py`)

## Diretórios de Dados

```
~/.enxame/bee-{node_id}/
├── identity.json          # Identidade (persistente)
├── config.json            # Configuração
├── memory.db              # SQLite (memória, interações, semântica)
├── lancedb/               # Índice vetorial LanceDB
├── documents/             # Documentos para indexar
│   └── inbox/             # Novos docs pendentes
├── zim/                   # Arquivos .zim (Wikipedia offline)
├── cache/                 # Cache volátil
└── logs/                  # Logs
```

## Desenvolvimento

```bash
# Testes
python -m pytest bees/tests/

# Lint
ruff check bees/

# Type check
mypy bees/
```

## Especificações

- **[BEE-0001](spec/BEE-0001-ABELHA.md)** — Conceito de Abelha (standalone, offline-first, generalista)
- **[BEE-0002](spec/BEE-0002-PROTOCOLO.md)** — Protocolo de comunicação (mDNS, handshake, heartbeat, queries)

## Princípios (EIP-0001, EIP-0002)

1. **Architecture First** — Specs em `spec/` antes de implementar
2. **Resource First** — Zero Docker, zero frameworks frontend, dependências mínimas
3. **Soberania Digital** — Sem OpenWebUI, infraestrutura própria, controle total
4. **Offline First** — Internet é fallback, não dependência
5. **Generalismo** — Todas Abelhas iguais na instalação, especialização emergente

---

*Parte do sistema Enxame — "The Enxame is ready to swarm."*