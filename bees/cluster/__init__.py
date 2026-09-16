"""Cluster management para Enxame - Eleição de papéis, failover, índice global."""

from .state import ClusterState, ClusterRole, PeerKnowledge, load_cluster_state, save_cluster_state
from .election import elect_roles, score_peer, JUIZ_CAPS, BIBLIOTECARIO_CAPS, GUARDA_CAPS
from .global_index import GlobalIndex, build_global_index, query_bibliotecario_where
from .internet_gate import InternetGate, can_access_internet
from .monitor import ClusterMonitor, start_monitoring, stop_monitoring

__all__ = [
    "ClusterState",
    "ClusterRole",
    "PeerKnowledge",
    "load_cluster_state",
    "save_cluster_state",
    "elect_roles",
    "score_peer",
    "JUIZ_CAPS",
    "BIBLIOTECARIO_CAPS",
    "GUARDA_CAPS",
    "GlobalIndex",
    "build_global_index",
    "query_bibliotecario_where",
    "InternetGate",
    "can_access_internet",
    "ClusterMonitor",
    "start_monitoring",
    "stop_monitoring",
]