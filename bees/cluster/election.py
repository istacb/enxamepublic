"""Algoritmo de eleição de papéis do cluster Enxame."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .state import ClusterRole, ClusterState

# ClusterRole agora vive em .state (módulo base do pacote) para quebrar o
# ciclo de importação state <-> election. É re-exportado aqui para manter
# compatibilidade com `from bees.cluster.election import ClusterRole`.
__all__ = [
    "ClusterRole",
    "ClusterState",
    "PeerScore",
    "JUIZ_CAPS",
    "BIBLIOTECARIO_CAPS",
    "GUARDA_CAPS",
    "has_capabilities",
    "score_peer",
    "elect_roles",
    "elect_juiz_failover",
    "restore_juiz",
]


# Capabilities requeridas para cada papel primário
JUIZ_CAPS = frozenset([
    "llm_inference",    # Para ponderação e decisão
    "rag",              # Para consultar conhecimento local
    "memory",           # Para contexto histórico
    "query",            # Processamento de queries
    "vector_search",    # Busca semântica
])

BIBLIOTECARIO_CAPS = frozenset([
    "rag",              # RAG local
    "embeddings",       # Geração de embeddings
    "vector_search",    # Busca vetorial
    "index",            # Indexação de documentos
    "ocr",              # OCR para documentos
    "zim",              # Leitura ZIM offline
])

GUARDA_CAPS = frozenset([
    "security",         # Auditoria de segurança
    "audit",            # Auditoria de ações
    "monitoring",       # Monitoramento de anomalias
])


@dataclass(slots=True)
class PeerScore:
    """Score de um peer para eleição."""
    peer: Any  # DiscoveredPeer
    score: float
    primary_role: ClusterRole | None = None
    is_artist: bool = False


def has_capabilities(peer: Any, required: frozenset[str]) -> bool:
    """Verifica se peer tem todas as capabilities requeridas."""
    peer_caps = set(getattr(peer, "capabilities", []))
    return required.issubset(peer_caps)


def score_peer(peer: Any) -> float:
    """
    Calcula score de adequação de um peer para papéis de liderança.

    IMPORTANTE — este score precisa ser DETERMINÍSTICO: cada abelha roda a
    eleição sozinha, a partir da sua própria visão da rede, e todas precisam
    chegar ao MESMO resultado. Se o score depender de algo volátil, cada abelha
    elege um juiz diferente (split-brain) e o enxame fica com três orquestradores
    que não se reconhecem — foi exatamente o que aconteceu na prática.

    Por isso `load` e `uptime` FORAM REMOVIDOS daqui:
      - `load` é a carga que o peer anunciou via mDNS num instante qualquer;
        duas abelhas leem valores diferentes e pesava 20 pontos.
      - `uptime_seconds` nem existe em DiscoveredPeer (dava 0 sempre).

    Ficam só atributos estáveis, anunciados pelo próprio dono e iguais para
    todos os observadores: hardware e capabilities. O desempate é por node_id
    (ver `_sort_scored`), que também é estável.

    Critérios:
    - Hardware: RAM, CPU, GPU
    - Capabilities: quantidade e relevância para os papéis
    """
    score = 0.0
    
    # Hardware (40%)
    hw = getattr(peer, "hardware", None)
    if hw:
        score += getattr(hw, "ram_total_gb", 0) * 0.5
        score += getattr(hw, "cpu_cores", 0) * 2
        if getattr(hw, "gpu_available", False):
            score += getattr(hw, "gpu_vram_gb", 0) * 3
    
    # Capabilities (30%)
    caps = getattr(peer, "capabilities", [])
    score += len(caps) * 5
    
    # Bonus por capabilities críticas
    critical_caps = {"llm_inference", "rag", "embeddings", "vector_search", "index", "ocr", "security"}
    score += len(set(caps) & critical_caps) * 10
    
    return score


def _sort_scored(scored: list) -> list:
    """Ordena (score, peer) por score DESC e node_id ASC como desempate.

    `list.sort` é estável, então empatados ficavam na ordem em que o mDNS
    descobriu os peers — ordem que difere de abelha para abelha. Desempatar por
    node_id torna a eleição reprodutível em todos os nodes.
    """
    return sorted(scored, key=lambda x: (-x[0], x[1].node_id))


def elect_roles(peers: list[Any], current_state: ClusterState | None = None) -> ClusterState:
    """
    Elei papéis do cluster baseado nos peers descobertos.
    
    Args:
        peers: Lista de DiscoveredPeer ativos
        current_state: Estado atual (para preservar epoch em re-eleição)
    
    Returns:
        Novo ClusterState com papéis eleitos
    """
    if len(peers) < 3:
        # Menos de 3 peers: não forma cluster, todos standalone
        return ClusterState(
            epoch=(current_state.epoch if current_state else 0),
            workers=[p.node_id for p in peers],
        )
    
    # 1. Calcular scores
    scored = _sort_scored([(score_peer(p), p) for p in peers])
    
    # 2. Identificar artists (GPU)
    artist_peers = [p for s, p in scored if getattr(getattr(p, "hardware", None), "gpu_available", False)]
    artist_ids = [p.node_id for p in artist_peers]
    
    # 3. Atribuir papéis primários
    juiz = None
    bibliotecario = None
    guarda = None
    used = set()
    
    # Juiz: melhor score com capabilities completas
    for s, p in scored:
        if p.node_id not in used and has_capabilities(p, JUIZ_CAPS):
            juiz = p.node_id
            used.add(p.node_id)
            break
    
    # Bibliotecário: próximo melhor com capabilities
    for s, p in scored:
        if p.node_id not in used and has_capabilities(p, BIBLIOTECARIO_CAPS):
            bibliotecario = p.node_id
            used.add(p.node_id)
            break
    
    # Guarda: próximo melhor com capabilities
    for s, p in scored:
        if p.node_id not in used and has_capabilities(p, GUARDA_CAPS):
            guarda = p.node_id
            used.add(p.node_id)
            break
    
    # 4. Workers = restantes
    workers = [p.node_id for s, p in scored if p.node_id not in used]
    
    # 5. Consolidação de papéis (menos máquinas = mais funções secundárias)
    secondary_roles = {}
    all_peers = {p.node_id for s, p in scored}
    
    if len(peers) == 3:
        # 3 máquinas: todos são workers secundários
        for pid in all_peers:
            secondary_roles[pid] = [ClusterRole.WORKER]
    elif len(peers) == 4:
        # 4 máquinas: workers primários + papéis têm worker secundário
        for pid in all_peers:
            if pid in workers:
                continue  # Já é worker primário
            secondary_roles[pid] = [ClusterRole.WORKER]
    
    # 6. Se algum papel não foi preenchido, tentar preencher com melhor disponível
    if juiz is None and scored:
        # `scored` guarda tuplas (score, peer) — ver _sort_scored.
        juiz = scored[0][1].node_id
    if bibliotecario is None:
        for s, p in scored:
            if p.node_id != juiz:
                bibliotecario = p.node_id
                break
    if guarda is None:
        for s, p in scored:
            if p.node_id not in {juiz, bibliotecario}:
                guarda = p.node_id
                break
    
    # 7. Construir estado
    epoch = (current_state.epoch + 1) if current_state else 1
    
    return ClusterState(
        epoch=epoch,
        juiz_id=juiz,
        bibliotecario_id=bibliotecario,
        guarda_id=guarda,
        workers=workers,
        artist_workers=artist_ids,
        secondary_roles=secondary_roles,
        last_election=__import__("time").time(),
    )


def elect_juiz_failover(peers: list[Any], failed_juiz_id: str, current_state: ClusterState) -> ClusterState:
    """
    Elege novo Juiz temporário após falha do Juiz atual.
    
    Critério: próximo melhor score (excluindo o falho) com capabilities de Juiz.
    """
    # Filtrar peer falho
    available = [p for p in peers if p.node_id != failed_juiz_id]
    
    if not available:
        return current_state  # Sem peers para assumir
    
    # Encontrar próximo melhor com capabilities de Juiz
    scored = _sort_scored([(score_peer(p), p) for p in available])
    
    new_juiz = None
    for s, p in scored:
        if has_capabilities(p, JUIZ_CAPS):
            new_juiz = p.node_id
            break
    
    if new_juiz is None:
        # Fallback: melhor disponível.
        # `scored` guarda tuplas (score, peer) — `scored[0].peer` levantava
        # AttributeError justamente no caminho de emergência do failover,
        # que é quando nenhuma das opções tem as capabilities de juiz.
        new_juiz = scored[0][1].node_id
    
    # Criar novo estado com failover
    new_state = ClusterState(
        epoch=current_state.epoch,
        juiz_id=new_juiz,
        bibliotecario_id=current_state.bibliotecario_id,
        guarda_id=current_state.guarda_id,
        workers=current_state.workers,
        artist_workers=current_state.artist_workers,
        secondary_roles=current_state.secondary_roles,
        juiz_failover_started=__import__("time").time(),
        last_election=current_state.last_election,
        manifesto_version=current_state.manifesto_version,
        global_index=current_state.global_index,
    )
    
    # Marcar Juiz original como worker secundário se não for
    if failed_juiz_id not in new_state.secondary_roles:
        new_state.secondary_roles[failed_juiz_id] = []
    if ClusterRole.WORKER not in new_state.secondary_roles[failed_juiz_id]:
        new_state.secondary_roles[failed_juiz_id].append(ClusterRole.WORKER)
    
    return new_state


def restore_juiz(current_state: ClusterState, original_juiz_id: str) -> ClusterState:
    """Restaura Juiz original após retorno."""
    if current_state.juiz_id == original_juiz_id:
        return current_state  # Já é o Juiz
    
    return ClusterState(
        epoch=current_state.epoch,
        juiz_id=original_juiz_id,
        bibliotecario_id=current_state.bibliotecario_id,
        guarda_id=current_state.guarda_id,
        workers=current_state.workers,
        artist_workers=current_state.artist_workers,
        secondary_roles=current_state.secondary_roles,
        juiz_failover_started=None,  # Limpa failover
        last_election=current_state.last_election,
        manifesto_version=current_state.manifesto_version,
        global_index=current_state.global_index,
    )