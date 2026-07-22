from __future__ import annotations

from dataclasses import dataclass
import socket

from zeroconf import IPVersion, ServiceInfo, Zeroconf


@dataclass(slots=True)
class ENXAMEMDNSAdvertiser:
    service_name: str
    node_id: str
    role: str
    host_ip: str
    port: int
    capabilities: str = "exp,ws,http"
    models: str = ""

    def __post_init__(self) -> None:
        self._zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        self._info: ServiceInfo | None = None

    def start(self) -> None:
        full_name = f"{self.service_name}._enxame._tcp.local."
        self._info = ServiceInfo(
            type_="_enxame._tcp.local.",
            name=full_name,
            addresses=[socket.inet_aton(self.host_ip)],
            port=self.port,
            properties={
                "node_id": self.node_id,
                "role": self.role,
                "capabilities": self.capabilities,
                "models": self.models,
            },
            server=f"{self.node_id}.local.",
        )
        self._zeroconf.register_service(self._info)

    def stop(self) -> None:
        if self._info is not None:
            self._zeroconf.unregister_service(self._info)
        self._zeroconf.close()
