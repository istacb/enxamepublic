#!/usr/bin/env python3
"""
AutoDiscoveryService — Descoberta Automática Avançada
=====================================================
Estende a descoberta mDNS da Abelha com:
- Detecção de capacidades remotas
- Classificação automática de peers
- Health monitoring contínuo
- Network topology mapping
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

from bees.protocol.messages import BeeState

logger = logging.getLogger("enxame.discovery")

SERVICE_TYPE = "_enxame._tcp.local."
ENXAME_SERVICE_TYPE = "_enxame-evolved._tcp.local."


@dataclass(slots=True)
class DiscoveredPeer:
    """Peer descoberto com metadados ricos."""
    node_id: str
    role: str
    host: str
    port: int
    capabilities: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    profiles: list[str] = field(default_factory=list)
    load: float = 0.0
    state: BeeState = BeeState.RUNNING
    version: str = "1.0"
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_heartbeat_seq: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    _latency_ms: float = 0.0
    _reliability_score: float = 1.0


@dataclass(slots=True)
class NetworkTopology:
    """Mapeamento da topologia de rede."""
    nodes: dict[str, DiscoveredPeer] = field(default_factory=dict)
    edges: list[tuple[str, str, float]] = field(default_factory=list)  # (from, to, latency)
    clusters: dict[str, list[str]] = field(default_factory=dict)  # cluster_id -> [node_ids]
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))


class AutoDiscoveryService:
    """
    Serviço de auto-descoberta avançada para Enxame Evoluído.
    
    Funcionalidades:
    - mDNS para descoberta local
    - Anúncio de capacidades expandidas
    - Health monitoring com latency tracking
    - Classificação automática de peers por能力
    - Network topology mapping
    - Peer capability profiling
    """

    def __init__(
        self,
        node_id: str,
        host: str,
        port: int,
        capabilities: list[str],
        models: list[str],
        profiles: list[str] | None = None,
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
        self.profiles = profiles or []
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
        self._topology = NetworkTopology()
        self._local_ip = self._get_local_ip()

    async def start(self) -> None:
        """Inicia descoberta automática."""
        self._zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        
        # Browser para ambos tipos de serviço
        self._browser = ServiceBrowser(
            self._zeroconf,
            [SERVICE_TYPE, ENXAME_SERVICE_TYPE],
            handlers=[self._on_service_state_change],
        )

        self._running = True
        self._tasks = [
            asyncio.create_task(self._announcement_loop()),
            asyncio.create_task(self._health_monitor_loop()),
            asyncio.create_task(self._topology_update_loop()),
        ]
        logger.info(f"AutoDiscovery iniciado para {self.node_id}")

    async def stop(self) -> None:
        """Para descoberta."""
        self._running = False
        for task in self._tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if self._browser:
            self._browser.cancel()
        if self._zeroconf:
            self._zeroconf.close()
        logger.info("AutoDiscovery parado")

    def _on_service_state_change(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        """Callback para mudanças de serviços mDNS."""
        if state_change is ServiceStateChange.Removed:
            self._remove_peer_by_name(name)
            return

        if state_change is ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                self._process_service_info(info, service_type)

    def _process_service_info(self, info: ServiceInfo, service_type: str) -> None:
        """Processa informações de serviço descoberto."""
        if not info.addresses:
            return

        props = {}
        for k, v in info.properties.items():
            try:
                key = k.decode("utf-8") if isinstance(k, bytes) else k
                val = v.decode("utf-8") if isinstance(v, bytes) else str(v)
                props[key] = val
            except Exception:
                continue

        node_id = props.get("node_id")
        if not node_id or node_id == self.node_id:
            return

        host = socket.inet_ntoa(info.addresses[0])
        port = info.port

        # Parse capabilities
        caps = self._parse_json_list(props.get("capabilities", "[]"))
        models = self._parse_json_list(props.get("models", "[]"))
        profiles = self._parse_json_list(props.get("profiles", "[]"))

        load = float(props.get("load", 0.0))
        state_str = props.get("state", "RUNNING")
        version = props.get("version", "1.0")
        
        try:
            state = BeeState(state_str)
        except Exception:
            state = BeeState.RUNNING

        peer = DiscoveredPeer(
            node_id=node_id,
            role=props.get("role", "enxame-node"),
            host=host,
            port=port,
            capabilities=caps,
            models=models,
            profiles=profiles,
            load=load,
            state=state,
            version=version,
            last_seen=datetime.now(UTC),
            metadata={
                "service_type": service_type,
                "raw_props": props,
            },
        )

        is_new = node_id not in self._peers
        self._peers[node_id] = peer
        self._topology.nodes[node_id] = peer

        if is_new:
            logger.info(f"Peer descoberto: {node_id} ({peer.role}) caps={len(caps)} models={len(models)} profiles={len(profiles)}")
            if self.on_peer_found:
                self.on_peer_found(peer)

    def _parse_json_list(self, value: str) -> list[str]:
        """Parse seguro de lista JSON."""
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except Exception:
            pass
        # Fallback: split por vírgula
        return [x.strip() for x in value.split(",") if x.strip()]

    def _remove_peer_by_name(self, name: str) -> None:
        """Remove peer pelo nome do serviço."""
        for node_id, peer in list(self._peers.items()):
            expected_names = [
                f"{node_id}.{SERVICE_TYPE}",
                f"{node_id}.{ENXAME_SERVICE_TYPE}",
            ]
            if name in expected_names or name.startswith(node_id):
                self._remove_peer(node_id)
                break

    def _remove_peer(self, node_id: str) -> None:
        """Remove peer e notifica."""
        if node_id in self._peers:
            del self._peers[node_id]
        if node_id in self._topology.nodes:
            del self._topology.nodes[node_id]
        # Remover edges relacionados
        self._topology.edges = [
            (f, t, l) for f, t, l in self._topology.edges
            if f != node_id and t != node_id
        ]
        logger.warning(f"Peer removido: {node_id}")
        if self.on_peer_lost:
            self.on_peer_lost(node_id)

    def get_active_peers(self) -> list[DiscoveredPeer]:
        """Retorna peers ativos (com heartbeat recente)."""
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

    def get_peers_by_capability(self, capability: str) -> list[DiscoveredPeer]:
        """Retorna peers que têm capability específica."""
        return [p for p in self.get_active_peers() if capability in p.capabilities]

    def get_peers_by_profile(self, profile: str) -> list[DiscoveredPeer]:
        """Retorna peers com perfil específico."""
        return [p for p in self.get_active_peers() if profile in p.profiles]

    def get_best_peer_for_task(self, task_type: str, required_caps: list[str]) -> DiscoveredPeer | None:
        """Seleciona melhor peer para tarefa baseado em capacidades e carga."""
        candidates = self.get_active_peers()
        if not candidates:
            return None

        # Filtrar por capacidades requeridas
        candidates = [p for p in candidates if all(c in p.capabilities for c in required_caps)]
        if not candidates:
            return None

        # Score: menor load + maior reliability + capacidades extras
        def score(peer: DiscoveredPeer) -> float:
            base = 1.0 - peer.load
            reliability = peer._reliability_score
            extra_caps = len(set(peer.capabilities) - set(required_caps))
            latency_penalty = peer._latency_ms / 1000.0
            return base * reliability + extra_caps * 0.1 - latency_penalty

        return max(candidates, key=score)

    # =========================================================================
    # Loops de Background
    # =========================================================================

    async def _announcement_loop(self) -> None:
        """Loop de anúncio mDNS periódico."""
        while self._running:
            try:
                self._announce()
            except Exception as e:
                logger.error(f"Erro no anúncio: {e}")
            await asyncio.sleep(self.heartbeat_interval)

    async def _health_monitor_loop(self) -> None:
        """Monitora saúde dos peers com latency checks."""
        while self._running:
            try:
                await self._check_peer_health()
            except Exception as e:
                logger.error(f"Erro no health monitor: {e}")
            await asyncio.sleep(10)

    async def _topology_update_loop(self) -> None:
        """Atualiza mapeamento de topologia de rede."""
        while self._running:
            try:
                await self._update_topology()
            except Exception as e:
                logger.error(f"Erro no topology update: {e}")
            await asyncio.sleep(60)

    def _announce(self) -> None:
        """Anuncia este nó via mDNS."""
        if not self._zeroconf:
            return

        # Anúncio padrão (compatibilidade)
        self._info = ServiceInfo(
            type_=SERVICE_TYPE,
            name=f"{self.node_id}.{SERVICE_TYPE}",
            addresses=[socket.inet_aton(self._local_ip)],
            port=self.port,
            properties={
                "node_id": self.node_id,
                "role": "enxame-node",
                "capabilities": json.dumps(self.capabilities),
                "models": json.dumps(self.models),
                "profiles": json.dumps(self.profiles),
                "load": str(self._calculate_load()),
                "state": "RUNNING",
                "version": "2.0",
                "protocol_version": "1.0",
            },
            server=f"{self.node_id}.local.",
        )
        self._zeroconf.register_service(self._info)

        # Anúncio evoluído
        evolved_info = ServiceInfo(
            type_=ENXAME_SERVICE_TYPE,
            name=f"{self.node_id}.{ENXAME_SERVICE_TYPE}",
            addresses=[socket.inet_aton(self._local_ip)],
            port=self.port,
            properties={
                "node_id": self.node_id,
                "role": "enxame-node",
                "capabilities": json.dumps(self.capabilities),
                "models": json.dumps(self.models),
                "profiles": json.dumps(self.profiles),
                "load": str(self._calculate_load()),
                "state": "RUNNING",
                "version": "2.0",
            },
            server=f"{self.node_id}.local.",
        )
        self._zeroconf.register_service(evolved_info)

    async def _check_peer_health(self) -> None:
        """Verifica saúde dos peers com ping/latency."""
        for peer in list(self._peers.values()):
            try:
                start = time.time()
                # Ping simples via HTTP
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"http://{peer.host}:{peer.port}/health",
                        timeout=aiohttp.ClientTimeout(total=3)
                    ) as resp:
                        if resp.status == 200:
                            peer._latency_ms = (time.time() - start) * 1000
                            peer._reliability_score = min(peer._reliability_score + 0.01, 1.0)
                            peer.last_seen = datetime.now(UTC)
                            data = await resp.json()
                            peer.load = data.get("load", peer.load)
                            peer.state = BeeState(data.get("state", "RUNNING"))
                        else:
                            peer._reliability_score = max(peer._reliability_score - 0.05, 0.0)
            except Exception:
                peer._reliability_score = max(peer._reliability_score - 0.1, 0.0)

    async def _update_topology(self) -> None:
        """Atualiza mapeamento de topologia."""
        self._topology.last_updated = datetime.now(UTC)
        
        # Detectar clusters por proximidade de capacidades
        peers = self.get_active_peers()
        clusters = {}
        for peer in peers:
            cap_key = tuple(sorted(peer.capabilities)[:3])  # Top 3 caps
            if cap_key not in clusters:
                clusters[cap_key] = []
            clusters[cap_key].append(peer.node_id)
        
        self._topology.clusters = {
            f"cluster_{i}": nodes for i, nodes in enumerate(clusters.values())
        }

    def _calculate_load(self) -> float:
        """Calcula carga atual."""
        import psutil
        cpu = psutil.cpu_percent(interval=0.1) / 100.0
        mem = psutil.virtual_memory().percent / 100.0
        return (cpu + mem) / 2.0

    def update_announcement(self, load: float, state: BeeState = BeeState.RUNNING) -> None:
        """Atualiza anúncio com nova carga/estado."""
        if self._zeroconf and self._info:
            self._info.properties = {
                "node_id": self.node_id,
                "role": "enxame-node",
                "capabilities": json.dumps(self.capabilities),
                "models": json.dumps(self.models),
                "profiles": json.dumps(self.profiles),
                "load": str(load),
                "state": state.value,
                "version": "2.0",
                "protocol_version": "1.0",
            }
            self._zeroconf.update_service(self._info)

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
                    "models": p.models,
                    "profiles": p.profiles,
                    "latency_ms": p._latency_ms,
                    "reliability": p._reliability_score,
                }
                for p in active
            ],
            "topology": {
                "clusters": self._topology.clusters,
                "edges": len(self._topology.edges),
            },
        }

    def _get_local_ip(self) -> str:
        """Obtém IP local."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"


from contextlib import suppress