# EIP-0009: Eleição de Papéis e Gerenciamento de Cluster Enxame

## Status

**Proposto** - Em revisão

## Resumo

Define o sistema de eleição de papéis (Juiz, Bibliotecário, Guarda, Workers) em um cluster Enxame com 3+ máquinas descobertas, incluindo consolidação de papéis, failover automático, indexação distribuída e controle de acesso à internet.

## Motivação

O Enxame atual opera como Abelhas standalone (BEE-0001) com descoberta mDNS e protocolo BEE (BEE-0002). Para formar um Enxame funcional, é necessário:

- Eleição automática de papéis críticos
- Consolidação inteligente quando há poucas máquinas
- Failover transparente com timeout de 72h
- Indexação global distribuída via Bibliotecário
- Controle granular de acesso à internet

## Princípios

### 1. Eleição Baseada em Capabilities (BEE-0003)

Papéis são eleitos com base nas capabilities descobertas:
- **Juiz**: Requer `llm_inference`, `rag`, `memory`, `query` - melhor CPU/RAM
- **Bibliotecário**: Requer `rag`, `embeddings`, `vector_search`, `index`, `ocr`, `zim` - melhor armazenamento
- **Guarda**: Requer `security`, `audit`, `monitoring` - máquina dedicada ou a mais segura
- **Workers**: Capabilities restantes, especialização por hardware (GPU = Artist)

### 2. Consolidação de Papéis (Menos Máquinas = Mais Funções)

| Máquinas | Juiz | Bibliotecário | Guarda | Workers |
|----------|------|---------------|--------|---------|
| 3 | M1 | M2 | M3 | M1+M2+M3 (secundário) |
| 4 | M1 | M2 | M3 | M4 (primário), M1-3 (sec) |
| 5+ | Dedicado | Dedicado | Dedicado | Restantes |

**Regra**: Papel primário = responsabilidade total. Papel secundário = executa se necessário, mas não é dono.

### 3. Worker Artist (GPU)

- Máquinas com GPU detectada (BEE-0003 §3.4) → Worker Artist primário
- Função primária: geração de imagens/vídeos via modelos de visão
- Ociosidade → Worker secundário genérico
- Prioridade de tarefas: visão > geração texto > RAG

### 4. Failover de Juiz (EIP-0005)

```
Juiz cai → Próximo eleito assume temporariamente
    │
    ├─ Juiz original volta em < 72h → Retoma, temporário encerra
    └─ Juiz não volta em 72h → Nova eleição completa
```

- Monitoramento via heartbeat (BEE-0002 §9) + `STATE_CHANGE`
- Eleição usa critério: maior uptime + capabilities completas + menor load
- Estado persistido em `~/.enxame/cluster_state.json`

### 5. Bibliotecário Global (Indexação Distribuída)

```
Bibliotecário eleito:
  1. Coleta manifesto de cada peer (KNOWLEDGE_QUERY + RESEARCH_REQUEST)
  2. Constrói índice global: {assunto → [peer_id, confidence, doc_count]}
  3. Roteia queries: "Quem tem direito tributário?" → Peer com maior confidence
  4. Só vai para internet se NENHUM peer tiver o conhecimento
```

### 6. Controle de Acesso à Internet

| Papel | Acesso | Finalidade |
|-------|--------|------------|
| Juiz | Sim | Ponderação de respostas conflitantes, decisão final |
| Bibliotecário | Sim | Fallback de conhecimento (último recurso) |
| Guarda | Sim | Aprender novas técnicas de ataque/defesa, assinaturas de malware |
| Workers | Não | Operação puramente offline |

## Especificação Técnica

### 6.1 Estado do Cluster

```python
@dataclass
class ClusterState:
    epoch: int                    # Incrementa a cada eleição
    juiz_id: str | None           # Node ID do Juiz eleito
    bibliotecario_id: str | None  # Node ID do Bibliotecário eleito
    guarda_id: str | None         # Node ID do Guarda eleito
    workers: list[str]            # Node IDs dos Workers
    artist_workers: list[str]     # Subset com GPU
    juiz_failover_started: datetime | None  # Para contagem 72h
    last_election: datetime
    manifesto_version: dict[str, int]  # node_id -> versão manifesto
```

### 6.2 Algoritmo de Eleição

```python
def elect_roles(peers: list[DiscoveredPeer]) -> ClusterState:
    # 1. Ordenar por score de adequação
    scored = [(score_peer(p), p) for p in peers]
    scored.sort(reverse=True)  # Melhor primeiro
    
    # 2. Atribuir papéis primários
    juiz = scored[0].peer if has_capabilities(scored[0].peer, JUIZ_CAPS) else None
    bibliotecario = next((p for s,p in scored if p != juiz and has_capabilities(p, BIB_CAPS)), None)
    guarda = next((p for s,p in scored if p not in {juiz, bibliotecario} and has_capabilities(p, GUARDA_CAPS)), None)
    
    # 3. Workers = restantes
    workers = [p for s,p in scored if p not in {juiz, bibliotecario, guarda}]
    artist = [p for p in workers if p.hardware.gpu_available]
    
    # 4. Consolidação se poucos peers
    if len(peers) == 3:
        # Todos são workers secundários
        for p in peers:
            p.secondary_worker = True
    
    return ClusterState(...)
```

### 6.3 Critérios de Score

```python
def score_peer(peer: DiscoveredPeer) -> float:
    score = 0.0
    # Hardware (40%)
    score += peer.hardware.ram_gb * 0.5
    score += peer.hardware.cpu_cores * 2
    if peer.hardware.gpu_available:
        score += peer.hardware.gpu_vram_gb * 3
    # Capabilities (30%)
    score += len(peer.capabilities) * 5
    # Load invertido (20%) - menos load = melhor
    score += (1.0 - peer.load) * 20
    # Uptime (10%)
    score += min(peer.uptime_seconds / 3600, 24) * 0.5
    return score
```

### 6.4 Protocolo de Failover

1. **Detecção**: 3 heartbeats perdidos (15s, BEE-0002 §9.5) → `PEER_LOST`
2. **Verificação**: Se `peer.node_id == cluster_state.juiz_id`
3. **Promoção Temporária** (EIP-0005):
   - Próximo melhor score assume como Juiz temporário
   - Marca `juiz_failover_started = now()`
   - Anuncia `STATE_CHANGE` com `reason="juiz_failover"`
4. **Monitoramento**: Loop verifica a cada 60s se Juiz original voltou
5. **Timeout 72h**: Se `now() - juiz_failover_started > 72h` → Nova eleição completa
6. **Restauração**: Juiz original volta → Assume imediatamente, temporário encerra

### 6.5 Indexação Global do Bibliotecário

```python
async def build_global_index(bibliotecario: BeeService) -> dict:
    global_index = {}  # assunto -> list[PeerKnowledge]
    
    for peer in bibliotecario.discovery.get_active_peers():
        # KNOWLEDGE_QUERY para cada domínio conhecido
        for domain in KNOWN_DOMAINS:
            resp = await query_peer(peer, KNOWLEDGE_QUERY(subject=domain))
            if resp.has_knowledge:
                global_index.setdefault(domain, []).append(
                    PeerKnowledge(
                        peer_id=peer.node_id,
                        confidence=resp.confidence,
                        doc_count=resp.document_count,
                        topics=resp.topics
                    )
                )
    
    # Ordenar por confidence decrescente
    for domain in global_index:
        global_index[domain].sort(key=lambda x: x.confidence, reverse=True)
    
    return global_index
```

### 6.6 Roteamento de Query (Política LOCAL → ENXAME → WEB)

```python
async def route_query(query: str, cluster: ClusterState) -> Answer:
    # 1. LOCAL (sempre tenta primeiro)
    local = await query_local(query)
    if local.confidence >= THRESHOLD_ENXAME:
        return local
    
    # 2. ENXAME - Consultar Bibliotecário para saber ONDE buscar
    if cluster.bibliotecario_id:
        target_peers = await query_bibliotecario_where(query)
        for peer_id in target_peers:
            result = await query_peer(peer_id, RESEARCH_REQUEST(query))
            if result.confidence >= THRESHOLD_WEB:
                return result
    
    # 3. WEB - Apenas Juiz, Bibliotecário ou Guarda
    if cluster.is_internet_role():
        return await query_web(query)
    
    return best_available(local, enxame_results)
```

## Implementação

### Componentes Novos

1. **`bees/cluster/election.py`** - Algoritmo de eleição e failover
2. **`bees/cluster/state.py`** - Persistência de `ClusterState`
3. **`bees/cluster/global_index.py`** - Índice global do Bibliotecário
4. **`bees/cluster/internet_gate.py`** - Controle de acesso à internet por papel
5. **`bees/cluster/monitor.py`** - Monitoramento de health + failover

### Integração com BEE Existente

- `BeeService` ganha `cluster_role: ClusterRole` e `cluster_state: ClusterState`
- `start()` executa eleição se `len(peers) >= 3`
- `_heartbeat_loop` monitora failover
- `_query_enxame` usa índice global do Bibliotecário
- `allow_web` respeita `cluster_role` não apenas config local

### Persistência

```
~/.enxame/cluster_state.json  # Estado do cluster (epoch, roles, timestamps)
~/.enxame/global_index.json   # Índice global do Bibliotecário (cache)
```

## Consequências

### Positivas
- Enxame auto-organizado sem configuração manual
- Resiliente a falhas (failover automático)
- Uso eficiente de hardware (GPU → Artist, melhor HW → Juiz)
- Internet controlada e auditável
- Busca distribuída inteligente antes de ir para web

### Negativas
- Complexidade de estado distribuído
- Requer relógio sincronizado (NTP) para eleição justa
- 72h de janela de failover pode ser longa para alguns casos
- Bibliotecário vira ponto de gargalo para roteamento

### Neutras
- Compatível com BEE-0001/0002/0003 existentes
- Abelhas standalone continuam funcionando (sem cluster)
- Eleição só ocorre com 3+ peers descobertos

## Referências

- BEE-0001: Conceito de Abelha
- BEE-0002: Protocolo de Comunicação
- BEE-0003: Capabilities e Model Discovery
- EIP-0001: Architecture First
- EIP-0003: Dynamic Capability Discovery
- EIP-0005: Temporary Service Promotion

## Histórico

- **2025-09-16** - EIP criado baseado em requisitos do usuário