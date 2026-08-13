"""Componentes de cluster: benchmark, eleição e busca local distribuída."""

from .benchmark import HardwareBenchmark, HardwareProfile
from .election import (
    ClusterElection,
    ElectionResult,
    FailoverElection,
    HeartbeatManager,
    NodeBenchmark,
    PeerNode,
    calculate_hardware_score,
)
from .local_search import LocalSearchEngine, LocalSearchResult

__all__ = [
    'HardwareBenchmark',
    'HardwareProfile',
    'NodeBenchmark',
    'ElectionResult',
    'ClusterElection',
    'LocalSearchEngine',
    'LocalSearchResult',
    'calculate_hardware_score',
    'PeerNode',
    'HeartbeatManager',
    'FailoverElection',
]
