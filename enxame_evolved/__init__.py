"""
ENXAME Evolved — Arquitetura Evoluída do Enxame
================================================
Evolução natural da Abelha (/bees) para sistema multi-agente autônomo
com auto-descoberta, perfis dinâmicos, multimodal e orquestração por EIPs.
"""

__version__ = "2.0.0"

from .kernel import EnxameKernel
from .discovery import AutoDiscoveryService
from .profiles import AgentProfileManager
from .multimodal import MultimodalProcessor
from .orchestrator import TaskOrchestrator
from .sprint import SprintPlanner

__all__ = [
    "EnxameKernel",
    "AutoDiscoveryService",
    "AgentProfileManager",
    "MultimodalProcessor",
    "TaskOrchestrator",
    "SprintPlanner",
]