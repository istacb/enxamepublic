from __future__ import annotations

from dataclasses import dataclass
import socket
from threading import Event

from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf


@dataclass(slots=True)
class DiscoveredNode:
    node_id: str
    role: str
    host: str
    port: int
    capabilities: str
    models: str


class ENXAMEMDNSBrowser:
    def __init__(self) -> None:
        self.zeroconf = Zeroconf()
        self.nodes: dict[str, DiscoveredNode] = {}
        self._stop_event = Event()
        self._browser: ServiceBrowser | None = None

    def _on_service_state_change(self, zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        if state_change is ServiceStateChange.Removed:
            self.nodes.pop(name, None)
            return

        info = zeroconf.get_service_info(service_type, name)
        if not info or not info.addresses:
            return

        props = {k.decode("utf-8"): v.decode("utf-8") for k, v in info.properties.items()}
        host = socket.inet_ntoa(info.addresses[0])
        self.nodes[name] = DiscoveredNode(
            node_id=props.get("node_id", name),
            role=props.get("role", "unknown"),
            host=host,
            port=info.port,
            capabilities=props.get("capabilities", ""),
            models=props.get("models", ""),
        )

    def start(self) -> None:
        self._browser = ServiceBrowser(
            self.zeroconf,
            "_enxame._tcp.local.",
            handlers=[self._on_service_state_change],
        )

    def stop(self) -> None:
        self._stop_event.set()
        self.zeroconf.close()
