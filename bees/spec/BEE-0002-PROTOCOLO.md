# BEE-0002 — PROTOCOLO DE COMUNICAÇÃO ENTRE ABELHAS

**Versão:** 1.0  
**Status:** Normativo  
**Data:** 2025  
**Autoria:** Arquitetura Enxame  
**Revisão:** Inicial

---

## 1. OBJETIVO

Definir o protocolo mínimo de comunicação entre Abelhas que permita:

1. Descoberta automática em rede local
2. Handshake inicial seguro
3. Troca de manifesto de capabilities
4. Consulta e resposta entre pares
5. Detecção de indisponibilidade
6. Compatibilidade multiplataforma

Este protocolo é **independente** de:
- Sistema operacional (Windows, Linux, macOS)
- Arquitetura de CPU (x86_64, ARM64)
- Provider de LLM (Ollama, outros)
- Modelo específico (Hermes, Llama, Gemma, etc.)

---

## 2. PRINCÍPIOS NORMATIVOS

### 2.1 Reutilização First

O protocolo DEVE reutilizar mecanismos existentes no repositório sempre que possível:

- **Discovery:** mDNS/Zeroconf existente em `core/discovery/`
- **Envelope:** Estrutura EXP existente em `core/exp/envelope.py`
- **Segurança:** HMAC existente em `core/exp/security.py`
- **Transporte:** WebSocket existente em `core/exp/server.py` e `core/exp/client.py`

### 2.2 Minimalismo

O protocolo DEVE ser pequeno. Cada mensagem deve ter propósito claro.

### 2.3 Versionamento

Todas as mensagens DEVEM incluir versão do protocolo para compatibilidade futura.

### 2.4 Offline First

O protocolo DEVE funcionar em rede local sem internet. Internet é fallback opcional.

### 2.5 Generalismo

Abelhas NÃO possuem papéis fixos. Todas são generalistas inicialmente.

---

## 3. IDENTIDADE DA ABELHA

### 3.1 Estrutura de Identidade

Cada Abelha possui identidade única composta por:

```python
@dataclass
class BeeIdentity:
    node_id: str           # UUID v4 único
    public_key: str        # Chave pública Ed25519 (base64)
    host: str              # IP ou hostname
    port: int              # Porta de escuta WebSocket
    protocol_version: str  # Versão do protocolo BEE
    timestamp: datetime    # Momento de criação da identidade
```

### 3.2 Geração de Identidade

A identidade É GERADA na primeira inicialização e PERSISTIDA localmente.

**Local de persistência:** `~/.enxame/bees/identity.json`

**Não regenerar** a menos que o usuário solicite reset explícito.

---

## 4. DISCOVERY (REUTILIZAÇÃO)

### 4.1 Mecanismo

O protocolo REUTILIZA o mecanismo mDNS existente em `core/discovery/`.

**Service Type:** `_enxame._tcp.local.`

**Campos anunciados:**
| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `node_id` | string | Sim | UUID da Abelha |
| `host` | string | Sim | IP de escuta |
| `port` | int | Sim | Porta WebSocket |
| `protocol_version` | string | Sim | Versão BEE (ex: "1.0") |
| `capabilities` | string | Não | Lista JSON de capacidades |
| `models` | string | Não | Modelos Ollama disponíveis |
| `load` | float | Não | Carga atual (0.0-1.0) |

### 4.2 Adaptação do Discovery Existente

O discovery existente EMITE campo `role` para backward compatibility.

Para Abelhas, o campo `role` DEVE ser `"bee"` (valor literal).

Capacidades reais são comunicadas via campo `capabilities` (JSON array).

### 4.3 Exemplo de Anúncio mDNS

```json
{
  "node_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "bee",
  "host": "192.168.1.100",
  "port": 8765,
  "protocol_version": "1.0",
  "capabilities": "[\"rag\", \"ocr\", \"embeddings\"]",
  "models": "[\"llama3:8b\", \"gemma2:9b\"]",
  "load": "0.3"
}
```

---

## 5. HANDSHAKE

### 5.1 Sequência de Handshake

```
Abelha A                          Abelha B
   |                                 |
   |-------- HELLO (manifesto) ------>|
   |                                 |
   |<------ HELLO_ACK (manifesto) ---|
   |                                 |
   |--------- HEARTBEAT ------------>|
   |                                 |
   |<-------- HEARTBEAT_ACK ---------|
   |                                 |
   |         [Conexão estabelecida]  |
```

### 5.2 Mensagem HELLO

**Tipo:** `BEE_HELLO`

**Payload:**
```json
{
  "identity": {
    "node_id": "uuid-a",
    "public_key": "base64-pubkey-a",
    "protocol_version": "1.0"
  },
  "manifesto": {
    "capabilities": ["rag", "ocr", "embeddings"],
    "models": ["llama3:8b"],
    "indexes": ["documents", "zim"],
    "load": 0.3,
    "uptime_seconds": 3600
  },
  "nonce": "random-bytes-base64"
}
```

### 5.3 Mensagem HELLO_ACK

**Tipo:** `BEE_HELLO_ACK`

**Payload:**
```json
{
  "identity": {
    "node_id": "uuid-b",
    "public_key": "base64-pubkey-b",
    "protocol_version": "1.0"
  },
  "manifesto": {
    "capabilities": ["rag", "embeddings"],
    "models": ["gemma2:9b"],
    "indexes": ["documents"],
    "load": 0.5,
    "uptime_seconds": 7200
  },
  "nonce": "random-bytes-base64",
  "echo_nonce": "nonce-do-hello-original"
}
```

### 5.4 Validação de Handshake

1. Verificar `protocol_version` compatível
2. Validar assinatura HMAC (se shared_secret configurado)
3. Confirmar `echo_nonce` bate com nonce original
4. Armazenar identidade e manifesto remoto

---

## 6. MANIFESTO

### 6.1 Propósito

O manifesto informa metadados suficientes para outra Abelha decidir:

> **"Vale a pena consultar esta Abelha?"**

### 6.2 Estrutura do Manifesto

```python
@dataclass
class BeeManifesto:
    capabilities: list[str]    # Habilidades disponíveis
    models: list[str]          # Modelos Ollama locais
    indexes: list[str]         # Índices de conhecimento disponíveis
    load: float                # Carga atual (0.0 = ocioso, 1.0 = sobrecarregado)
    uptime_seconds: int        # Tempo desde inicialização
    last_activity: datetime    # Última atividade de processamento
    version: str               # Versão do software da Abelha
```

### 6.3 Capabilities Conhecidas

| Capability | Descrição | Quando anunciar |
|------------|-----------|-----------------|
| `rag` | Possui RAG local com documentos indexados | Sempre se tiver LanceDB/Qdrant |
| `ocr` | Suporte a OCR para imagens/PDFs | Se Tesseract disponível |
| `embeddings` | Gera embeddings localmente | Se modelo de embeddings disponível |
| `zim` | Possui arquivos ZIM offline | Se tiver arquivos .zim |
| `web_fallback` | Acesso à internet habilitado | Apenas se config permitir |
| `large_context` | Suporta contexto > 32K tokens | Se modelo suportar |

### 6.4 Models

Lista de modelos Ollama disponíveis localmente.

**Formato:** Nomes exatos como retornados por `ollama list`

**Exemplo:** `["llama3:8b", "gemma2:9b", "nomic-embed-text"]`

### 6.5 Indexes

Lista de índices de conhecimento disponíveis.

**Valores comuns:**
- `documents` - Documentos indexados localmente
- `zim` - Arquivos ZIM carregados
- `memory` - Memória de conversas/histórico
- `custom:<name>` - Índices customizados

### 6.6 Load

Carga atual da Abelha para balanceamento.

**Cálculo sugerido:**
```python
load = (cpu_percent / 100 + queue_size / max_queue) / 2
```

**Interpretação:**
- `0.0 - 0.3`: Disponível para novas consultas
- `0.3 - 0.7`: Ocupado, mas aceita consultas importantes
- `0.7 - 1.0`: Sobrecarregado, apenas consultas críticas

---

## 7. CAPABILITIES

### 7.1 Definição

Capabilities são habilidades dinâmicas que uma Abelha pode executar.

Diferente de papéis fixos, capabilities:
- Podem mudar durante runtime
- São descobertas automaticamente
- Múltiplas Abelhas podem ter mesma capability
- Uma Abelha pode ter zero ou muitas capabilities

### 7.2 Descoberta de Capabilities

Capabilities são descobertas via:
1. **mDNS** - Campo `capabilities` no anúncio
2. **Manifesto** - Durante handshake
3. **Query direta** - Mensagem `CAPABILITY_QUERY`

### 7.3 Query de Capability

Quando uma Abelha quer saber se outra tem capacidade específica:

```json
{
  "type": "CAPABILITY_QUERY",
  "payload": {
    "capability": "rag",
    "subject": "direito tributário"
  }
}
```

Resposta:
```json
{
  "type": "CAPABILITY_RESPONSE",
  "payload": {
    "has_capability": true,
    "confidence": 0.85,
    "document_count": 12,
    "last_updated": "2025-01-15T10:30:00Z"
  }
}
```

---

## 8. ESTADO DA ABELHA

### 8.1 Estados Válidos

| Estado | Descrição | Transições permitidas |
|--------|-----------|----------------------|
| `STOPPED` | Abelha não está rodando | → STARTING |
| `STARTING` | Inicializando componentes | → RUNNING, → STOPPED |
| `RUNNING` | Operacional | → STOPPING, → DEGRADED |
| `STOPPING` | Finalizando graceful | → STOPPED |
| `DEGRADED` | Operacional com limitações | → RUNNING, → STOPPING |

### 8.2 Comunicação de Estado

Estado é comunicado via:
- **Heartbeat** - Campo `state` em cada heartbeat
- **Mudança abrupta** - Mensagem `STATE_CHANGE` se entrar em DEGRADED

### 8.3 Estado DEGRADED

Uma Abelha entra em estado DEGRADED quando:
- Ollama indisponível
- Disco cheio (> 95%)
- Memória crítica (< 5% livre)
- Índice corrompido

Neste estado, a Abelha:
- Continua respondendo heartbeats
- Anuncia carga = 1.0 (não aceitar novas consultas)
- Pode ainda responder consultas em andamento

---

## 9. HEARTBEAT

### 9.1 Propósito

Heartbeat mantém sessão ativa e monitora saúde da conexão.

### 9.2 Intervalo

**Padrão:** 5 segundos

**Timeout:** 15 segundos (3 heartbeats perdidos)

### 9.3 Mensagem HEARTBEAT

**Tipo:** `BEE_HEARTBEAT`

**Payload:**
```json
{
  "node_id": "uuid-a",
  "state": "RUNNING",
  "load": 0.3,
  "timestamp": "2025-01-15T10:30:00Z",
  "sequence": 142
}
```

### 9.4 Resposta HEARTBEAT_ACK

**Tipo:** `BEE_HEARTBEAT_ACK`

**Payload:**
```json
{
  "node_id": "uuid-b",
  "state": "RUNNING",
  "load": 0.5,
  "timestamp": "2025-01-15T10:30:05Z",
  "sequence": 89,
  "ack_sequence": 142
}
```

### 9.5 Detecção de Falha

Se 3 heartbeats consecutivos não forem respondidos:

1. Marcar Abelha remota como `UNREACHABLE`
2. Enviar notificação `PEER_LOST` para listeners locais
3. Remover da lista de peers ativos
4. Manter em cache por 60s (pode retornar)

---

## 10. CONSULTA (QUERY)

### 10.1 Tipos de Consulta

| Tipo | Descrição | Quando usar |
|------|-----------|-------------|
| `KNOWLEDGE_QUERY` | "Você tem conhecimento sobre X?" | Antes de pesquisa completa |
| `RESEARCH_REQUEST` | "Pesquise X com contexto Y" | Quando precisa de resposta completa |
| `MODEL_REQUEST` | "Gere resposta usando seu modelo" | Quando precisa de inferência |

### 10.2 KNOWLEDGE_QUERY

Consulta leve para verificar se vale a pena enviar pesquisa completa.

**Tipo:** `BEE_KNOWLEDGE_QUERY`

**Payload:**
```json
{
  "query_id": "uuid-query-123",
  "subject": "direito tributário brasileiro",
  "keywords": ["tributário", "impostos", "Brasil"],
  "min_confidence": 0.6,
  "timeout_ms": 2000
}
```

**Resposta esperada (rápida):**
```json
{
  "type": "BEE_KNOWLEDGE_RESPONSE",
  "payload": {
    "query_id": "uuid-query-123",
    "has_knowledge": true,
    "confidence": 0.85,
    "document_count": 12,
    "topics": ["ICMS", "ISS", "IRPJ"],
    "oldest_doc": "2020-01-01",
    "newest_doc": "2024-12-15"
  }
}
```

### 10.3 RESEARCH_REQUEST

Solicitação de pesquisa completa com RAG local.

**Tipo:** `BEE_RESEARCH_REQUEST`

**Payload:**
```json
{
  "request_id": "uuid-req-456",
  "query": "Quais são os impostos federais no Brasil?",
  "context": "Preciso de lista completa com alíquotas atuais",
  "max_results": 10,
  "include_sources": true,
  "timeout_ms": 30000
}
```

**Resposta:**
```json
{
  "type": "BEE_RESEARCH_RESULT",
  "payload": {
    "request_id": "uuid-req-456",
    "results": [
      {
        "content": "IRPJ: 15% + 10% adicional...",
        "source": "documento_xyz.pdf",
        "confidence": 0.92,
        "page": 5
      }
    ],
    "total_results": 5,
    "processing_time_ms": 1250,
    "model_used": "llama3:8b",
    "sources_included": true
  }
}
```

### 10.4 MODEL_REQUEST

Solicitação de inferência/generação usando modelo local.

**Tipo:** `BEE_MODEL_REQUEST`

**Payload:**
```json
{
  "request_id": "uuid-model-789",
  "prompt": "Explique diferença entre ICMS e ISS",
  "system_prompt": "Você é assistente jurídico especializado",
  "max_tokens": 500,
  "temperature": 0.7,
  "timeout_ms": 60000
}
```

**Resposta:**
```json
{
  "type": "BEE_MODEL_RESPONSE",
  "payload": {
    "request_id": "uuid-model-789",
    "generation": "ICMS é imposto estadual... ISS é municipal...",
    "model_used": "llama3:8b",
    "tokens_used": 342,
    "processing_time_ms": 4500,
    "finish_reason": "stop"
  }
}
```

---

## 11. RESPOSTA

### 11.1 Estrutura Comum

Todas as respostas seguem padrão:

```python
@dataclass
class BeeResponse:
    request_id: str          # Correlação com request original
    success: bool            # True se processado com sucesso
    data: Any                # Payload específico
    error: str | None        # Código de erro se falhou
    error_detail: str | None # Detalhe humano do erro
    processing_time_ms: int  # Tempo de processamento
    model_used: str | None   # Modelo utilizado (se aplicável)
```

### 11.2 Códigos de Erro

| Código | Descrição | Ação recomendada |
|--------|-----------|------------------|
| `OK` | Sucesso | - |
| `NOT_FOUND` | Conhecimento não encontrado | Tentar outra Abelha ou web |
| `TIMEOUT` | Timeout na operação | Retry com timeout maior |
| `OVERLOADED` | Abelha sobrecarregada | Tentar outra Abelha |
| `UNSUPPORTED` | Capability não suportada | Não reenviar este tipo |
| `AUTH_FAILED` | Falha de autenticação | Verificar credenciais |
| `VERSION_MISMATCH` | Versão incompatível | Atualizar protocolo |
| `INTERNAL_ERROR` | Erro interno | Log e reportar |

### 11.3 Resposta Parcial

Se timeout ocorrer durante processamento longo:

```json
{
  "type": "BEE_RESEARCH_RESULT",
  "payload": {
    "request_id": "uuid-req-456",
    "partial": true,
    "results": [...],
    "more_available": true,
    "continue_token": "token-xyz"
  }
}
```

---

## 12. TIMEOUT

### 12.1 Timeouts Padrão

| Operação | Timeout Padrão | Máximo |
|----------|----------------|--------|
| Handshake | 5000 ms | 10000 ms |
| Heartbeat | 5000 ms | 15000 ms |
| Knowledge Query | 2000 ms | 5000 ms |
| Research Request | 30000 ms | 120000 ms |
| Model Request | 60000 ms | 300000 ms |
| Connection idle | 300000 ms | 600000 ms |

### 12.2 Comportamento em Timeout

1. Cancelar operação pendente
2. Liberar recursos associados
3. Notificar solicitante com erro `TIMEOUT`
4. Opcional: Retry com backoff exponencial

### 12.3 Backoff Exponencial

Para retries automáticos:

```python
delay = min(base_delay * (2 ** attempt), max_delay)
# base_delay = 1000ms, max_delay = 30000ms
```

---

## 13. ABELHA TEMPORARIAMENTE INDISPONÍVEL

### 13.1 Cenários de Indisponibilidade

- Reinício programado
- Atualização de software
- Problema de rede temporário
- Sobrecarga extrema

### 13.2 Mensagem STATE_CHANGE

Quando Abelha vai ficar indisponível:

**Tipo:** `BEE_STATE_CHANGE`

**Payload:**
```json
{
  "node_id": "uuid-a",
  "new_state": "STOPPING",
  "reason": "maintenance",
  "estimated_return_seconds": 120,
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### 13.3 Comportamento de Peers

Ao receber `STATE_CHANGE`:

1. Parar de enviar novas consultas
2. Aguardar `estimated_return_seconds`
3. Após timeout, tratar como `PEER_LOST`
4. Tentar reconectar periodicamente

### 13.4 Mensagem PEER_LOST

Quando peer é considerado perdido:

**Tipo:** `BEE_PEER_LOST`

**Payload:**
```json
{
  "node_id": "uuid-a",
  "last_seen": "2025-01-15T10:25:00Z",
  "reason": "heartbeat_timeout",
  "missed_heartbeats": 3
}
```

---

## 14. SEGURANÇA

### 14.1 Autenticação

O protocolo SUPORTA dois modos:

**Modo 1: Shared Secret (existente)**
- Reutiliza `EXPSecurity` de `core/exp/security.py`
- HMAC-SHA256 com chave compartilhada
- Adequado para redes locais confiáveis

**Modo 2: Sem autenticação**
- Para desenvolvimento/testing
- NÃO recomendado em produção

### 14.2 Assinatura de Mensagens

Todas as mensagens DEVEM ser assinadas (quando autenticação habilitada):

```python
signature = HMAC-SHA256(shared_secret, canonical_json(payload))
```

### 14.3 Validação de Timestamp

Timestamp fora de janela de 60 segundos DEVEM ser rejeitados.

### 14.4 Sanitização de Input

Todo input de Abelha remota DEVE passar por sanitização:
- Reutilizar `input_sanitizer.py` de `core/exp/`
- Prevenir prompt injection
- Validar tamanhos máximos

---

## 15. VERSIONAMENTO

### 15.1 Versão Atual

**Protocolo BEE:** `1.0`

**Compatibilidade:**
- `1.x` são compatíveis entre si
- `2.0` será breaking change

### 15.2 Negociação de Versão

Durante handshake:

```
HELLO: protocol_version = "1.0"
HELLO_ACK: protocol_version = "1.0" (ou menor compatível)
```

Se versões incompatíveis:
```
ERROR: {
  "code": "VERSION_MISMATCH",
  "detail": "Expected 1.x, got 2.0",
  "supported_versions": ["1.0", "1.1"]
}
```

### 15.3 Extensibilidade

Novos tipos de mensagem podem ser adicionados em versões menores:
- `1.0`: Tipos básicos (HELLO, QUERY, RESPONSE)
- `1.1`: Novos tipos (STREAM, BATCH)
- `2.0`: Mudanças estruturais

---

## 16. INDEPENDÊNCIA DE PLATAFORMA

### 16.1 Sistemas Operacionais Suportados

| SO | Versões | Status |
|----|---------|--------|
| Linux | Kernel 4.x+ | ✅ Nativo |
| macOS | 11+ (Big Sur) | ✅ Nativo |
| Windows | 10+ | ✅ Nativo |

### 16.2 Endianness

Protocolo usa JSON UTF-8, independente de endianness.

### 16.3 Paths de Arquivo

Paths devem usar separadores nativos do SO:
- Linux/macOS: `/home/user/.enxame`
- Windows: `C:\Users\user\.enxame`

### 16.4 Rede

- IPv4 obrigatório
- IPv6 opcional
- Portas: 8765 (padrão WebSocket)

---

## 17. INDEPENDÊNCIA DE PROVIDER/MODELO

### 17.1 Providers Suportados

| Provider | Status | Notas |
|----------|--------|-------|
| Ollama | ✅ Primário | HTTP API local |
| OpenAI API | ⚠️ Futuro | Via plugin |
| LM Studio | ⚠️ Futuro | Compatível com Ollama |
| LocalAI | ⚠️ Futuro | API compatível |

### 17.2 Modelos

O protocolo NÃO depende de modelo específico.

Modelos são identificados por nome string:
- `"llama3:8b"`
- `"gemma2:9b"`
- `"hermes-llama3:latest"`

### 17.3 Seleção de Modelo

Cada Abelha decide qual modelo usar baseado em:
- Recursos locais (RAM, CPU, GPU)
- Tipo de tarefa (embeddings vs generation)
- Preferências de configuração

---

## 18. RELAÇÃO COM OLLAMA

### 18.1 Ollama é Provider, Não Protocolo

Ollama é APENAS um provider de inferência local.

O protocolo BEE funciona independentemente do Ollama.

### 18.2 Descoberta de Modelos

Abelha DEVE descobrir modelos Ollama disponíveis:

```python
GET http://localhost:11434/api/tags
→ {"models": [{"name": "llama3:8b"}, ...]}
```

### 18.3 Uso de Modelos

Abelha USA Ollama para:
- Gerar embeddings
- Inferência/generação de texto
- RAG local

### 18.4 Fallback sem Ollama

Se Ollama indisponível, Abelha:
- Entra em estado `DEGRADED`
- Anuncia `load = 1.0`
- Pode ainda servir documentos indexados
- Encaminha queries para outras Abelhas

---

## 19. RELAÇÃO COM HERMES E OUTROS AGENTES

### 19.1 Hermes é Opcional

Hermes é UM POSSÍVEL agente/modelo.

O protocolo NÃO depende de Hermes.

### 19.2 Outros Agentes

Qualquer agente pode rodar dentro de uma Abelha:
- Agente de pesquisa
- Agente de código
- Agente jurídico
- Agente médico

### 19.3 Plugins

Agentes externos podem ser carregados como plugins:
- Hot-load sem restart
- Registro de capabilities dinâmico
- Isolamento de falhas

---

## 20. O QUE NÃO FAZ PARTE DESTA FASE

### 20.1 Fora do Escopo Atual

| Funcionalidade | Status | Razão |
|----------------|--------|-------|
| Inferência distribuída de modelos grandes | ❌ Futuro | Complexidade desnecessária |
| Fragmentação de modelo entre Abelhas | ❌ Futuro | Latência alta |
| Papéis fixos (Juiz, Bibliotecário) | ❌ Obsoleto | Arquitetura baseada em capabilities |
| Eleição de líder | ❌ Obsoleto | Peer-to-peer puro |
| Síntese centralizada de respostas | ❌ Futuro | Cada Abelha sintetiza localmente |
| Streaming de tokens entre Abelhas | ❌ Futuro | Otimização prematura |
| Compressão de payload | ❌ Futuro | Otimização prematura |
| Criptografia assimétrica | ❌ Futuro | HMAC suficiente para LAN |
| NAT traversal / Internet direta | ❌ Futuro | Foco em rede local |

### 20.2 Instalação de Múltiplos Modelos

O protocolo NÃO instala múltiplos modelos automaticamente.

Cada Abelha instala APENAS o modelo adequado ao seu hardware.

### 20.3 Especialização Forçada

Abelhas NÃO são especializadas inicialmente.

Especialização pode emergir organicamente por:
- Configuração manual
- Aprendizado de uso
- Capacidades de hardware

---

## 21. EXEMPLOS DE FLUXO

### 21.1 Fluxo Completo: Descoberta → Consulta

```
[Abelha A]                                      [Abelha B]
     |                                               |
     |-- mDNS: "Olá, sou bee-abc, tenho RAG" ------->|
     |<-- mDNS: "Olá, sou bee-xyz, tenho RAG" -------|
     |                                               |
     |-- WS HELLO (manifesto completo) ------------->|
     |<-- WS HELLO_ACK (manifesto completo) ---------|
     |                                               |
     |-- HEARTBEAT (a cada 5s) -------------------->|
     |<-- HEARTBEAT_ACK ----------------------------|
     |                                               |
     |-- KNOWLEDGE_QUERY: "tem direito tributário?" ->|
     |<-- KNOWLEDGE_RESPONSE: "sim, 12 docs" --------|
     |                                               |
     |-- RESEARCH_REQUEST: "pesquise impostos" ----->|
     |<-- RESEARCH_RESULT: [resultados] -------------|
     |                                               |
```

### 21.2 Fluxo: Peer Desaparece

```
[Abelha A]                                      [Abelha B]
     |                                               |
     |-- HEARTBEAT -------------------------------->|
     |                                               |
     |  [rede cai, B não responde]                  |
     |                                               |
     |-- HEARTBEAT (sem resposta) ----------------->|
     |-- HEARTBEAT (sem resposta) ----------------->|
     |-- HEARTBEAT (sem resposta) ----------------->|
     |                                               |
     |  [3 heartbeats perdidos = 15s]               |
     |                                               |
     |  Marca B como UNREACHABLE                    |
     |  Remove de peers ativos                      |
     |  Notifica listeners locais                   |
     |                                               |
     |  [aguarda 60s]                               |
     |                                               |
     |  Tenta reconectar                            |
     |  Se sucesso: restabelece conexão             |
     |  Se falha: remove definitivamente            |
```

---

## 22. REFERÊNCIAS

### 22.1 Especificações Relacionadas

- **BEE-0001** — Conceito de Abelha
- **EIP-0001** — Architecture First
- **EIP-0002** — Resource First
- **EIP-0003** — Dynamic Capability Discovery

### 22.2 Implementações de Referência

- `core/discovery/mdns_discovery.py` — Discovery mDNS
- `core/exp/envelope.py` — Estrutura de mensagens
- `core/exp/security.py` — Autenticação HMAC
- `core/exp/server.py` — Servidor WebSocket
- `core/exp/client.py` — Cliente WebSocket

---

## 23. HISTÓRICO DE REVISÕES

| Versão | Data | Autor | Mudanças |
|--------|------|-------|----------|
| 1.0 | 2025-01 | Arquitetura | Versão inicial normativa |

---

**FIM DA ESPECIFICAÇÃO BEE-0002**
