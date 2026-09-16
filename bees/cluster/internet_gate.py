"""Controle de acesso à internet por papel no cluster."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from .state import ClusterRole, ClusterState

logger = logging.getLogger("bee.cluster.internet_gate")


class InternetPurpose(Enum):
    """Finalidades permitidas para acesso à internet."""
    JUIZ_PONDERACAO = "juiz_ponderacao"      # Juiz: ponderar respostas conflitantes
    BIBLIOTECARIO_FALLBACK = "bibliotecario_fallback"  # Bibliotecário: fallback de conhecimento
    GUARDA_APRENDIZADO = "guarda_aprendizado"  # Guarda: aprender técnicas de ataque/defesa


# Mapeamento papel -> finalidades permitidas
ROLE_PERMISSIONS: dict[ClusterRole, list[InternetPurpose]] = {
    ClusterRole.JUIZ: [InternetPurpose.JUIZ_PONDERACAO],
    ClusterRole.BIBLIOTECARIO: [InternetPurpose.BIBLIOTECARIO_FALLBACK],
    ClusterRole.GUARDA: [InternetPurpose.GUARDA_APRENDIZADO],
    # WORKER e WORKER_ARTIST: sem acesso
}


class InternetGate:
    """Controla acesso à internet baseado no papel do node."""
    
    def __init__(self, cluster_state: ClusterState, node_id: str):
        self.cluster_state = cluster_state
        self.node_id = node_id
    
    def can_access(self, purpose: InternetPurpose | None = None) -> bool:
        """
        Verifica se este node pode acessar a internet.
        
        Args:
            purpose: Finalidade específica (opcional). Se None, verifica acesso geral.
        """
        # Verificar papel primário
        primary_role = self.cluster_state.get_role(self.node_id)
        if primary_role and primary_role in ROLE_PERMISSIONS:
            if purpose is None or purpose in ROLE_PERMISSIONS[primary_role]:
                return True
        
        # Verificar papéis secundários
        for role in self.cluster_state.get_secondary_roles(self.node_id):
            if role in ROLE_PERMISSIONS:
                if purpose is None or purpose in ROLE_PERMISSIONS[role]:
                    return True
        
        return False
    
    def get_allowed_purposes(self) -> list[InternetPurpose]:
        """Retorna finalidades permitidas para este node."""
        purposes = []
        primary = self.cluster_state.get_role(self.node_id)
        if primary and primary in ROLE_PERMISSIONS:
            purposes.extend(ROLE_PERMISSIONS[primary])
        for role in self.cluster_state.get_secondary_roles(self.node_id):
            if role in ROLE_PERMISSIONS:
                purposes.extend(ROLE_PERMISSIONS[role])
        return purposes


def can_access_internet(cluster_state: ClusterState, node_id: str, purpose: InternetPurpose | None = None) -> bool:
    """Função auxiliar para verificar acesso à internet."""
    gate = InternetGate(cluster_state, node_id)
    return gate.can_access(purpose)


class InternetAccessLogger:
    """Logger de acessos à internet para auditoria."""
    
    def __init__(self, data_dir: Any):
        self.log_file = data_dir / "logs" / "internet_access.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log_access(self, node_id: str, purpose: InternetPurpose, url: str, success: bool) -> None:
        """Registra tentativa de acesso à internet."""
        import json
        import time
        
        entry = {
            "timestamp": time.time(),
            "node_id": node_id,
            "purpose": purpose.value,
            "url": url,
            "success": success,
        }
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # Falha silenciosa no log


class GuardedWebClient:
    """Wrapper do WebSearchClient que exige permissão do InternetGate."""
    
    def __init__(
        self,
        web_client: Any,
        internet_gate: InternetGate,
        access_logger: InternetAccessLogger,
        node_id: str
    ):
        self.web_client = web_client
        self.gate = internet_gate
        self.logger = access_logger
        self.node_id = node_id
    
    async def search(self, query: str, purpose: InternetPurpose) -> list[Any]:
        """Busca na web se permitido."""
        if not self.gate.can_access(purpose):
            self.logger.log_access(self.node_id, purpose, f"search:{query[:50]}", False)
            logger.warning(f"Node {self.node_id} tentou acesso à internet sem permissão: {purpose.value}")
            return []
        
        try:
            results = await self.web_client.search(query)
            self.logger.log_access(self.node_id, purpose, f"search:{query[:50]}", True)
            return results
        except Exception as e:
            self.logger.log_access(self.node_id, purpose, f"search:{query[:50]}", False)
            raise