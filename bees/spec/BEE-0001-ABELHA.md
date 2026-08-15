# BEE-0001 — ABELHA

**Status:** Draft  
**Versão:** 1.0.0  
**Data:** 2025  
**Autoria:** Arquitetura Enxame  
**Revisão:** Baseado na auditoria arquitetural do repositório enxamepublic

---

## 1. CONCEITO DE ABELHA

Uma **Abelha** é uma unidade autônoma do sistema Enxame, executando em uma única máquina física ou virtual. Cada Abelha é um processo independente que possui:

- Identidade única na rede
- Capacidade de processamento local
- Armazenamento próprio
- Conhecimento local indexado
- Habilidade de comunicação peer-to-peer

**Definição normativa:** Abelha é o átomo operacional do Enxame. Não existe Enxame sem pelo menos uma Abelha, e uma Abelha não requer outras para existir.

---

## 2. RELAÇÃO ABELHA × ENXAME

**Enxame** é a propriedade emergente resultante da comunicação e cooperação entre duas ou mais Abelhas conectadas em rede.

### Princípios fundamentais:

1. **Uma Abelha deve conseguir existir e trabalhar sem qualquer outra Abelha.**
   - Funciona isolada (standalone)
   - Processa queries localmente
   - Mantém memória e contexto próprios
   - Indexa documentos locais
   - Acessa internet como fallback se configurado

2. **O Enxame é uma propriedade emergente da comunicação entre duas ou mais Abelhas.**
   - Não há entidade central "Enxame"
   - Enxame = rede de Abelhas + protocolo de comunicação
   - Cooperação surge quando Abelhas se descobrem e trocam conhecimento
   - Topologia é mesh (ponto-a-ponto), não estrela

3. **Não há hierarquia obrigatória.**
   - Todas as Abelhas são pares (peers)
   - Nenhuma Abelha é "mestra" ou "serva" por design
   - Coordenação é distribuída e consensual

---

## 3. IDENTIDADE DA ABELHA

Cada Abelha possui uma identidade única composta por:

### 3.1 Componentes da Identidade

| Campo | Tipo | Descrição | Mutável |
|-------|------|-----------|---------|
| `bee_id` | UUID v4 | Identificador único global | Não |
| `hostname` | string | Nome do host na rede | Sim (reconfig) |
| `address` | IP:Port | Endereço de escuta | Sim (dinâmico) |
| `public_key` | Ed25519 | Chave pública para autenticação | Não |
| `created_at` | timestamp | Data de criação da identidade | Não |
| `capabilities` | list[] | Lista dinâmica de capacidades | Sim |
| `models` | list[] | Modelos disponíveis localmente | Sim |
| `load_score` | float | Carga atual (0.0–1.0) | Sim (tempo real) |

### 3.2 Geração da Identidade

1. Na primeira inicialização, a Abelha gera:
   - `bee_id` via UUID v4 aleatório
   - Par de chaves Ed25519 para assinatura
   - Timestamp de criação

2. A identidade é persistida em:
   ```
   $BEE_DATA_DIR/identity.json
   ```

3. A identidade NÃO muda entre reinicializações, exceto:
   - `capabilities` (atualizada dinamicamente)
   - `models` (atualizado ao detectar mudanças no Ollama)
   - `load_score` (atualizado em tempo real)
   - `address` (pode mudar se porta/IP mudarem)

### 3.3 Anúncio de Identidade

A Abelha anuncia sua identidade via mDNS com payload:
```json
{
  "bee_id": "uuid-v4",
  "hostname": "nome-host",
  "port": 8765,
  "capabilities": ["rag", "ocr", "embeddings"],
  "models": ["llama3.2:3b", "gemma2:2b"],
  "load_score": 0.35,
  "protocol_version": "BEE-0001"
}
```

---

## 4. ESTADO DA ABELHA

### 4.1 Estados do Ciclo de Vida

```
┌─────────────┐
│  STOPPED    │ ← Estado inicial (processo não rodando)
└──────┬──────┘
       │ start()
       ▼
┌─────────────┐
│ STARTING    │ ← Inicializando componentes
└──────┬──────┘
       │ todos componentes OK
       ▼
┌─────────────┐
│  RUNNING    │ ← Operacional, aceitando queries
└──────┬──────┘
       │ erro crítico / stop()
       ▼
┌─────────────┐
│  STOPPING   │ ← Finalizando graceful
└──────┬──────┘
       │ cleanup completo
       ▼
┌─────────────┐
│  STOPPED    │
└─────────────┘
```

### 4.2 Estados Adicionais (não bloqueantes)

| Estado | Significado | Impacto |
|--------|-------------|---------|
| `INDEXING` | Reindexando documentos locais | Pode aumentar `load_score` |
| `DISCOVERING` | Buscando outras Abelhas na rede | Background |
| `PEER_CONNECTED` | Conectada a N outras Abelhas | Habilita cooperação |
| `DEGRADED` | Algum componente falhou | Funcionalidade reduzida |
| `OFFLINE_MODE` | Internet indisponível/bloqueada | Usa apenas recursos locais |

### 4.3 Persistência de Estado

A Abelha persiste:
- Identidade (imutável após criação)
- Configuração local
- Memória de longo prazo (SQLite)
- Índice vetorial (LanceDB)
- Cache de respostas recentes

A Abelha **NÃO** persiste:
- Estado de peers (redescobre via mDNS)
- Cache volátil (recria ao iniciar)
- Contexto de sessão (efêmero)

---

## 5. CICLO DE VIDA

### 5.1 Inicialização (`start()`)

Sequência obrigatória:

1. **Carregar identidade**
   - Ler `$BEE_DATA_DIR/identity.json`
   - Se não existe, gerar nova identidade
   - Validar integridade (assinatura)

2. **Carregar configuração**
   - Ler `$BEE_DATA_DIR/config.json`
   - Aplicar defaults se ausente
   - Validar paths e permissões

3. **Inicializar Bibliotecário Local**
   - Criar/abrir LanceDB store
   - Carregar EmbeddingService
   - Validar UniversalDocumentReader

4. **Inicializar Memória Local**
   - Abrir SQLite `memory.db`
   - Carregar contexto persistente
   - Validar tabelas

5. **Detectar modelos Ollama**
   - Consultar `GET /api/tags` no Ollama local
   - Filtrar modelos por tamanho (1B–10B recomendado)
   - Selecionar melhor modelo conforme hardware
   - Persistir lista em estado local

6. **Anunciar presença via mDNS**
   - Publicar serviço `_enxame-bee._tcp.local`
   - Incluir bee_id, capabilities, models, load_score

7. **Iniciar servidor HTTP**
   - Bind em `config.host:config.port`
   - Expor endpoints: `/health`, `/query`, `/models`, `/status`

8. **Iniciar loop de descoberta**
   - Browser mDNS em background
   - Atualizar lista de peers conhecidos
   - Manter heartbeat com peers ativos

9. **Transicionar para `RUNNING`**
   - Logar "Abelha {bee_id} online"
   - Aceitar queries externas

### 5.2 Operação (`RUNNING`)

Loop principal:

```python
while state == RUNNING:
    # 1. Processar queries recebidas (HTTP/WebSocket)
    handle_incoming_requests()
    
    # 2. Manter heartbeat com peers
    send_heartbeats()
    check_peer_health()
    
    # 3. Atualizar load_score
    update_load_metrics()
    
    # 4. Reanunciar presença via mDNS (TTL)
    refresh_mdns_announcement()
    
    # 5. Reindexação agendada (se documentos mudaram)
    if documents_changed():
        trigger_reindex()
    
    sleep(LOOP_INTERVAL)
```

### 5.3 Finalização (`stop()`)

Sequência graceful:

1. Transicionar para `STOPPING`
2. Parar de aceitar novas queries
3. Aguardar queries em processamento (timeout: 30s)
4. Fechar conexões com peers
5. Remover anúncio mDNS
6. Flush de caches em memória
7. Fechar SQLite e LanceDB
8. Logar "Abelha {bee_id} offline"
9. Transicionar para `STOPPED`

### 5.4 Recuperação de Falhas

| Falha | Ação |
|-------|------|
| Ollama indisponível | Tentar reconnect, marcar estado `DEGRADED`, continuar sem inferência local |
| LanceDB corrompido | Recriar índice do zero, alertar usuário |
| SQLite corrompido | Backup automático, recriar tabelas, perder histórico mas manter identidade |
| mDNS falha | Continuar operando standalone, tentar reconectar periodicamente |
| Disco cheio | Parar indexação, limpar cache, alertar crítico |

---

## 6. GENERALISMO INICIAL

### 6.1 Princípio do Generalismo

**Todas as Abelhas são generalistas na instalação inicial.**

Não existe:
- Papel primário obrigatório
- Papel secundário obrigatório
- Especialização forçada
- Hierarquia de funções

### 6.2 Implicações

1. **Instalação idêntica**
   - Mesmo pacote/software em todas as máquinas
   - Mesmas capacidades básicas
   - Diferenças surgem apenas de hardware e dados locais

2. **Capacidade universal**
   - Toda Abelha pode:
     - Receber queries
     - Processar localmente
     - Indexar documentos
     - Fazer OCR
     - Gerar embeddings
     - Pesquisar RAG
     - Comunicar com outras Abelhas
     - Acessar internet (se permitido)

3. **Especialização emergente (futuro)**
   - Pode surgir por:
     - Dados locais específicos (ex: muitos docs jurídicos)
     - Hardware diferenciado (ex: GPU potente)
     - Configuração manual do usuário
     - Aprendizado de padrões de uso
   - **NÃO** é implementado nesta fase

### 6.3 Anti-padrões proibidos

❌ Instalar Abelha como "Juiz" ou "Bibliotecário" fixo  
❌ Designar papel na instalação  
❌ Assumir que uma Abelha é "melhor" que outra por design  
❌ Criar dependência de papel para operação básica  

---

## 7. CAPABILITIES

### 7.1 Definição

**Capabilities** são habilidades funcionais que uma Abelha possui e pode anunciar para outras Abelhas.

### 7.2 Capabilities Básicas (obrigatórias)

Toda Abelha **DEVE** ter:

| Capability | ID | Descrição |
|------------|----|-----------|
| Query Processing | `query` | Processa queries de linguagem natural |
| Document Indexing | `index` | Indexa documentos locais |
| Vector Search | `vector_search` | Busca semântica via embeddings |
| Text Embedding | `embeddings` | Gera vetores de texto |

### 7.3 Capabilities Opcionais (detectadas)

| Capability | ID | Condição |
|------------|----|----------|
| OCR | `ocr` | Tesseract/PDFium disponível |
| ZIM Reading | `zim` | Arquivos ZIM presentes |
| Web Search | `web` | Internet habilitada na config |
| Peer Cooperation | `peer` | Outras Abelhas descobertas |

### 7.4 Formato de Anúncio

```json
{
  "capabilities": [
    {"id": "query", "version": "1.0"},
    {"id": "index", "version": "1.0"},
    {"id": "vector_search", "version": "1.0"},
    {"id": "embeddings", "version": "1.0"},
    {"id": "ocr", "version": "1.0", "optional": true},
    {"id": "web", "version": "1.0", "optional": true, "enabled": false}
  ]
}
```

### 7.5 Consulta de Capabilities

Protocolo Bee-to-Bee:

```
REQUEST:  GET /capabilities
RESPONSE: 200 OK + JSON acima
```

Uma Abelha pode consultar capabilities de outra antes de enviar query complexa.

---

## 8. RECURSOS LOCAIS

### 8.1 Diretórios da Abelha

Estrutura padrão:

```
$BEE_DATA_DIR/
├── identity.json          # Identidade (persistente)
├── config.json            # Configuração (editável)
├── memory.db              # Memória SQLite (persistente)
├── lancedb/               # Índice vetorial (persistente)
│   └── documents/
├── cache/                 # Cache volátil
│   ├── responses/
│   └── embeddings/
├── documents/             # Documentos indexáveis
│   └── inbox/             # Novos documentos pendentes
├── logs/                  # Logs da Abelha
│   └── bee.log
└── tmp/                   # Temporários
```

### 8.2 Variáveis de Ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `BEE_DATA_DIR` | `~/.enxame/bee-{bee_id}` | Diretório de dados |
| `BEE_HOST` | `0.0.0.0` | Host de escuta |
| `BEE_PORT` | `8765` | Porta HTTP |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `BEE_ALLOW_WEB` | `false` | Habilita fallback web |
| `BEE_LOG_LEVEL` | `INFO` | Nível de log |

### 8.3 Recursos de Hardware

A Abelha detecta e utiliza:

| Recurso | Uso |
|---------|-----|
| CPU | Inferência de modelos, OCR, embeddings |
| RAM | Cache, contexto, modelos carregados |
| GPU (se disponível) | Acelerar inferência Ollama |
| Disco | Persistência (índices, memória, docs) |
| Rede | Descoberta mDNS, comunicação peer-to-peer |

### 8.4 Limites Configuráveis

```json
{
  "max_ram_mb": 4096,
  "max_cache_items": 1000,
  "max_context_messages": 50,
  "max_concurrent_queries": 4,
  "query_timeout_seconds": 60,
  "peer_timeout_seconds": 5
}
```

---

## 9. MODELO(S) LOCAIS

### 9.1 Princípios

1. **Descoberta automática:** A Abelha descobre quais modelos Ollama existem localmente.
2. **Seleção por recursos:** Cada máquina utiliza o melhor modelo que consegue sustentar.
3. **Faixa recomendada:** Modelos de 1B a 10B parâmetros conforme RAM/CPU/GPU.
4. **Sem instalação automática:** Não instalar múltiplos modelos pequenos sem necessidade.
5. **Independência de provider:** Ollama é um provider, não o protocolo.

### 9.2 Detecção de Modelos

Na inicialização, a Abelha:

```python
models = ollama_client.list_models()
# GET http://localhost:11434/api/tags
# Retorna: [{"name": "llama3.2:3b", "size": 2GB}, ...]
```

### 9.3 Seleção do Melhor Modelo

Algoritmo:

```python
def select_best_model(hardware_profile, available_models):
    """
    Seleciona modelo baseado em recursos disponíveis.
    
    hardware_profile: {ram_gb, cpu_cores, has_gpu}
    available_models: [{name, size, params}]
    """
    ram_threshold = hardware_profile.ram_gb * 0.5  # 50% da RAM
    
    candidates = [
        m for m in available_models
        if estimate_ram_usage(m) <= ram_threshold
        and 1e9 <= m.params <= 10e9  # 1B a 10B
    ]
    
    if not candidates:
        # Fallback: menor modelo disponível
        return min(available_models, key=lambda m: m.params)
    
    # Preferir maior modelo dentro do limite
    return max(candidates, key=lambda m: m.params)
```

### 9.4 Tabela de Referência

| RAM Disponível | CPU | GPU | Modelo Recomendado |
|----------------|-----|-----|-------------------|
| 4 GB | 2 cores | Não | phi3:mini (3.8B) ou similar |
| 8 GB | 4 cores | Não | llama3.2:3b ou gemma2:2b |
| 16 GB | 8 cores | Não | llama3.2:7b ou mistral:7b |
| 16+ GB | 8+ cores | Sim | Qualquer modelo até 10B com aceleração GPU |

### 9.5 Persistência da Seleção

A Abelha persiste:
```json
{
  "selected_model": "llama3.2:3b",
  "selection_reason": "best_fit_for_hardware",
  "hardware_snapshot": {
    "ram_gb": 8,
    "cpu_cores": 4,
    "has_gpu": false
  },
  "last_updated": "2025-01-15T10:30:00Z"
}
```

### 9.6 Troca de Modelo

A Abelha pode trocar de modelo se:
- Usuário configura manualmente
- Novo modelo é instalado no Ollama
- Hardware muda (ex: GPU adicionada)
- Modelo atual falha repetidamente

---

## 10. BIBLIOTECÁRIO LOCAL

### 10.1 Definição

Cada Abelha possui seu próprio **Bibliotecário Local**, responsável por:
- Indexar documentos locais
- Gerar embeddings
- Realizar busca vetorial (RAG)
- Suportar múltiplos formatos de documento
- Executar OCR quando necessário

### 10.2 Componentes Reutilizados

Do repositório existente (`/workspace/bibliotecario/`):

| Componente | Arquivo Original | Uso na Abelha |
|------------|------------------|---------------|
| EmbeddingService | `embeddings.py` | Geração de embeddings com fallback determinístico |
| UniversalDocumentReader | `universal_reader.py` | Leitura multi-formato (PDF, DOCX, TXT, etc.) |
| LocalDocumentIndexer | `indexer.py` | Indexação de documentos locais |
| LanceDBStore | `lancedb_store.py` | Armazenamento vetorial embedded |
| ZIMReader | `zim_reader.py` | Leitura de arquivos ZIM offline |
| DuckDuckGoClient | `web_client.py` | Fallback web (opcional) |

### 10.3 Adaptações para Abelha

1. **Sem Redis:** Cache apenas em memória (volátil)
2. **Sem tradução automática:** Translator é opcional/removido
3. **Paths locais:** Todos os índices sob `$BEE_DATA_DIR/lancedb/`
4. **Configuração mínima:** Sem dependência de serviços externos

### 10.4 Pipeline de Indexação

```
Documento → UniversalReader → Texto Bruto
                              ↓
                    [OCR se necessário]
                              ↓
                    EmbeddingService → Vetor
                              ↓
                    LanceDBStore → Persistência
```

### 10.5 Pipeline de Busca (RAG Local)

```
Query → Embedding → Vetor da Query
                      ↓
              LanceDB Similarity Search
                      ↓
              Top-K documentos relevantes
                      ↓
              Context Builder (monta prompt)
                      ↓
              Ollama (modelo local) → Resposta
```

### 10.6 Formatos Suportados

| Formato | Extensão | Leitor |
|---------|----------|--------|
| PDF | `.pdf` | PDFium + OCR opcional |
| Word | `.docx` | python-docx |
| Texto | `.txt` | Nativo |
| Markdown | `.md` | Nativo |
| HTML | `.html`, `.htm` | BeautifulSoup |
| ZIM | `.zim` | ZIMReader |
| CSV | `.csv` | pandas/csv |
| JSON | `.json` | Nativo |

### 10.7 Interface do Bibliotecário

```python
class LocalLibrarian:
    def index_document(self, path: str) -> IndexResult
    def index_directory(self, path: str) -> IndexResult
    def search(self, query: str, top_k: int = 5) -> SearchResults
    def delete_document(self, doc_id: str) -> bool
    def get_stats(self) -> IndexStats
```

---

## 11. MEMÓRIA E CONTEXTO

### 11.1 Definição

A **Memória Local** da Abelha armazena:
- Preferências do usuário/local
- Histórico de interações
- Contexto de sessões recentes
- Memória semântica (tags, conceitos)

### 11.2 Componente Reutilizado

Do repositório existente (`/workspace/core/memory/usuario_memory.py`):

| Função Original | Renomeada para Abelha |
|-----------------|----------------------|
| `UsuarioMemory` | `BeeMemory` |
| `salvar_contexto()` | `salvar_contexto()` |
| `carregar_contexto()` | `carregar_contexto()` |
| `registrar_interacao()` | `registrar_interacao()` |
| `buscar_memoria_semantica()` | `buscar_memoria_semantica()` |
| `atualizar_relevancia_memoria()` | `atualizar_relevancia_memoria()` |

### 11.3 Esquema SQLite

Tabelas persistidas em `$BEE_DATA_DIR/memory.db`:

```sql
-- Contexto/preferências
CREATE TABLE context (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Histórico de interações
CREATE TABLE interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    query TEXT NOT NULL,
    response TEXT,
    source TEXT,  -- 'local', 'peer', 'web'
    confidence REAL
);

-- Memória semântica
CREATE TABLE semantic_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    tags TEXT,  -- JSON array
    relevance REAL DEFAULT 1.0,
    accessed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 11.4 Ciclo de Vida da Memória

| Tipo | Persistência | Limpeza |
|------|--------------|---------|
| Contexto | Permanente | Até exclusão manual |
| Histórico | Permanente | Rotativo (últimos N registros) |
| Memória Semântica | Permanente | Relevance decay (não acessado → menor relevância) |
| Cache de Sessão | Volátil | Reinicialização |

### 11.5 Integração com Fluxo de Decisão

```python
def process_query(query):
    # 1. Buscar na memória semântica
    memory_results = bee_memory.buscar_memoria_semantica(query)
    if memory_results.confidence > threshold:
        return memory_results.response
    
    # 2. Buscar no RAG local
    rag_results = librarian.search(query)
    if rag_results.confidence > threshold:
        bee_memory.registrar_interacao(query, rag_results.response, 'local')
        return rag_results.response
    
    # ... continua para peers e web
```

---

## 12. RAG LOCAL

### 12.1 Definição

**RAG (Retrieval-Augmented Generation) Local** é o mecanismo pelo qual a Abelha:
1. Recupera documentos relevantes do índice local
2. Monta contexto com trechos recuperados
3. Gera resposta usando modelo local

### 12.2 Pipeline Completo

```
┌─────────────┐
│   Query     │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ 1. Embedding    │  → Gera vetor da query
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ 2. LanceDB      │  → Busca similaridade cosseno
│    Search       │  → Retorna top-K chunks
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ 3. Reranking    │  → Opcional: reorder por relevância
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ 4. Context      │  → Monta prompt com chunks
│    Building     │  → Adiciona instruções
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ 5. Generation   │  → Ollama com modelo local
│    (Ollama)     │  → Gera resposta
└──────┬──────────┘
       │
       ▼
┌─────────────┐
│  Resposta   │
└─────────────┘
```

### 12.3 Template de Prompt

```
Você é uma abelha do sistema Enxame. Responda baseado APENAS nos documentos fornecidos.

DOCUMENTOS:
{chunk_1}
{chunk_2}
...
{chunk_K}

PERGUNTA: {query}

Se os documentos não contêm informação suficiente, diga "Não encontrei informação relevante nos meus documentos locais."
```

### 12.4 Configurações

```json
{
  "rag_top_k": 5,
  "rag_chunk_size": 512,
  "rag_chunk_overlap": 50,
  "rag_similarity_threshold": 0.7,
  "rag_rerank_enabled": false
}
```

### 12.5 Métricas de Qualidade

A Abelha rastreia:
- `rag_hit_rate`: % queries com resultado RAG útil
- `avg_similarity_score`: Similaridade média dos chunks recuperados
- `response_confidence`: Confiança média das respostas geradas

---

## 13. POLÍTICA OFFLINE FIRST

### 13.1 Princípio

**A Abelha opera primariamente offline.** Internet é recurso de último recurso, não dependência.

### 13.2 Hierarquia de Fontes

```
┌────────────────────────┐
│ 1. Memória/Contexto    │ ← Mais rápido, sempre disponível
│    Local               │
└───────────┬────────────┘
            │ não encontrou
            ▼
┌────────────────────────┐
│ 2. Conhecimento/RAG    │ ← Index local, funciona offline
│    Local               │
└───────────┬────────────┘
            │ não encontrou
            ▼
┌────────────────────────┐
│ 3. Outras Abelhas      │ ← Requer rede local, sem internet
│    (Enxame)            │
└───────────┬────────────┘
            │ não encontrou
            ▼
┌────────────────────────┐
│ 4. Internet            │ ← Último recurso, requer config
│    (Web Fallback)      │
└────────────────────────┘
```

### 13.3 Comportamento Offline

Quando **sem conexão de rede**:

1. ✅ Funciona normalmente com memória local
2. ✅ Funciona normalmente com RAG local
3. ❌ Não descobre outras Abelhas
4. ❌ Não acessa internet (mesmo se habilitado)

Quando **com rede local mas sem internet**:

1. ✅ Funciona com memória local
2. ✅ Funciona com RAG local
3. ✅ Descobre e coopera com outras Abelhas
4. ❌ Não acessa internet

Quando **completo (rede + internet)**:

1. ✅ Memória local
2. ✅ RAG local
3. ✅ Cooperação com Abelhas
4. ✅ Internet (se `BEE_ALLOW_WEB=true`)

### 13.4 Configuração de Internet

```json
{
  "allow_web": false,
  "web_provider": "duckduckgo",
  "web_max_results": 5,
  "web_timeout_seconds": 10
}
```

**Default:** `allow_web = false` (offline-first)

### 13.5 Indicador de Modo

A Abelha expõe seu modo atual:

```json
GET /status
{
  "state": "RUNNING",
  "mode": "OFFLINE",  // OFFLINE, LAN_ONLY, FULL
  "peers_discovered": 3,
  "internet_available": false,
  "web_enabled": false
}
```

---

## 14. POLÍTICA: LOCAL → ENXAME → WEB

### 14.1 Formalização do Fluxo

Esta política define a ordem **obrigatória** de fontes de conhecimento:

```
LOCAL (sempre primeiro)
  ↓ esgota ou baixa confiança
ENXAME (se peers disponíveis)
  ↓ esgota ou baixa confiança
WEB (apenas se habilitado)
```

### 14.2 Critérios de Transição

#### LOCAL → ENXAME

Transicionar quando:
- `local_results.confidence < threshold_enxame` (default: 0.7)
- OU `local_results.count == 0`
- E `peers_discovered > 0`

#### ENXAME → WEB

Transicionar quando:
- `ensemble_results.confidence < threshold_web` (default: 0.8)
- OU todas as Abelhas consultadas retornaram vazio
- E `config.allow_web == true`

### 14.3 Algoritmo de Decisão

```python
def process_query_with_policy(query):
    confidence_thresholds = {
        'local': 0.0,      # Sempre tenta primeiro
        'enxame': 0.7,     # Se local < 0.7, vai para enxame
        'web': 0.8         # Se enxame < 0.8 e web habilitado
    }
    
    # 1. LOCAL
    local_result = query_local(query)
    if local_result.confidence >= confidence_thresholds['enxame']:
        return local_result
    
    # 2. ENXAME (se houver peers)
    if peers_discovered() > 0:
        enxame_result = query_peers(query)
        if enxame_result.confidence >= confidence_thresholds['web']:
            return enxame_result
    
    # 3. WEB (apenas se habilitado)
    if config.allow_web:
        web_result = query_web(query)
        return web_result
    
    # Fallback: retorna melhor disponível ou "não sei"
    return best_of(local_result, enxame_result, fallback_response())
```

### 14.4 Rastreabilidade

Toda resposta inclui metadados:

```json
{
  "answer": "...",
  "source": "local",  // ou "enxame", "web"
  "confidence": 0.85,
  "sources_used": [
    {"type": "local", "doc_id": "xyz", "similarity": 0.92}
  ],
  "fallback_chain": ["local", "enxame"]  // passos tentados
}
```

---

## 15. PRINCÍPIOS DE SEGURANÇA

### 15.1 Autenticação

1. **Identidade criptográfica:**
   - Cada Abelha tem par de chaves Ed25519
   - Chave pública anunciada no mDNS
   - Mensagens assinadas digitalmente

2. **Autenticação mútua:**
   - Abelhas verificam assinaturas umas das outras
   - Rejeita mensagens de identidade desconhecida (configurável)

### 15.2 Integridade

1. **Assinatura de mensagens:**
   - Todo envelope EXP-Bee assinado
   - Verificação obrigatória antes de processar

2. **Proteção contra replay:**
   - Timestamp em cada mensagem
   - Janela de validade: 5 minutos
   - Nonce para evitar duplicação

### 15.3 Confidencialidade

1. **Criptografia em trânsito:**
   - WebSocket sobre TLS (wss://) em produção
   - HTTP sobre TLS (https://) em produção
   - Desenvolvimento: plaintext permitido

2. **Dados em repouso:**
   - SQLite: criptografia opcional
   - LanceDB: criptografia no nível do filesystem

### 15.4 Proteção contra Injection

1. **Input sanitization:**
   - Reutilizar `core/exp/input_sanitizer.py`
   - Detectar tentativas de prompt injection
   - Bloquear padrões maliciosos

2. **Isolamento de contexto:**
   - Queries de peers não acessam memória local diretamente
   - RAG retorna apenas chunks, não documentos completos

### 15.5 Guardian Local

Cada Abelha executa instância local do Guardião:

| Função | Implementação |
|--------|---------------|
| Detecção de anomaly | Monitora padrões de query suspeitos |
| Rate limiting | Máximo N queries/segundo por peer |
| Integrity check | Verifica integridade de índices periodicamente |
| Reporte local | Loga incidentes em `$BEE_DATA_DIR/logs/security.log` |

**Nota:** Reporte remoto é opcional e configurável.

### 15.6 Configurações de Segurança

```json
{
  "require_auth": true,
  "allow_anonymous_peers": false,
  "max_queries_per_minute": 60,
  "message_ttl_seconds": 300,
  "tls_enabled": false,
  "tls_cert_path": null,
  "tls_key_path": null
}
```

---

## 16. INDEPENDÊNCIA DE SISTEMA OPERACIONAL

### 16.1 Princípio

**A Abelha deve ser multiplataforma.** Funciona em:

- Linux (x86_64, ARM64)
- macOS (Intel, Apple Silicon)
- Windows (10/11, x86_64)

### 16.2 Dependências Platform-Agnostic

| Componente | Biblioteca | Multiplataforma |
|------------|------------|-----------------|
| mDNS | `zeroconf` | ✅ |
| SQLite | `sqlite3` (stdlib) | ✅ |
| LanceDB | `lancedb` | ✅ |
| Ollama Client | `requests` | ✅ |
| Embeddings | `sentence-transformers` | ✅ |
| OCR | `pytesseract` + Tesseract OS | ⚠️ Requer instalação OS-specific |
| PDF | `pypdfium2` | ✅ |

### 16.3 Paths e Filesystem

```python
# Usar pathlib para paths cross-platform
from pathlib import Path

data_dir = Path.home() / '.enxame' / f'bee-{bee_id}'
data_dir.mkdir(parents=True, exist_ok=True)
```

### 16.4 Variáveis de Ambiente

Nomes de variáveis são case-sensitive no Unix, case-insensitive no Windows.

**Convenção:** Sempre uppercase com underscore:
- `BEE_DATA_DIR`
- `OLLAMA_BASE_URL`
- `BEE_ALLOW_WEB`

### 16.5 Portas e Rede

- mDNS: porta 5353 (padrão, requer privilégio em alguns OS)
- HTTP API: porta configurável (default 8765)
- WebSocket: mesma porta HTTP (upgrade)

### 16.6 Instalação do Ollama

A Abelha **não instala** Ollama. Pressupõe-se que Ollama esteja instalado no sistema.

Documentação por plataforma fica fora do escopo da Abelha.

---

## 17. INDEPENDÊNCIA DE PROVIDER/MODELO

### 17.1 Princípio

**O protocolo da Abelha é independente do provider de modelos e do modelo específico.**

### 17.2 Abstração de Provider

Atualmente suporta:
- Ollama (via HTTP API)

Futuros providers possíveis:
- LM Studio
- vLLM
- HuggingFace TGI
- API cloud (OpenAI, Anthropic, etc.)

### 17.3 Interface de Provider

```python
class ModelProvider(ABC):
    @abstractmethod
    def list_models(self) -> List[ModelInfo]
    
    @abstractmethod
    def generate(self, model: str, prompt: str, **kwargs) -> GenerationResult
    
    @abstractmethod
    def is_available(self) -> bool
```

Implementação atual: `OllamaProvider`

### 17.4 Independência de Modelo

A Abelha **não assume** nenhum modelo específico:

❌ Não hardcode `llama3` ou `gemma2` como únicos  
❌ Não valida modelo contra lista fixa  
✅ Descobre modelos disponíveis  
✅ Seleciona melhor modelo para hardware  
✅ Permite configuração manual  

### 17.5 Configuração de Modelo

```json
{
  "model_provider": "ollama",
  "model_auto_select": true,
  "model_manual_override": null,
  "model_fallback_order": ["llama3.2:3b", "gemma2:2b", "phi3:mini"]
}
```

Se `model_auto_select = true`: seleção automática por hardware  
Se `model_manual_override = "mistral:7b"`: usa este modelo sempre

### 17.6 Versionamento de Protocolo

O protocolo de comunicação não depende da versão do modelo:

```json
{
  "protocol_version": "BEE-0001",
  "model_used": "llama3.2:3b",
  "model_params": 3800000000
}
```

---

## 18. RELAÇÃO COM OLLAMA

### 18.1 Definição

**Ollama é um provider de inferência local, não parte do protocolo da Abelha.**

### 18.2 Responsabilidades do Ollama

| Ollama faz | Ollama NÃO faz |
|------------|----------------|
| Servir modelos LLM via HTTP API | Gerenciar identidade da Abelha |
| Listar modelos instalados | Descobrir outras Abelhas |
| Gerar texto dado prompt | Indexar documentos |
| Rodar localmente | Coordenar Enxame |

### 18.3 Comunicação Abelha ↔ Ollama

```
Abelha                          Ollama
  │                               │
  │ GET /api/tags                 │
  ├──────────────────────────────>│
  │                               │
  │ [lista de modelos]            │
  │<──────────────────────────────┤
  │                               │
  │ POST /api/generate            │
  │ {model, prompt, stream}       │
  ├──────────────────────────────>│
  │                               │
  │ [stream de tokens]            │
  │<──────────────────────────────┤
```

### 18.4 Tratamento de Erros

| Erro Ollama | Ação da Abelha |
|-------------|----------------|
| Connection refused | Marcar Ollama indisponível, operar sem inferência |
| Model not found | Selecionar outro modelo disponível |
| Out of memory | Reduzir contexto, selecionar modelo menor |
| Timeout | Retry com backoff, fallback para próxima fonte |

### 18.5 Configuração

```json
{
  "ollama_base_url": "http://localhost:11434",
  "ollama_timeout_seconds": 60,
  "ollama_retry_count": 3,
  "ollama_retry_delay_seconds": 2
}
```

### 18.6 Múltiplas Instâncias Ollama

Suporte futuro (não implementado inicialmente):
- Ollama em máquina diferente
- Load balancing entre múltiplos Ollamas
- Failover automático

---

## 19. RELAÇÃO COM HERMES E OUTROS AGENTES

### 19.1 Definição

**Hermes é uma possibilidade de agente/modelo, não dependência arquitetural.**

### 19.2 Princípio de Independência

A Abelha:
- ✅ Pode usar Hermes se estiver disponível no Ollama local
- ✅ Pode usar qualquer outro modelo (Llama, Gemma, Mistral, Phi, etc.)
- ✅ Não requer Hermes para funcionar
- ✅ Não assume Hermes como default

### 19.3 Agentes vs. Abelha

| Conceito | Definição |
|----------|-----------|
| **Abelha** | Unidade autônoma do sistema (este documento) |
| **Agente** | Padrão de software que usa modelo para tomar ações |
| **Hermes** | Implementação específica de agente (se existir) |

**Relação:** Uma Abelha pode executar um Agente internamente, mas não é obrigatório.

### 19.4 Plugin de Agente (Futuro)

Arquitetura para suportar agentes como plugins:

```
bees/
├── agents/
│   ├── base.py           # Interface base de agente
│   └── plugins/
│       ├── hermes.py     # Plugin Hermes (opcional)
│       └── simple.py     # Agente simples (default)
```

**Nesta fase:** Não implementar. Apenas deixar arquitetura extensível.

### 19.5 Configuração de Agente

```json
{
  "agent_enabled": false,
  "agent_type": "simple",
  "agent_plugins": []
}
```

Default: agente desabilitado, Abelha opera sem comportamento de agente complexo.

---

## 20. O QUE NÃO FAZ PARTE DA ABELHA NESTA FASE

### 20.1 Funcionalidades Explicitamente Excluídas

| Item | Razão | Futuro |
|------|-------|--------|
| **Inferência distribuída de modelos grandes** | Complexidade desnecessária, foco em autonomia local | Fase posterior |
| **Papel primário/secundário obrigatório** | Viola princípio de generalismo | Nunca (design) |
| **Especialização forçada na instalação** | Viola princípio de generalismo | Nunca (design) |
| **Instalação automática de múltiplos modelos** | Consumo de recursos, decisão do usuário | Talvez (opt-in) |
| **Eleição de líder/juiz** | Arquitetura anterior com papéis fixos | Substituído por mesh |
| **Orquestração centralizada** | Ponto único de falha | Substituído por cooperação P2P |
| **Tradução automática PT-BR** | Específico demais, acoplamento | Plugin opcional |
| **Redis como dependência** | Quebra offline-first, complexidade | Removido |
| **OpenWebUI/OpenRouter integration** | Interfaces externas não essenciais | Plugins futuros |
| **Fragmentação de modelo grande entre Abelhas** | Complexidade de coordenação | Fase muito posterior |

### 20.2 Escopo da Fase Atual (BEE-0001)

**Inclui:**
- ✅ Abelha autônoma standalone
- ✅ Discovery via mDNS
- ✅ Comunicação peer-to-peer básica
- ✅ Bibliotecário local completo
- ✅ RAG local funcional
- ✅ Memória persistente
- ✅ Fluxo LOCAL → ENXAME → WEB
- ✅ Seleção automática de modelo por hardware
- ✅ Offline-first por design

**Não inclui:**
- ❌ Especialização de Abelhas
- ❌ Balanceamento de carga sofisticado
- ❌ Agregação avançada de respostas múltiplas
- ❌ Consenso distribuído
- ❌ Replicação de dados entre Abelhas
- ❌ Migração de contexto entre Abelhas
- ❌ Inferência fragmentada

### 20.3 Critério de Pronto

Uma implementação da Abelha está completa quando:

1. ✅ Consegue rodar sozinha (sem outras Abelhas)
2. ✅ Processa queries usando memória local + RAG local
3. ✅ Descobre outras Abelhas via mDNS
4. ✅ Pergunta a outra Abelha se tem conhecimento relevante
5. ✅ Solicita pesquisa completa a outra Abelha
6. ✅ Segue fluxo LOCAL → ENXAME → WEB
7. ✅ Funciona offline (sem internet)
8. ✅ Seleciona modelo adequado ao hardware
9. ✅ Persiste identidade e memória
10. ✅ Expõe API HTTP básica (/health, /query, /status)

---

## ANEXO A: REFERÊNCIAS A COMPONENTES EXISTENTES

### A.1 Componentes Reutilizáveis (core/)

| Componente | Arquivo | Adaptação Necessária |
|------------|---------|---------------------|
| mDNS Discovery | `core/discovery/mdns_discovery.py` | Remover campo `role` |
| Heartbeat | `core/cluster/election.py` | Extrair apenas HeartbeatManager |
| Benchmark | `core/cluster/benchmark.py` | Nenhum |
| Ollama Client | `core/ollama/client.py` | Adicionar `list_models()`, remover validação fixa |
| Memory | `core/memory/usuario_memory.py` | Renomear classe para `BeeMemory` |
| Input Sanitizer | `core/exp/input_sanitizer.py` | Nenhum |
| Security | `core/exp/security.py` | Nenhum |

### A.2 Componentes Reutilizáveis (bibliotecario/)

| Componente | Arquivo | Adaptação Necessária |
|------------|---------|---------------------|
| Embeddings | `bibliotecario/embeddings.py` | Nenhum |
| Universal Reader | `bibliotecario/universal_reader.py` | Nenhum |
| Indexer | `bibliotecario/indexer.py` | Nenhum |
| LanceDB Store | `bibliotecario/lancedb_store.py` | Nenhum |
| ZIM Reader | `bibliotecario/zim_reader.py` | Nenhum |
| Web Client | `bibliotecario/web_client.py` | Nenhum |
| Search Service | `bibliotecario/search_service.py` | Tornar Redis opcional, remover translator |

### A.3 Componentes a Isolar (não usar inicialmente)

| Componente | Motivo |
|------------|--------|
| `core/cluster/election.py` (ClusterElection) | Eleição de papéis fixos |
| `core/exp/types.py` (ROLE_*, ELECTION_*) | Tipos específicos de papéis |
| `agentes/plugins/*.py` | Especializações fixas |
| `agentes/service.py` | Acoplado a Juiz central |
| `juiz/service.py` | Orquestração centralizada |
| `api/install/node_role_setup.py` | Configuração de papéis fixos |

---

## ANEXO B: GLOSSÁRIO

| Termo | Definição |
|-------|-----------|
| **Abelha** | Unidade autônoma do sistema, roda em uma máquina |
| **Enxame** | Rede de duas ou mais Abelhas cooperando |
| **Bibliotecário** | Componente de indexação, busca e RAG local |
| **RAG** | Retrieval-Augmented Generation |
| **Offline-first** | Projeto que prioriza operação sem internet |
| **Generalista** | Abelha sem especialização fixa, capaz de todas as funções básicas |
| **Capability** | Habilidade funcional anunciada pela Abelha |
| **Peer** | Outra Abelha na rede |
| **mDNS** | Multicast DNS, protocolo de descoberta local |
| **EXP** | Protocolo de comunicação original do Enxame |
| **EXP-Bee** | Subconjunto do EXP adaptado para Abelhas |

---

## ANEXO C: HISTÓRICO DE REVISÕES

| Versão | Data | Autor | Mudanças |
|--------|------|-------|----------|
| 1.0.0 | 2025 | Arquitetura Enxame | Versão inicial baseada na auditoria |

---

## CONSISTÊNCIA ARQUITETURAL

### Verificação contra EIP-0001 e EIP-0002

**Nota:** Os arquivos EIP-0001 e EIP-0002 não foram encontrados no repositório durante a auditoria. Esta verificação é baseada nas referências encontradas no código.

### Potenciais Conflitos Identificados

| Conflito | Severidade | Resolução |
|----------|------------|-----------|
| **Campo `role` no discovery mDNS** | Alto | BEE-0001 especifica `capabilities` no lugar de `role`. Core precisa de atualização backward-compatible. |
| **Tipos ROLE_* e ELECTION_* no EXP** | Alto | BEE-0001 não usa estes tipos. Criar subconjunto EXP-Bee ou versionar protocolo. |
| **Agente Service conectado a Juiz** | Médio | Nova implementação em `bees/` não conecta a Juiz. Coexistência requer portas diferentes. |
| **Redis no Search Service** | Baixo | BEE-0001 usa cache em memória. Backward-compatible pois Redis já era opcional. |

### Recomendações de Mitigação

1. **Namespace isolation:** Manter `bees/` completamente separado até maturidade
2. **Versionamento de protocolo:** Adicionar campo `protocol_version` no mDNS
3. **Coexistência:** Permitir nós tradicionais e Abelhas rodando simultaneamente
4. **Feature flags:** Habilitar novo comportamento via configuração

### Compatibilidade Garantida

✅ Abelha não quebra nós existentes (namespace separado)  
✅ Protocolo EXP tradicional continua funcionando  
✅ Bibliotecário existente permanece intacto  
✅ APIs atuais do Juiz não são modificadas  

---

**FIM DA ESPECIFICAÇÃO BEE-0001**
