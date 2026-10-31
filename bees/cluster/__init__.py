"""Cluster management para Enxame - Eleição de papéis, failover, índice global."""

from .types import (
    ClusterState, ClusterRole, PeerKnowledge, PeerBenchmark, ElectionResult,
    JUIZ_CAPS, BIBLIOTECARIO_CAPS, GUARDA_CAPS, WORKER_BASE_CAPS, ARTIST_CAPS
)
from .state import load_cluster_state, save_cluster_state, get_cluster_state_path
from .election import elect_roles, elect_juiz_failover, restore_juiz, score_peer, has_capabilities
from .global_index import GlobalIndex, build_global_index, query_bibliotecario_where
from .internet_gate import InternetGate, InternetPurpose
from .monitor import ClusterMonitor, start_monitoring, stop_monitoring

__all__ = [
    # Types
    "ClusterState",
    "ClusterRole",
    "PeerKnowledge",
    "PeerBenchmark",
    "ElectionResult",
    "JUIZ_CAPS",
    "BIBLIOTECARIO_CAPS",
    "GUARDA_CAPS",
    "WORKER_BASE_CAPS",
    "ARTIST_CAPS",
    # State I/O
    "load_cluster_state",
    "save_cluster_state",
    "get_cluster_state_path",
    # Election
    "elect_roles",
    "elect_juiz_failover",
    "restore_juiz",
    "score_peer",
    "has_capabilities",
    # Global index
    "GlobalIndex",
    "build_global_index",
    "query_bibliotecario_where",
    # Internet gate
    "InternetGate",
    "InternetPurpose",
    # Monitoring
    "ClusterMonitor",
    "start_monitoring",
    "stop_monitoring",
]