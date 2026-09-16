"""Índice global distribuído mantido pelo Bibliotecário."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from .state import PeerKnowledge, ClusterState

logger = logging.getLogger("bee.cluster.global_index")

# Domínios conhecidos para indexação
KNOWN_DOMAINS = [
    "direito tributário",
    "direito civil",
    "direito penal",
    "direito trabalhista",
    "direito administrativo",
    "direito constitucional",
    "direito empresarial",
    "direito do consumidor",
    "direito previdenciário",
    "direito ambiental",
    "programação",
    "python",
    "javascript",
    "machine learning",
    "inteligência artificial",
    "banco de dados",
    "arquitetura de software",
    "devops",
    "segurança da informação",
    "redes de computadores",
    "sistemas operacionais",
    "matemática",
    "física",
    "química",
    "biologia",
    "medicina",
    "engenharia",
    "finanças",
    "economia",
    "contabilidade",
    "gestão de projetos",
    "marketing",
    "vendas",
    "recursos humanos",
]


@dataclass(slots=True)
class GlobalIndex:
    """Índice global: assunto -> lista de PeerKnowledge ordenada por confidence."""
    data: dict[str, list[PeerKnowledge]] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)
    peer_manifestos: dict[str, dict] = field(default_factory=dict)  # node_id -> manifesto
    
    def get_peers_for_subject(self, subject: str, min_confidence: float = 0.5) -> list[PeerKnowledge]:
        """Retorna peers que têm conhecimento sobre assunto, ordenados por confidence."""
        # Busca exata
        if subject in self.data:
            return [pk for pk in self.data[subject] if pk.confidence >= min_confidence]
        
        # Busca parcial (substring)
        results = []
        subject_lower = subject.lower()
        for domain, peers in self.data.items():
            if subject_lower in domain.lower() or domain.lower() in subject_lower:
                for pk in peers:
                    if pk.confidence >= min_confidence:
                        results.append(pk)
        
        # Ordenar por confidence desc
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results
    
    def add_knowledge(self, subject: str, knowledge: PeerKnowledge) -> None:
        """Adiciona conhecimento ao índice."""
        if subject not in self.data:
            self.data[subject] = []
        
        # Evitar duplicatas do mesmo peer
        existing = next((i for i, pk in enumerate(self.data[subject]) if pk.peer_id == knowledge.peer_id), None)
        if existing is not None:
            # Atualizar se confidence maior
            if knowledge.confidence > self.data[subject][existing].confidence:
                self.data[subject][existing] = knowledge
        else:
            self.data[subject].append(knowledge)
        
        # Manter ordenado
        self.data[subject].sort(key=lambda x: x.confidence, reverse=True)
        self.last_updated = time.time()
    
    def update_peer_manifesto(self, node_id: str, manifesto: dict) -> None:
        """Atualiza manifesto do peer."""
        self.peer_manifestos[node_id] = manifesto
        self.last_updated = time.time()
    
    def get_stats(self) -> dict:
        """Estatísticas do índice."""
        total_entries = sum(len(v) for v in self.data.values())
        unique_peers = set()
        for peers in self.data.values():
            for pk in peers:
                unique_peers.add(pk.peer_id)
        return {
            "domains_indexed": len(self.data),
            "total_entries": total_entries,
            "unique_peers": len(unique_peers),
            "last_updated": self.last_updated,
        }


async def query_peer_knowledge(
    peer: Any,
    subject: str,
    timeout_ms: int = 2000
) -> tuple[str, PeerKnowledge | None]:
    """
    Consulta um peer via KNOWLEDGE_QUERY.
    Retorna (peer_id, PeerKnowledge) ou (peer_id, None).
    """
    try:
        from ..protocol.handler import BeeProtocolHandler
        from ..protocol.messages import BeeKnowledgeQuery, BeeMessageType
        from ..protocol.envelope import BeeEnvelope
        
        # Criar handler temporário para enviar query
        handler = BeeProtocolHandler(node_id="global_index_query", shared_secret=None)
        
        envelope = handler.create_knowledge_query(
            target_node_id=peer.node_id,
            subject=subject,
            timeout_ms=timeout_ms,
        )
        
        # Enviar via HTTP
        import aiohttp
        url = f"http://{peer.host}:{peer.port}/api/v1/bee/message"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, 
                json=envelope.to_dict(), 
                timeout=aiohttp.ClientTimeout(total=timeout_ms / 1000)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = BeeEnvelope.from_dict(data)
                    if response.msg_type == BeeMessageType.KNOWLEDGE_RESPONSE:
                        kq_resp = BeeKnowledgeQuery.from_dict(response.payload)  # type: ignore
                        knowledge = PeerKnowledge(
                            peer_id=peer.node_id,
                            confidence=kq_resp.confidence,
                            document_count=kq_resp.document_count,
                            topics=kq_resp.topics,
                        )
                        return peer.node_id, knowledge
    except Exception as e:
        logger.debug(f"Erro consultando peer {peer.node_id} sobre '{subject}': {e}")
    
    return peer.node_id, None


async def build_global_index(
    bibliotecario_peer: Any,
    peers: list[Any],
    domains: list[str] | None = None,
    concurrency: int = 5
) -> GlobalIndex:
    """
    Constrói índice global consultando todos os peers.
    
    Args:
        bibliotecario_peer: Peer do Bibliotecário (para fazer as queries)
        peers: Lista de peers ativos
        domains: Domínios a consultar (padrão: KNOWN_DOMAINS)
        concurrency: Número de queries paralelas
    
    Returns:
        GlobalIndex populado
    """
    domains = domains or KNOWN_DOMAINS
    index = GlobalIndex()
    
    # Semaphore para limitar concorrência
    semaphore = asyncio.Semaphore(concurrency)
    
    async def query_domain_peer(domain: str, peer: Any):
        async with semaphore:
            peer_id, knowledge = await query_peer_knowledge(peer, domain)
            if knowledge and knowledge.confidence > 0:
                index.add_knowledge(domain, knowledge)
    
    # Executar todas as queries
    tasks = []
    for domain in domains:
        for peer in peers:
            if peer.node_id == bibliotecario_peer.node_id:
                continue  # Não consultar a si mesmo
            tasks.append(query_domain_peer(domain, peer))
    
    # Executar em lotes para não sobrecarregar
    for i in range(0, len(tasks), concurrency * 2):
        batch = tasks[i:i + concurrency * 2]
        await asyncio.gather(*batch, return_exceptions=True)
    
    logger.info(f"Índice global construído: {index.get_stats()}")
    return index


async def query_bibliotecario_where(
    bibliotecario_peer: Any,
    subject: str,
    global_index: GlobalIndex | None = None,
    min_confidence: float = 0.5
) -> list[str]:
    """
    Consulta o Bibliotecário para saber ONDE buscar um assunto.
    
    Se global_index fornecido, usa ele (cache).
    Senão, faz KNOWLEDGE_QUERY direto no Bibliotecário.
    """
    if global_index:
        peers = global_index.get_peers_for_subject(subject, min_confidence)
        return [pk.peer_id for pk in peers]
    
    # Fallback: consultar Bibliotecário diretamente
    try:
        from ..protocol.handler import BeeProtocolHandler
        from ..protocol.messages import BeeMessageType
        from ..protocol.envelope import BeeEnvelope
        
        handler = BeeProtocolHandler(node_id="query_where", shared_secret=None)
        envelope = handler.create_knowledge_query(
            target_node_id=bibliotecario_peer.node_id,
            subject=subject,
            timeout_ms=3000,
        )
        
        import aiohttp
        url = f"http://{bibliotecario_peer.host}:{bibliotecario_peer.port}/api/v1/bee/message"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, 
                json=envelope.to_dict(), 
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = BeeEnvelope.from_dict(data)
                    if response.msg_type == BeeMessageType.KNOWLEDGE_RESPONSE:
                        # Bibliotecário retorna lista de peers com o conhecimento
                        # Assumindo formato estendido no payload
                        payload = response.payload
                        if "target_peers" in payload:
                            return payload["target_peers"]
    except Exception as e:
        logger.debug(f"Erro consultando Bibliotecário: {e}")
    
    return []


async def refresh_global_index_periodic(
    bibliotecario_service: Any,
    interval_seconds: int = 3600  # 1 hora
) -> None:
    """Task periódica para atualizar índice global."""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            if not getattr(bibliotecario_service, "_running", False):
                break
            
            peers = bibliotecario_service._discovery.get_active_peers() if bibliotecario_service._discovery else []
            if len(peers) >= 2:  # Pelo menos 1 outro peer
                index = await build_global_index(bibliotecario_service, peers)
                # Salvar no estado do cluster
                if hasattr(bibliotecario_service, "cluster_state"):
                    bibliotecario_service.cluster_state.global_index = index.data
                    from .state import save_cluster_state
                    save_cluster_state(bibliotecario_service.config.data_dir, bibliotecario_service.cluster_state)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Erro atualizando índice global: {e}")