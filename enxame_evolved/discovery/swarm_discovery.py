"""
SwarmDiscovery — Descoberta de Peers via mDNS/Zeroconf
======================================================
Implementa descoberta automática de agentes no enxame:
- Anúncio via mDNS (_enxame._tcp.local.)
- Browser para descoberta de peers
- Handshake de capacidades
- Heartbeat e detecção de falhas
- Sincronização de manifestos
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
import uuid
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

from zeroconf import IPVersion, ServiceBrowser, ServiceInfo, ServiceStateChange, Zeroconf

from enxame_evolved.agents.evolved_agent import AgentCapability

logger = logging.getLogger("enxame.discovery")

SERVICE_TYPE = "_enxame._tcp.local."


@dataclass(slots=True)
class DiscoveredPeer:
    """Peer descoberto no enxame."""
    node_id: str
    name: str
    host: str
    port: int
    capabilities: list[str] = field(default_factory=list)
    specialties: list[str] = field(default_factory=list)
    model: str = ""
    profile: dict[str, Any] | None = None
    benchmark: dict[str, Any] = field(default_factory=dict)
    load: float = 0.0
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_heartbeat: datetime | None = None
    status: str = "unknown"  # unknown, connected, disconnected
    metadata: dict[str, Any] = field(default_factory=dict)


class SwarmDiscovery:
    """
    Serviço de descoberta de enxame via mDNS.
    
    Funcionalidades:
    - Anúncio da própria identidade e capacidades
    - Descoberta contínua de peers
    - Handshake de perfis (troca de manifestos)
    - Heartbeat para detecção de falhas
    - Callback para notificação de peers encontrados/perdidos
    """
    
    def __init__(
        self,
        agent_id: str,
        host: str,
        port: int,
        capabilities: list[str] | None = None,
        specialties: list[str] | None = None,
        model: str = "",
        name: str = "",
        benchmark: dict[str, Any] | None = None,
        on_peer_found: Callable[[DiscoveredPeer], None] | None = None,
        on_peer_lost: Callable[[str], None] | None = None,
        on_peer_updated: Callable[[DiscoveredPeer], None] | None = None,
        heartbeat_interval: float = 5.0,
        heartbeat_timeout: float = 15.0,
        announce_interval: float = 30.0,
    ) -> None:
        self.agent_id = agent_id
        self.name = name or f"Agent-{agent_id[:8]}"
        self.host = host
        self.port = port
        self.capabilities = capabilities or []
        self.specialties = specialties or []
        self.model = model
        self.benchmark = benchmark or {}
        
        self.on_peer_found = on_peer_found
        self.on_peer_lost = on_peer_lost
        self.on_peer_updated = on_peer_updated
        
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.announce_interval = announce_interval
        
        self._peers: dict[str, DiscoveredPeer] = {}
        self._zeroconf: Zeroconf | None = None
        self._browser: ServiceBrowser | None = None
        self._info: ServiceInfo | None = None
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._local_ip = self._get_local_ip()
        
        # Sequence para heartbeats
        self._heartbeat_sequence = 0
    
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
    
    async def start(self) -> None:
        """Inicia descoberta mDNS."""
        logger.info(f"Iniciando SwarmDiscovery para {self.agent_id}")
        
        self._zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        
        # Iniciar browser
        self._browser = ServiceBrowser(
            self._zeroconf,
            SERVICE_TYPE,
            handlers=[self._on_service_state_change],
        )
        
        # Anunciar presença
        self._start_announcement()
        
        self._running = True
        
        # Tasks de background
        self._tasks = [
            asyncio.create_task(self._announcement_loop()),
            asyncio.create_task(self._cleanup_loop()),
            asyncio.create_task(self._heartbeat_loop()),
        ]
        
        logger.info(f"SwarmDiscovery ativo - Anunciando em {self._local_ip}:{self.port}")
    
    async def stop(self) -> None:
        """Para descoberta mDNS."""
        logger.info("Parando SwarmDiscovery...")
        self._running = False
        
        # Cancelar tasks
        for task in self._tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        
        # Remover anúncio
        if self._zeroconf and self._info:
            self._zeroconf.unregister_service(self._info)
        
        if self._browser:
            self._browser.cancel()
        
        if self._zeroconf:
            self._zeroconf.close()
        
        logger.info("SwarmDiscovery parado")
    
    def _start_announcement(self) -> None:
        """Inicia anúncio mDNS."""
        if not self._zeroconf:
            return
        
        self._info = ServiceInfo(
            type_=SERVICE_TYPE,
            name=f"{self.agent_id}.{SERVICE_TYPE}",
            addresses=[socket.inet_aton(self._local_ip)],
            port=self.port,
            properties={
                "node_id": self.agent_id.encode("utf-8"),
                "name": self.name.encode("utf-8"),
                "capabilities": json.dumps(self.capabilities).encode("utf-8"),
                "specialties": json.dumps(self.specialties).encode("utf-8"),
                "model": self.model.encode("utf-8"),
                "benchmark": json.dumps(self.benchmark).encode("utf-8"),
                "protocol_version": "2.0".encode("utf-8"),
                "load": "0.0".encode("utf-8"),
            },
            server=f"{self.agent_id}.local.",
        )
        self._zeroconf.register_service(self._info)
    
    def _update_announcement(self, load: float) -> None:
        """Atualiza anúncio com nova carga."""
        if self._zeroconf and self._info:
            self._info.properties = {
                "node_id": self.agent_id.encode("utf-8"),
                "name": self.name.encode("utf-8"),
                "capabilities": json.dumps(self.capabilities).encode("utf-8"),
                "specialties": json.dumps(self.specialties).encode("utf-8"),
                "model": self.model.encode("utf-8"),
                "benchmark": json.dumps(self.benchmark).encode("utf-8"),
                "protocol_version": "2.0".encode("utf-8"),
                "load": str(load).encode("utf-8"),
            }
            self._zeroconf.update_service(self._info)
    
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
                key = k.decode("utf-8") if isinstance(k, bytes) else k
                val = v.decode("utf-8") if isinstance(v, bytes) else str(v)
                props[key] = val
            except Exception:
                pass
        
        node_id = props.get("node_id")
        if not node_id or node_id == self.agent_id:
            return  # Ignorar a si mesmo
        
        host = socket.inet_ntoa(info.addresses[0])
        port = info.port
        
        # Parse capabilities e specialties
        caps = []
        try:
            caps = json.loads(props.get("capabilities", "[]"))
        except Exception:
            pass
        
        specs = []
        try:
            specs = json.loads(props.get("specialties", "[]"))
        except Exception:
            pass
        
        benchmark = {}
        try:
            benchmark = json.loads(props.get("benchmark", "{}"))
        except Exception:
            pass
        
        load = float(props.get("load", 0.0))
        
        peer = DiscoveredPeer(
            node_id=node_id,
            name=props.get("name", node_id),
            host=host,
            port=port,
            capabilities=caps,
            specialties=specs,
            model=props.get("model", ""),
            benchmark=benchmark,
            load=load,
            last_seen=datetime.now(UTC),
            status="connected",
        )
        
        is_new = node_id not in self._peers
        self._peers[node_id] = peer
        
        if is_new:
            logger.info(f"Peer descoberto: {node_id} ({peer.name}) - caps: {caps}")
            if self.on_peer_found:
                self.on_peer_found(peer)
        else:
            if self.on_peer_updated:
                self.on_peer_updated(peer)
    
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
            peer = self._peers[node_id]
            peer.status = "disconnected"
            del self._peers[node_id]
            logger.warning(f"Peer removido: {node_id} ({peer.name})")
            if self.on_peer_lost:
                self.on_peer_lost(node_id)
    
    def get_active_peers(self) -> list[DiscoveredPeer]:
        """Retorna lista de peers ativos."""
        now = datetime.now(UTC)
        active = []
        for peer in self._peers.values():
            elapsed = (now - peer.last_seen).total_seconds()
            if elapsed < self.heartbeat_timeout and peer.status != "disconnected":
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
        """Retorna peers que têm uma capability específica."""
        active = self.get_active_peers()
        return [p for p in active if capability in p.capabilities]
    
    def get_peers_by_specialty(self, specialty: str) -> list[DiscoveredPeer]:
        """Retorna peers que têm uma especialidade específica."""
        active = self.get_active_peers()
        return [p for p in active if specialty in p.specialties]
    
    async def update_peer_profile(self, node_id: str, profile: dict[str, Any]) -> None:
        """Atualiza perfil do peer (recebido via handshake HTTP)."""
        if node_id in self._peers:
            self._peers[node_id].profile = profile
            self._peers[node_id].capabilities = profile.get("capabilities", [])
            self._peers[node_id].specialties = profile.get("specialties", [])
            self._peers[node_id].model = profile.get("model", "")
            self._peers[node_id].last_seen = datetime.now(UTC)
            
            if self.on_peer_updated:
                self.on_peer_updated(self._peers[node_id])
    
    async def update_peer_heartbeat(self, node_id: str, load: float, status: str = "connected") -> None:
        """Atualiza heartbeat do peer."""
        if node_id in self._peers:
            peer = self._peers[node_id]
            peer.load = load
            peer.last_heartbeat = datetime.now(UTC)
            peer.last_seen = datetime.now(UTC)
            peer.status = status
    
    # =========================================================================
    # Loops de Background
    # =========================================================================
    
    async def _announcement_loop(self) -> None:
        """Loop de re-anúncio periódico."""
        while self._running:
            try:
                await asyncio.sleep(self.announce_interval)
                if self._running:
                    self._update_announcement(self._get_current_load())
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no announcement loop: {e}")
    
    async def _heartbeat_loop(self) -> None:
        """Loop de heartbeat para peers conhecidos."""
        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                if not self._running:
                    break
                
                # Enviar heartbeat para peers via HTTP
                for peer in self.get_active_peers():
                    await self._send_heartbeat_to_peer(peer)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no heartbeat loop: {e}")
    
    async def _send_heartbeat_to_peer(self, peer: DiscoveredPeer) -> None:
        """Envia heartbeat para peer via HTTP."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.post(
                    f"http://{peer.host}:{peer.port}/api/v1/heartbeat",
                    json={
                        "source_id": self.agent_id,
                        "load": self._get_current_load(),
                        "sequence": self._heartbeat_sequence,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
                if resp.status_code == 200:
                    peer.last_heartbeat = datetime.now(UTC)
                    self._heartbeat_sequence += 1
        except Exception:
            pass  # Peer pode estar indisponível temporariamente
    
    def _get_current_load(self) -> float:
        """Calcula carga atual (placeholder - integrar com pool real)."""
        import psutil
        try:
            cpu = psutil.cpu_percent(interval=0.1) / 100.0
            mem = psutil.virtual_memory().percent / 100.0
            return round((cpu + mem) / 2.0, 2)
        except Exception:
            return 0.0
    
    async def _cleanup_loop(self) -> None:
        """Loop de limpeza de peers stale."""
        while self._running:
            try:
                await asyncio.sleep(30)
                await self._cleanup_stale_peers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no cleanup loop: {e}")
    
    async def _cleanup_stale_peers(self) -> None:
        """Remove peers que não enviam heartbeat há muito tempo."""
        now = datetime.now(UTC)
        stale = []
        
        for node_id, peer in self._peers.items():
            elapsed = (now - peer.last_seen).total_seconds()
            if elapsed > self.heartbeat_timeout:
                stale.append(node_id)
        
        for node_id in stale:
            logger.warning(f"Peer stale removido: {node_id} (sem contato por {elapsed:.0f}s)")
            self._remove_peer(node_id)
    
    # =========================================================================
    # Handshake de Capacidades (HTTP)
    # =========================================================================
    
    async def request_peer_profile(self, node_id: str) -> dict[str, Any] | None:
        """Solicita perfil completo do peer via HTTP."""
        peer = self.get_peer(node_id)
        if not peer:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"http://{peer.host}:{peer.port}/api/v1/profile")
                if resp.status_code == 200:
                    profile = resp.json()
                    await self.update_peer_profile(node_id, profile)
                    return profile
        except Exception as e:
            logger.debug(f"Erro ao solicitar perfil de {node_id}: {e}")
        return None
    
    async def request_peer_capabilities(self, node_id: str) -> list[str] | None:
        """Solicita capacidades do peer."""
        peer = self.get_peer(node_id)
        if not peer:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"http://{peer.host}:{peer.port}/api/v1/capabilities")
                if resp.status_code == 200:
                    data = resp.json()
                    caps = data.get("capabilities", [])
                    await self.update_peer_profile(node_id, {"capabilities": caps})
                    return caps
        except Exception:
            pass
        return None
    
    # =========================================================================
    # Dispatch de Tarefas para Peers
    # =========================================================================
    
    async def dispatch_task_to_peer(
        self,
        node_id: str,
        task_id: str,
        subtask: str,
        context: str | None,
        required_capabilities: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Envia tarefa para execução em peer específico."""
        peer = self.get_peer(node_id)
        if not peer:
            return {"error": f"Peer {node_id} não encontrado ou inativo"}
        
        # Verificar capabilities se requeridas
        if required_capabilities:
            missing = [c for c in required_capabilities if c not in peer.capabilities]
            if missing:
                return {"error": f"Peer não tem capabilities: {missing}"}
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"http://{peer.host}:{peer.port}/api/v1/execute",
                    json={
                        "task_id": task_id,
                        "subtask": subtask,
                        "context": context,
                        "source_id": self.agent_id,
                    },
                )
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"Peer retornou {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"error": f"Falha ao despachar para peer: {e}"}
    
    async def broadcast_task(
        self,
        task_id: str,
        subtask: str,
        context: str | None,
        required_capabilities: list[str] | None = None,
    ) -> dict[str, Any]:
        """Transmite tarefa para todos peers capazes (melhor resposta vence)."""
        capable_peers = self.get_active_peers()
        
        if required_capabilities:
            capable_peers = [
                p for p in capable_peers 
                if all(c in p.capabilities for c in required_capabilities)
            ]
        
        if not capable_peers:
            return {"error": "Nenhum peer com capabilities necessárias"}
        
        # Enviar para todos peers capazes em paralelo
        tasks = [
            self.dispatch_task_to_peer(p.node_id, task_id, subtask, context, required_capabilities)
            for p in capable_peers
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Retornar melhor resultado (primeiro sucesso)
        for i, result in enumerate(results):
            if isinstance(result, dict) and "error" not in result:
                result["peer_id"] = capable_peers[i].node_id
                return result
        
        # Se todos falharam, retornar primeiro erro
        return {"error": "Todos peers falharam", "details": [str(r) for r in results]}
    
    # =========================================================================
    # Status e Estatísticas
    # =========================================================================
    
    def get_stats(self) -> dict[str, Any]:
        active = self.get_active_peers()
        return {
            "agent_id": self.agent_id,
            "local_ip": self._local_ip,
            "port": self.port,
            "total_discovered": len(self._peers),
            "active_peers": len(active),
            "peers": [
                {
                    "node_id": p.node_id,
                    "name": p.name,
                    "host": p.host,
                    "port": p.port,
                    "capabilities": p.capabilities,
                    "specialties": p.specialties,
                    "model": p.model,
                    "load": p.load,
                    "status": p.status,
                    "last_seen": p.last_seen.isoformat(),
                }
                for p in active
            ],
            "capabilities_summary": self._get_capabilities_summary(),
        }
    
    def _get_capabilities_summary(self) -> dict[str, int]:
        """Resumo de capabilities disponíveis no enxame."""
        summary = {}
        for peer in self.get_active_peers():
            for cap in peer.capabilities:
                summary[cap] = summary.get(cap, 0) + 1
        return summary
    
    def list_all_peers(self) -> list[DiscoveredPeer]:
        """Lista todos peers (incluindo inativos)."""
        return list(self._peers.values())


# Import para httpx
import httpx