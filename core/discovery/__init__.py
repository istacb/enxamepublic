"""Descoberta de rede Enxame: UDP beacon + mDNS real (zeroconf)."""
from .beacon import Beacon, PeerInfo, discover_peers, BEACON_PORT
from .mdns import MdnsDiscovery, MdnsPeer, MDNS_TYPE, MDNS_PORT

__all__ = [
    'Beacon',
    'PeerInfo',
    'discover_peers',
    'BEACON_PORT',
    'MdnsDiscovery',
    'MdnsPeer',
    'MDNS_TYPE',
    'MDNS_PORT',
]
