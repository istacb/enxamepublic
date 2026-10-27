#!/usr/bin/env python3
"""
BeeDiscoveryService — Descoberta de Peers via mDNS
==================================================
Gerencia:
- Anúncio da própria Abelha via mDNS
- Descoberta de outras Abelhas na rede local
- Handshake e manutenção de conexões
- Heartbeat e detecção de falhas
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

from zeroconf import IPVersion, ServiceBrowser, ServiceInfo, ServiceStateChange, Zeroconf

from .protocol.messages import BeeManifesto, BeeState

logger = logging.getLogger("bee.discovery")

SERVICE_TYPE = "_enxame._tcp.local."


@dataclass(slots=True)
class DiscoveredPeer:
    """Peer descoberto na rede."""
    node_id: str
    role: str
    host: str
    port: int
    capabilities: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    load: float = 0.0
    state: BeeState = BeeState.RUNNING
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_heartbeat_seq: int = 0
    manifesto: BeeManifesto | None = None
    _sequence: int = 0


class BeeDiscoveryService:
    """
    Serviço de descoberta mDNS para Abelhas.
    
    Funciona como:
    - Anunciador (publica esta Abelha)
    - Navegador (descobre outras Abelhas)
    - Gerenciador de peers ativos
    """

    def __init__(
        self,
        node_id: str,
        host: str,
        port: int,
        capabilities: list[str],
        models: list[str],
        on_peer_found: Callable[[DiscoveredPeer], None] | None = None,
        on_peer_lost: Callable[[str], None] | None = None,
        heartbeat_interval: float = 5.0,
        heartbeat_timeout: float = 15.0,
    ) -> None:
        self.node_id = node_id
        self.host = host
        self.port = port
        self.capabilities = capabilities
        self.models = models
        self.on_peer_found = on_peer_found
        self.on_peer_lost = on_peer_lost
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout

        self._peers: dict[str, DiscoveredPeer] = {}
        self._zeroconf: Zeroconf | None = None
        self._browser: ServiceBrowser | None = None
        self._info: ServiceInfo | None = None
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Inicia descoberta mDNS."""
        self._zeroconf = Zeroconf(ip_version=IPVersion.V4Only)

        # Iniciar browser para descobrir peers
        self._browser = ServiceBrowser(
            self._zeroconf,
            SERVICE_TYPE,
            handlers=[self._on_service_state_change],
        )

        self._running = True
        self._tasks = [
            asyncio.create_task(self._cleanup_loop()),
        ]
        logger.info(f"Descoberta mDNS iniciada para {self.node_id}")

    async def stop(self) -> None:
        """Para descoberta mDNS."""
        self._running = False

        for task in self._tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        if self._browser:
            self._browser.cancel()
            self._browser = None

        if self._zeroconf:
            self._zeroconf.close()
            self._zeroconf = None

        logger.info("Descoberta mDNS parada")

    def _on_service_state_change(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        """Callback para mudanças de estado de serviços mDNS."""
        if state_change is ServiceStateChange.Removed:
            self._remove_peer_by_name(name)
            return

        if state_change is ServiceStateChange.Added:
            # Resolver serviço para obter detalhes
            info = zeroconf.get_service_info(service_type, name)
            if info:
                self._process_service_info(info)

    def _process_service_info(self, info: ServiceInfo) -> None:
        """Processa informações de um serviço descoberto."""
        if not info.addresses:
            return

        props = {}
        for k, v in info.properties.items():
            try:
                props[k.decode("utf-8")] = v.decode("utf-8") if isinstance(v, bytes) else str(v)
            except Exception:
                props[k.decode("utf-8") if isinstance(k, bytes) else k] = str(v)

        node_id = props.get("node_id")
        if not node_id or node_id == self.node_id:
            return  # Ignorar a si mesmo

        host = socket.inet_ntoa(info.addresses[0])
        port = info.port

        # Parse capabilities e models
        caps = []
        if props.get("capabilities"):
            try:
                caps = json.loads(props["capabilities"])
            except Exception:
                caps = [c.strip() for c in props["capabilities"].split(",") if c.strip()]

        models = []
        if props.get("models"):
            try:
                models = json.loads(props["models"])
            except Exception:
                models = [m.strip() for m in props["models"].split(",") if m.strip()]

        load = float(props.get("load", 0.0))
        state_str = props.get("state", "RUNNING")
        try:
            state = BeeState(state_str)
        except Exception:
            state = BeeState.RUNNING

        peer = DiscoveredPeer(
            node_id=node_id,
            role=props.get("role", "bee"),
            host=host,
            port=port,
            capabilities=caps,
            models=models,
            load=load,
            state=state,
            last_seen=datetime.now(UTC),
        )

        is_new = node_id not in self._peers
        self._peers[node_id] = peer

        if is_new:
            logger.info(f"Peer descoberto: {node_id} ({peer.role}) em {host}:{port}")
            if self.on_peer_found:
                self.on_peer_found(peer)

    def _remove_peer_by_name(self, name: str) -> None:
        """Remove peer pelo nome do serviço mDNS."""
        for node_id, peer in list(self._peers.items()):
            expected_name = f"{node_id}.{SERVICE_TYPE}"
            if name == expected_name or name.startswith(node_id):
                self._remove_peer(node_id)
                break

    def _remove_peer(self, node_id: str) -> None:
        """Remove peer e notifica callback."""
        if node_id in self._peers:
            del self._peers[node_id]
            logger.warning(f"Peer removido: {node_id}")
            if self.on_peer_lost:
                self.on_peer_lost(node_id)

    def get_active_peers(self) -> list[DiscoveredPeer]:
        """Retorna lista de peers ativos (visto recentemente)."""
        now = datetime.now(UTC)
        active = []
        for peer in self._peers.values():
            elapsed = (now - peer.last_seen).total_seconds()
            if elapsed < self.heartbeat_timeout and peer.state != BeeState.STOPPED:
                active.append(peer)
        return active

    def get_peer(self, node_id: str) -> DiscoveredPeer | None:
        """Retorna peer específico se ativo."""
        peer = self._peers.get(node_id)
        if peer:
            elapsed = (datetime.now(UTC) - peer.last_seen).total_seconds()
            if elapsed < self.heartbeat_timeout:
                return peer
        return None

    async def update_peer_manifesto(self, node_id: str, manifesto: BeeManifesto) -> None:
        """Atualiza manifesto do peer (recebido via HELLO_ACK)."""
        if node_id in self._peers:
            self._peers[node_id].manifesto = manifesto
            self._peers[node_id].capabilities = manifesto.capabilities
            self._peers[node_id].models = manifesto.models
            self._peers[node_id].load = manifesto.load

    async def update_peer_heartbeat(
        self,
        node_id: str,
        state: BeeState,
        load: float,
        sequence: int,
    ) -> None:
        """Atualiza heartbeat do peer."""
        if node_id in self._peers:
            peer = self._peers[node_id]
            peer.state = state
            peer.load = load
            peer.last_heartbeat_seq = sequence
            peer.last_seen = datetime.now(UTC)

    async def confirm_heartbeat(self, node_id: str, ack_sequence: int) -> None:
        """Confirma recebimento de heartbeat ACK."""
        if node_id in self._peers:
            self._peers[node_id].last_seen = datetime.now(UTC)

    async def cleanup_stale_peers(self) -> None:
        """Remove peers que não enviam heartbeat há muito tempo."""
        now = datetime.now(UTC)
        stale = []

        for node_id, peer in self._peers.items():
            elapsed = (now - peer.last_seen).total_seconds()
            if elapsed > self.heartbeat_timeout:
                stale.append(node_id)

        for node_id in stale:
            logger.warning(f"Peer stale removido: {node_id} (sem heartbeat por {elapsed:.0f}s)")
            self._remove_peer(node_id)

    async def _cleanup_loop(self) -> None:
        """Loop periódico de limpeza de peers stale."""
        while self._running:
            try:
                await self.cleanup_stale_peers()
            except Exception as e:
                logger.error(f"Erro no cleanup loop: {e}")
            await asyncio.sleep(30)

    # =========================================================================
    # Anúncio via mDNS
    # =========================================================================

    def start_announcement(self) -> None:
        """Inicia anúncio mDNS desta Abelha."""
        if not self._zeroconf:
            return

        self._info = ServiceInfo(
            type_=SERVICE_TYPE,
            name=f"{self.node_id}.{SERVICE_TYPE}",
            addresses=[socket.inet_aton(self._get_local_ip())],
            port=self.port,
            properties={
                "node_id": self.node_id,
                "role": "bee",
                "capabilities": json.dumps(self.capabilities),
                "models": json.dumps(self.models),
                "load": "0.0",
                "state": "RUNNING",
                "protocol_version": "1.0",
            },
            server=f"{self.node_id}.local.",
        )
        self._zeroconf.register_service(self._info)
        logger.info(f"Anúncio mDNS iniciado: {self.node_id}")

    def stop_announcement(self) -> None:
        """Para anúncio mDNS."""
        if self._zeroconf and self._info:
            self._zeroconf.unregister_service(self._info)
            self._info = None

    def update_announcement(self, load: float, state: BeeState = BeeState.RUNNING) -> None:
        """Atualiza anúncio com nova carga/estado."""
        if self._zeroconf and self._info:
            self._info.properties = {
                "node_id": self.node_id,
                "role": "bee",
                "capabilities": json.dumps(self.capabilities),
                "models": json.dumps(self.models),
                "load": str(load),
                "state": state.value,
                "protocol_version": "1.0",
            }
            self._zeroconf.update_service(self._info)

    def _get_local_ip(self) -> str:
        """Obtém IP local da máquina."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def get_stats(self) -> dict[str, Any]:
        """Estatísticas da descoberta."""
        active = self.get_active_peers()
        return {
            "total_discovered": len(self._peers),
            "active_peers": len(active),
            "peers": [
                {
                    "node_id": p.node_id,
                    "role": p.role,
                    "host": p.host,
                    "port": p.port,
                    "state": p.state.value,
                    "load": p.load,
                    "capabilities": p.capabilities,
                }
                for p in active
            ],
        }


# Import para suppress
from contextlib import suppress