"""Auto-descoberta de nós via Zeroconf (mDNS)."""
from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Callable

from zeroconf import IPVersion, ServiceBrowser, ServiceInfo, ServiceStateChange, Zeroconf


@dataclass(slots=True)
class NodeAnnouncer:
    """Publica a presença do nó na rede local via mDNS."""

    node_id: str
    role: str
    host_ip: str
    port: int
    capabilities: str = "exp,ws,http"
    models: str = ""
    service_type: str = "_enxame._tcp.local."

    _zeroconf: Zeroconf = field(init=False, repr=False, compare=False)
    _info: ServiceInfo | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        self._info = None

    def start(self) -> None:
        """Registra o serviço mDNS."""
        full_name = f"{self.node_id}.{self.service_type}"
        self._info = ServiceInfo(
            type_=self.service_type,
            name=full_name,
            addresses=[socket.inet_aton(self.host_ip)],
            port=self.port,
            properties={
                "node_id": self.node_id.encode("utf-8"),
                "role": self.role.encode("utf-8"),
                "capabilities": self.capabilities.encode("utf-8"),
                "models": self.models.encode("utf-8"),
            },
            server=f"{self.node_id}.local.",
        )
        self._zeroconf.register_service(self._info)

    def stop(self) -> None:
        """Remove o registro mDNS e fecha a conexão."""
        if self._info is not None:
            self._zeroconf.unregister_service(self._info)
        self._zeroconf.close()


@dataclass(slots=True)
class DiscoveredNode:
    """Informações de um nó descoberto na rede."""

    node_id: str
    role: str
    host: str
    port: int
    capabilities: str
    models: str


class NodeListener:
    """Escuta e registra dinamicamente novos nós na rede local via mDNS."""

    def __init__(self, on_node_found: Callable[[DiscoveredNode], None] | None = None) -> None:
        self.zeroconf = Zeroconf()
        self.nodes: dict[str, DiscoveredNode] = {}
        self._browser: ServiceBrowser | None = None
        self._on_node_found = on_node_found

    def _on_service_state_change(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        if state_change is ServiceStateChange.Removed:
            self.nodes.pop(name, None)
            return

        info = zeroconf.get_service_info(service_type, name)
        if not info or not info.addresses:
            return

        props = {k.decode("utf-8"): v.decode("utf-8") for k, v in info.properties.items()}
        host = socket.inet_ntoa(info.addresses[0])
        node = DiscoveredNode(
            node_id=props.get("node_id", name),
            role=props.get("role", "unknown"),
            host=host,
            port=info.port,
            capabilities=props.get("capabilities", ""),
            models=props.get("models", ""),
        )
        self.nodes[name] = node
        if self._on_node_found:
            self._on_node_found(node)

    def start(self) -> None:
        """Inicia a escuta por serviços mDNS."""
        self._browser = ServiceBrowser(
            self.zeroconf,
            "_enxame._tcp.local.",
            handlers=[self._on_service_state_change],
        )

    def stop(self) -> None:
        """Para a escuta e fecha a conexão."""
        self.zeroconf.close()
