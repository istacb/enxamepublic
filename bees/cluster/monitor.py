"""Monitoramento de cluster e failover automático."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

from .state import ClusterState, ClusterRole
from .election import elect_juiz_failover, restore_juiz, elect_roles

logger = logging.getLogger("bee.cluster.monitor")


class ClusterMonitor:
    """
    Monitora saúde do cluster e gerencia failover.
    
    Responsabilidades:
    - Detectar perda de Juiz via heartbeat
    - Iniciar failover temporário
    - Monitorar retorno do Juiz original (72h timeout)
    - Disparar nova eleição se necessário
    - Atualizar estado persistido
    """
    
    def __init__(
        self,
        bee_service: Any,
        cluster_state: ClusterState,
        save_state_fn: Callable[[ClusterState], None],
        check_interval: float = 60.0,  # Verificar a cada 60s
    ):
        self.bee_service = bee_service
        self.cluster_state = cluster_state
        self.save_state_fn = save_state_fn
        self.check_interval = check_interval
        self._running = False
        self._task: asyncio.Task | None = None
        self._juiz_was_down = False
    
    async def start(self) -> None:
        """Inicia monitoramento."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Cluster monitor iniciado")
    
    async def stop(self) -> None:
        """Para monitoramento."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Cluster monitor parado")
    
    async def _monitor_loop(self) -> None:
        """Loop principal de monitoramento."""
        while self._running:
            try:
                await self._check_cluster_health()
            except Exception as e:
                logger.error(f"Erro no monitoramento do cluster: {e}")
            await asyncio.sleep(self.check_interval)
    
    async def _check_cluster_health(self) -> None:
        """Verifica saúde do cluster e gerencia failover."""
        # 1. Verificar se Juiz está ativo
        juiz_id = self.cluster_state.juiz_id
        if not juiz_id:
            return  # Sem Juiz eleito
        
        # Verificar se Juiz está nos peers ativos
        juiz_peer = None
        if self.bee_service._discovery:
            for peer in self.bee_service._discovery.get_active_peers():
                if peer.node_id == juiz_id:
                    juiz_peer = peer
                    break
        
        juiz_online = juiz_peer is not None
        
        # 2. Se Juiz caiu e não estávamos em failover
        if not juiz_online and not self.cluster_state.is_juiz_failover_active():
            logger.warning(f"Juiz {juiz_id} está offline! Iniciando failover...")
            await self._handle_juiz_failure(juiz_id)
        
        # 3. Se estávamos em failover e Juiz voltou
        elif juiz_online and self.cluster_state.is_juiz_failover_active():
            logger.info(f"Juiz original {juiz_id} retornou! Restaurando...")
            await self._handle_juiz_restored(juiz_id)
        
        # 4. Verificar timeout de 72h para nova eleição
        elif self.cluster_state.should_trigger_new_election():
            logger.warning("Failover de Juiz excedeu 72h! Disparando nova eleição...")
            await self._trigger_new_election()
        
        # 5. Verificar re-eleição periódica se configuração mudou (peers entraram/sairam)
        await self._check_re_election_needed()
    
    async def _handle_juiz_failure(self, failed_juiz_id: str) -> None:
        """Lida com falha do Juiz - elege temporário."""
        peers = []
        if self.bee_service._discovery:
            peers = self.bee_service._discovery.get_active_peers()
        
        if not peers:
            logger.error("Sem peers disponíveis para failover!")
            return
        
        # Eleger novo Juiz temporário
        new_state = elect_juiz_failover(peers, failed_juiz_id, self.cluster_state)
        self.cluster_state = new_state
        self.save_state_fn(new_state)
        
        # Anunciar mudança de estado via protocolo
        if self.bee_service._handler:
            from ..protocol.messages import BeeStateChange, BeeState
            state_change = self.bee_service._handler.create_state_change(
                new_state=BeeState.RUNNING,
                reason="juiz_failover",
                estimated_return_seconds=None,
            )
            # Broadcast para todos os peers
            for peer in peers:
                state_change.target_node_id = peer.node_id
                await self.bee_service._send_to_peer(peer, state_change)
        
        logger.info(f"Failover ativado: {new_state.juiz_id} assumiu como Juiz temporário")
    
    async def _handle_juiz_restored(self, original_juiz_id: str) -> None:
        """Restaura Juiz original após retorno."""
        new_state = restore_juiz(self.cluster_state, original_juiz_id)
        self.cluster_state = new_state
        self.save_state_fn(new_state)
        
        # Anunciar restauração
        if self.bee_service._handler and self.bee_service._discovery:
            from ..protocol.messages import BeeStateChange, BeeState
            peers = self.bee_service._discovery.get_active_peers()
            state_change = self.bee_service._handler.create_state_change(
                new_state=BeeState.RUNNING,
                reason="juiz_restored",
                estimated_return_seconds=None,
            )
            for peer in peers:
                state_change.target_node_id = peer.node_id
                await self.bee_service._send_to_peer(peer, state_change)
        
        logger.info(f"Juiz original {original_juiz_id} restaurado")
    
    async def _trigger_new_election(self) -> None:
        """Dispara nova eleição completa após 72h de failover."""
        peers = []
        if self.bee_service._discovery:
            peers = self.bee_service._discovery.get_active_peers()
        
        if len(peers) < 3:
            logger.warning("Menos de 3 peers para nova eleição, mantendo failover")
            return
        
        # Nova eleição completa
        new_state = elect_roles(peers, self.cluster_state)
        self.cluster_state = new_state
        self.save_state_fn(new_state)
        
        # Anunciar nova eleição
        if self.bee_service._handler and self.bee_service._discovery:
            from ..protocol.messages import BeeStateChange, BeeState
            state_change = self.bee_service._handler.create_state_change(
                new_state=BeeState.RUNNING,
                reason="new_election",
                estimated_return_seconds=None,
            )
            for peer in peers:
                state_change.target_node_id = peer.node_id
                await self.bee_service._send_to_peer(peer, state_change)
        
        logger.info(f"Nova eleição completa: Juiz={new_state.juiz_id}, Bib={new_state.bibliotecario_id}, Guarda={new_state.guarda_id}")
    
    async def _check_re_election_needed(self) -> None:
        """Verifica se re-eleição é necessária (peers entraram/sairam significativamente)."""
        # Comparar peers atuais com manifesto_version
        current_peers = set()
        if self.bee_service._discovery:
            current_peers = {p.node_id for p in self.bee_service._discovery.get_active_peers()}
        
        known_peers = set(self.cluster_state.manifesto_version.keys())
        
        # Se diferença > 30% ou novos peers com GPU entraram, re-eleger
        if known_peers:
            diff = len(current_peers.symmetric_difference(known_peers))
            if diff / max(len(known_peers), 1) > 0.3:
                logger.info("Mudança significativa na composição do cluster, re-elegendo...")
                await self._trigger_new_election()
                return
        
        # Atualizar manifesto_version
        if self.bee_service._discovery:
            for peer in self.bee_service._discovery.get_active_peers():
                self.cluster_state.manifesto_version[peer.node_id] = int(time.time())


async def start_monitoring(
    bee_service: Any,
    cluster_state: ClusterState,
    save_state_fn: Callable[[ClusterState], None],
    check_interval: float = 60.0,
) -> ClusterMonitor:
    """Inicia monitoramento do cluster."""
    monitor = ClusterMonitor(bee_service, cluster_state, save_state_fn, check_interval)
    await monitor.start()
    return monitor


async def stop_monitoring(monitor: ClusterMonitor | None) -> None:
    """Para monitoramento do cluster."""
    if monitor:
        await monitor.stop()