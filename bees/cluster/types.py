"""Tipos compartilhados do cluster Enxame - evita imports circulares."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any


class ClusterRole(Enum):
    """Papéis no cluster Enxame."""
    JUIZ = "juiz"
    BIBLIOTECARIO = "bibliotecario"
    GUARDA = "guarda"
    WORKER = "worker"
    WORKER_ARTIST = "worker_artist"


# Capabilities requeridas para cada papel primário
JUIZ_CAPS = frozenset([
    "llm_inference",    # Para ponderação e decisão
    "rag",              # Para consultar conhecimento local
    "memory",           # Para contexto histórico
    "query",            # Processamento de queries
    "vector_search",    # Busca semântica
])

BIBLIOTECARIO_CAPS = frozenset([
    "rag",
    "vector_search",
    "embeddings",
    "index",
    "query",
    "memory",
])

GUARDA_CAPS = frozenset([
    "security",
    "audit",
    "memory",
    "query",
])

WORKER_BASE_CAPS = frozenset([
    "llm_inference",
    "rag",
    "memory",
    "query",
])

ARTIST_CAPS = frozenset([
    "llm_inference",
    "rag",
    "memory",
    "query",
    "vision",
    "image_gen",
])


@dataclass(slots=True)
class PeerBenchmark:
    """Benchmark de um peer para eleição."""
    node_id: str
    score: float
    ip: str = ""
    port: int = 0
    last_seen: float = 0.0


@dataclass(slots=True)
class PeerKnowledge:
    """Conhecimento de um peer sobre um assunto."""
    peer_id: str
    confidence: float
    document_count: int
    topics: list[str] = field(default_factory=list)
    last_updated: float = field(default_factory=time.time)


@dataclass(slots=True)
class ClusterState:
    """Estado global do cluster Enxame."""
    
    epoch: int = 0                          # Incrementa a cada eleição
    juiz_id: str | None = None
    bibliotecario_id: str | None = None
    guarda_id: str | None = None
    workers: list[str] = field(default_factory=list)
    artist_workers: list[str] = field(default_factory=list)
    secondary_roles: dict[str, list[ClusterRole]] = field(default_factory=dict)  # node_id -> [roles secundários]
    juiz_failover_started: float | None = None    # Timestamp do início do failover
    last_election: float = field(default_factory=time.time)
    manifesto_version: dict[str, int] = field(default_factory=dict)  # node_id -> versão
    
    # Índice global (cache do Bibliotecário)
    global_index: dict[str, list[PeerKnowledge]] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Serializa para dicionário."""
        data = asdict(self)
        # Converter enums para strings
        data["secondary_roles"] = {
            k: [r.value for r in v] for k, v in self.secondary_roles.items()
        }
        return data
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClusterState:
        """Deserializa de dicionário."""
        # Converter secondary_roles de volta para enums
        secondary = {}
        for k, v in data.get("secondary_roles", {}).items():
            secondary[k] = [ClusterRole(r) for r in v]
        data["secondary_roles"] = secondary
        return cls(**data)
    
    def has_juiz(self) -> bool:
        return self.juiz_id is not None
    
    def has_bibliotecario(self) -> bool:
        return self.bibliotecario_id is not None
    
    def has_guarda(self) -> bool:
        return self.guarda_id is not None
    
    def is_juiz_failover_active(self) -> bool:
        """Verifica se failover de Juiz está ativo."""
        if self.juiz_failover_started is None:
            return False
        return (time.time() - self.juiz_failover_started) < (72 * 3600)  # 72h
    
    def get_juiz_failover_elapsed_hours(self) -> float:
        """Horas decorridas desde início do failover."""
        if self.juiz_failover_started is None:
            return 0.0
        return (time.time() - self.juiz_failover_started) / 3600
    
    def should_trigger_new_election(self) -> bool:
        """Verifica se deve disparar nova eleição (failover > 72h)."""
        return self.is_juiz_failover_active() and self.get_juiz_failover_elapsed_hours() >= 72
    
    def get_role(self, node_id: str) -> ClusterRole | None:
        """Retorna papel primário de um node."""
        if node_id == self.juiz_id:
            return ClusterRole.JUIZ
        if node_id == self.bibliotecario_id:
            return ClusterRole.BIBLIOTECARIO
        if node_id == self.guarda_id:
            return ClusterRole.GUARDA
        if node_id in self.workers:
            return ClusterRole.WORKER
        return None
    
    def get_secondary_roles(self, node_id: str) -> list[ClusterRole]:
        """Retorna papéis secundários de um node."""
        return self.secondary_roles.get(node_id, [])
    
    def is_internet_role(self, node_id: str) -> bool:
        """Verifica se node tem papel com acesso à internet."""
        primary = self.get_role(node_id)
        if primary in (ClusterRole.JUIZ, ClusterRole.BIBLIOTECARIO, ClusterRole.GUARDA):
            return True
        # Papéis secundários também contam
        for role in self.get_secondary_roles(node_id):
            if role in (ClusterRole.JUIZ, ClusterRole.BIBLIOTECARIO, ClusterRole.GUARDA):
                return True
        return False


@dataclass(slots=True)
class ElectionResult:
    """Resultado da eleição."""
    quorum: bool
    juiz_node_id: str | None
    bibliotecaria_node_id: str | None
    agent_node_ids: list[str]
    ranking: list[PeerBenchmark]