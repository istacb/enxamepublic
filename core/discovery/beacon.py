"""Descoberta de nós Enxame na LAN.

Duas camadas, sem dependência obrigatória:
1. UDP broadcast beacon (sempre funciona em redes locais simples).
2. mDNS via zeroconf (opcional, para redes onde multicast está bloqueado).

Cada nó anuncia: node_id, ip, http_port, ws_port, role, score, models.
"""
from __future__ import annotations

import json
import socket
import threading
from dataclasses import dataclass, field
from typing import Callable

BEACON_PORT = 9999
BEACON_INTERVAL = 5.0
MAGIC = b'ENXAME'


@dataclass(slots=True)
class PeerInfo:
    node_id: str
    ip: str
    http_port: int
    ws_port: int
    role: str
    score: float
    models: list[str] = field(default_factory=list)
    last_seen: float = 0.0


class Beacon:
    """Envia e recebe beacons UDP de descoberta."""

    def __init__(
        self,
        node_id: str,
        ip: str,
        http_port: int,
        ws_port: int,
        role: str,
        score: float,
        models: list[str] | None = None,
        on_peer: Callable[[PeerInfo], None] | None = None,
    ) -> None:
        self.node_id = node_id
        self.ip = ip
        self.http_port = http_port
        self.ws_port = ws_port
        self.role = role
        self.score = score
        self.models = models or []
        self.on_peer = on_peer
        self.peers: dict[str, PeerInfo] = {}
        self._lock = threading.Lock()
        self._running = False
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def _payload(self) -> dict:
        return {
            'node_id': self.node_id,
            'ip': self.ip,
            'http_port': self.http_port,
            'ws_port': self.ws_port,
            'role': self.role,
            'score': self.score,
            'models': self.models,
        }

    def _recv_loop(self) -> None:
        assert self._sock is not None
        while self._running:
            try:
                data, addr = self._sock.recvfrom(4096)
            except OSError:
                break
            if not data.startswith(MAGIC):
                continue
            try:
                msg = json.loads(data[len(MAGIC):].decode('utf-8'))
            except Exception:
                continue
            peer = PeerInfo(
                node_id=str(msg.get('node_id', '')),
                ip=addr[0],
                http_port=int(msg.get('http_port', 0)),
                ws_port=int(msg.get('ws_port', 0)),
                role=str(msg.get('role', 'agente')),
                score=float(msg.get('score', 0)),
                models=list(msg.get('models', [])),
            )
            if not peer.node_id or peer.node_id == self.node_id:
                continue
            import time

            peer.last_seen = time.time()
            with self._lock:
                self.peers[peer.node_id] = peer
            if self.on_peer:
                try:
                    self.on_peer(peer)
                except Exception:
                    pass

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except OSError:
            pass
        self._sock.bind(('0.0.0.0', BEACON_PORT))
        self._sock.settimeout(1.0)
        self._running = True
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()

    def announce(self) -> None:
        if self._sock is None:
            return
        payload = MAGIC + json.dumps(self._payload()).encode('utf-8')
        try:
            self._sock.sendto(payload, ('<broadcast>', BEACON_PORT))
        except OSError:
            pass

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass

    def list_peers(self) -> list[PeerInfo]:
        import time

        now = time.time()
        with self._lock:
            fresh = [p for p in self.peers.values() if now - p.last_seen < 15]
        return fresh


def discover_peers(timeout: float = 3.0) -> list[PeerInfo]:
    """Descoberta one-shot: envia um beacon e coleta respostas."""
    import time

    found: dict[str, PeerInfo] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except OSError:
        pass
    sock.bind(('0.0.0.0', 0))
    sock.settimeout(0.5)

    payload = MAGIC + json.dumps({'probe': True}).encode('utf-8')
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            sock.sendto(payload, ('<broadcast>', BEACON_PORT))
        except OSError:
            pass
        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            continue
        except OSError:
            break
        if not data.startswith(MAGIC):
            continue
        try:
            msg = json.loads(data[len(MAGIC):].decode('utf-8'))
        except Exception:
            continue
        nid = str(msg.get('node_id', ''))
        if not nid or nid in found:
            continue
        found[nid] = PeerInfo(
            node_id=nid,
            ip=addr[0],
            http_port=int(msg.get('http_port', 0)),
            ws_port=int(msg.get('ws_port', 0)),
            role=str(msg.get('role', 'agente')),
            score=float(msg.get('score', 0)),
            models=list(msg.get('models', [])),
            last_seen=time.time(),
        )
    sock.close()
    return list(found.values())


def mdns_available() -> bool:
    try:
        import zeroconf  # noqa: F401

        return True
    except Exception:
        return False
