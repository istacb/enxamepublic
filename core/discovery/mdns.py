"""Descoberta mDNS real via zeroconf (opcional).

Anuncia _enxame._tcp.local e descobre peers no segmento de rede.
Se zeroconf não estiver instalado, fica silencioso (fallback UDP beacon).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Optional

try:
    from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf
    from zeroconf._services.interfaces import ServiceStateChange
    ZEROCONF_AVAILABLE = True
except Exception:  # pragma: no cover - zeroconf não instalado
    ZEROCONF_AVAILABLE = False
    ServiceBrowser = None  # type: ignore
    ServiceInfo = None  # type: ignore
    Zeroconf = None  # type: ignore
    ServiceStateChange = None  # type: ignore


MDNS_TYPE = '_enxame._tcp.local.'
MDNS_PORT = 7700


@dataclass(slots=True)
class MdnsPeer:
    node_id: str
    ip: str
    port: int
    role: str
    score: float
    models: list[str]


class MdnsDiscovery:
    def __init__(
        self,
        node_id: str,
        ip: str,
        port: int,
        role: str,
        score: float,
        models: list[str] | None = None,
        on_peer: Optional[Callable[[MdnsPeer], None]] = None,
    ) -> None:
        self.node_id = node_id
        self.ip = ip
        self.port = port
        self.role = role
        self.score = score
        self.models = models or []
        self.on_peer = on_peer
        self.zeroconf: Optional[object] = None
        self.browser: Optional[object] = None
        self._info: Optional[object] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.peers: dict[str, MdnsPeer] = {}
        self._lock = threading.Lock()

    def available(self) -> bool:
        return ZEROCONF_AVAILABLE

    def start(self) -> None:
        if not ZEROCONF_AVAILABLE:
            return
        import socket

        self.zeroconf = Zeroconf()

        # Anuncia este nó.
        props = {
            'node_id': self.node_id.encode('utf-8'),
            'role': self.role.encode('utf-8'),
            'score': str(self.score).encode('utf-8'),
            'models': ','.join(self.models).encode('utf-8'),
        }
        self._info = ServiceInfo(
            MDNS_TYPE,
            f'{self.node_id}.{MDNS_TYPE}',
            addresses=[socket.inet_aton(self.ip)] if self.ip != '0.0.0.0' else None,
            port=self.port,
            properties=props,
            server=f'{self.node_id}.local.',
        )
        self.zeroconf.register_service(self._info)

        # Descobre peers.
        def on_service_state_change(
            zc: object, service_type: str, name: str, state_change: object
        ) -> None:
            if state_change is ServiceStateChange.Added:
                info = zc.get_service_info(service_type, name, timeout=3000)
                if info is None or info.name == (self._info.name if self._info else ''):
                    return
                try:
                    ip = str(info.parsed_addresses()[0]) if info.parsed_addresses() else ''
                except Exception:
                    ip = ''
                nid = str(info.properties.get(b'node_id', b'').decode('utf-8'))
                if not nid or nid == self.node_id:
                    return
                peer = MdnsPeer(
                    node_id=nid,
                    ip=ip,
                    port=info.port or MDNS_PORT,
                    role=str(info.properties.get(b'role', b'agente').decode('utf-8')),
                    score=float(info.properties.get(b'score', b'0').decode('utf-8') or 0),
                    models=[
                        m for m in str(info.properties.get(b'models', b'').decode('utf-8')).split(',') if m
                    ],
                )
                with self._lock:
                    self.peers[peer.node_id] = peer
                if self.on_peer:
                    try:
                        self.on_peer(peer)
                    except Exception:
                        pass

        self.browser = ServiceBrowser(self.zeroconf, MDNS_TYPE, handlers=[on_service_state_change])
        self._running = True

    def stop(self) -> None:
        self._running = False
        if self.zeroconf is not None:
            try:
                if self._info is not None:
                    self.zeroconf.unregister_service(self._info)
                self.zeroconf.close()
            except Exception:
                pass
            self.zeroconf = None
        self.browser = None

    def list_peers(self) -> list[MdnsPeer]:
        with self._lock:
            return list(self.peers.values())
