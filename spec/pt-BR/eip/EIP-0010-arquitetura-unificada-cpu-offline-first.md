# EIP-0010: Arquitetura Unificada CPU-First, Offline-First e Painel Operacional do Enxame

## Status

**Ativo** — Implementação v2.1 (2026-11-16)

## Resumo

Unifica as camadas `bees/`, `enxame_evolved/`, `guardian/`, `core/` e `web/` com o contrato operacional de 5 camadas do `MANUAL-ASD-STE100-PAINEL-REMOTO.md`, otimizando todo o Enxame para execução **100% em CPU** (incluindo máquinas legadas sem AVX2), com operação **Offline-First estrita**, velocidade de resposta por chamada única em streaming, memória evolutiva de longo prazo, geração de imagens local gratuita em CPU, voz bidirecional offline-first e proveniência ponta a ponta por máquina e modelo.

## Motivação

1. **Estabilidade e Responsividade em Hardware Apenas CPU**: O Enxame deve operar com fluidez desde CPUs legadas (dual-core sem AVX2, pouca RAM) até CPUs multicore modernas. O usuário não deve perceber saltos internos de roteamento, mas deve visualizar de forma clara e honesta o perfil do hardware que está processando (`Legado`, `Padrão`, `Performance`) e a expectativa natural de tempo.
2. **Cascata Offline-First Real**: As máquinas operam offline por padrão. A resolução de uma pergunta segue estritamente:
   - **Nível 1**: Memória Adaptativa + Documentos Locais (RAG FTS5 BM25 / LanceDB + ZIM offline);
   - **Nível 2**: Documentos Distribuídos no Enxame LAN (roteados via *Topic Sketch* no Bibliotecário);
   - **Nível 3**: Conhecimento Paramétrico do Modelo Local em CPU (1 única chamada com streaming SSE);
   - **Nível 4**: Pesquisa na Internet — acionada **somente** se os Níveis 1–3 não possuírem a informação, o fallback web estiver habilitado e o papel no `InternetGate` permitir.
3. **Eliminação de Gargalos de Latência**: Substitui as 3 chamadas sequenciais de LLM (`_analyze_intent` + `search` + `_refine_with_profile`) e o streaming simulado por roteamento instantâneo Zero-LLM (`< 5 ms`) + **1 única passagem de inferência com streaming real de tokens**.
4. **Universalidade e Degradação Graciosa (STE-100 U1–U10)**: Contrato `/ping`, `/estado`, `/saude`, `/config` (com `sem_segredos()`), `/pedido` e `/inventario`, devolvendo `-1` / `"sem dados"` quando uma métrica ou dependência opcional não existir, jamais quebrando o serviço ou a interface.

## Especificação Técnica

### 1. Classificação de Hardware CPU (`HardwareTier`)

Cada nó mede CPU, núcleos, frequência, presença de instruções `AVX2`, RAM total/livre, disco e temperatura, classificando-se automaticamente:

| Tier | Critério | Estimativa Texto (CPU) | Estimativa Imagem (CPU 4-step) |
|---|---|---|---|
| `legado` | `< 4` núcleos físicos, `< 6 GB` RAM ou sem `AVX2` | ~2 a 6 tok/s | ~90 a 240 s |
| `padrao` | `4–7` núcleos e `6–15 GB` RAM | ~8 a 18 tok/s | ~45 a 90 s |
| `performance` | `>= 8` núcleos, `>= 16 GB` RAM e `AVX2` | ~18 a 35 tok/s | ~20 a 45 s |

### 2. Definição de Papéis em Dois Níveis

1. **Papel de Máquina no Cluster (`ClusterRole`)**: `juiz` (orquestrador líder), `bibliotecario` (índice global de documentos), `guarda` (auditoria e segurança), `worker` (execução geral) e `worker_artist` (geração local de mídia em CPU). Funciona para `1, 2, 3..N` máquinas com consolidação automática de papéis secundários e suporte a fixação manual (`pinned_role`).
2. **Perfil Cognitivo da Tarefa (`AgentProfile`)**: `generalist`, `coder`, `architect`, `researcher`, `analyst`, `legal`, `medical`, `creative`, `artist` — selecionado em `< 5 ms` pelo `FastIntentRouter` ou escolhido manualmente pelo usuário.

### 3. RAG Local Incremental + Push de *Topic Sketch* ao Bibliotecário

- Indexação local incremental em SQLite **FTS5 (BM25)** (compatível com 100% das CPUs sem AVX2) + `LanceDB` opcional.
- Ao iniciar ou ingerir documentos (`/api/v1/ingest`), cada nó extrai um `TopicSketch` leve (`doc_count`, `chunk_count`, termos ponderados BM25 e resumo por arquivo) e envia via push (`INDEX_ADVERTISE` / `/api/v1/rag/sketch`) ao nó `Bibliotecário`, sem transferir os documentos brutos pela rede.

### 4. Guardião Gatekeeper em 4 Estágios

1. **Gatekeeper de Entrada (`ALLOW` | `CONTAIN` | `BLOCK`)**: bloqueia *jailbreaks*, sobrescrita de prompt de sistema e exfiltração de segredos; isola código técnico legítimo com delimitadores dotados de *nonce* criptográfico único por requisição (`<<<ENTRADA_USUARIO_{nonce}>>>`).
2. **Escudo de Contexto RAG/Web**: sanitiza e encapsula trechos externos recuperados (`<<<FONTE_DOCUMENTAL_{nonce}>>>`) contra *Indirect Prompt Injection*.
3. **Proteção de Segredos e Transporte**: `sem_segredos()` em `/config`, `hmac.compare_digest` para tokens e validação estrita de envelopes.
4. **Ronda Assíncrona (`GuardianPatrol`)**: telemetria contínua de anomalias e registro auditável em SQLite.

### 5. Persistência Unificada: Histórico de Chat, Manutenção de Contexto e Memória Evolutiva

Banco SQLite em modo `WAL` (`enxame_unified.db`) com conexões isoladas por operação:
- `conversations` + `messages` + `messages_fts` (busca instantânea FTS5 no histórico);
- `ConversationContextManager`: orçamento de tokens combinando `System + Perfil Evolutivo + Memória Semântica + Resumo Deslizante (rolling_summary) + Últimos Turnos`, portável entre máquinas na delegação;
- `user_profile` + `semantic_memories`: consolidação assíncrona pós-resposta adaptando profundidade técnica, formato preferido e fatos duráveis conforme evolução e feedback do usuário.

### 6. Voz Bidirecional Offline-First e Estúdio de Imagens Gratuito em CPU

- **Voz (STT/TTS)**: `/api/v1/audio/transcribe` (`faster-whisper` CPU INT8 / CLI local + fallback navegador) e `/api/v1/audio/synthesize` (`piper-tts` CPU / TTS nativo offline do SO `espeak-ng`/`say`/SAPI + fallback `speechSynthesis` local).
- **Imagens em CPU (`LocalCpuImageStudio`)**: fila assíncrona dedicada (`max_workers=1` em CPU para preservar responsividade do chat) com progresso por etapa via WebSocket, suportando motores gratuitos open-source: `stable-diffusion.cpp` (GGUF CPU), `diffusers` CPU (`sd-turbo` / `tiny-sd` / `LCM` em 1–4 passos), detecção oportunista de `ComfyUI`/`Forge` locais e renderizador vetorial/raster procedural determinístico offline (`Pillow`) quando pesos externos ainda não estiverem instalados, com auto-revisão óptica de qualidade.

### 7. Carimbo Obrigatório de Proveniência (`ProvenanceStamp`)

Toda resposta de chat e toda imagem gerada inclui e persiste `provenance`:
- `machine_alias`, `node_id`, `platform`, `hardware_tier`, `cluster_role`, `agent_profile`, `model`, `source_tier`, `rag_sources`, `route_trace`, `ttft_ms` e `total_ms`.

## Referências

- EIP-0001 (Architecture First), EIP-0002 (Resource First), EIP-0006 (Knowledge Authority), EIP-0008 (Resource Preservation), EIP-0009 (Cluster Role Election)
- BEE-0001, BEE-0002, BEE-0003
- `MANUAL-ASD-STE100-PAINEL-REMOTO.md` (Regras de Universalidade U1–U10)
