"""
ENXAME Bees — Abelhas Standalone
================================
Pacote principal para Abelhas autônomas do sistema Enxame.

Cada Abelha é uma unidade independente que:
- Opera offline-first (memória local → RAG local → peers → web)
- Descobre peers via mDNS
- Comunica-se via protocolo BEE (WebSocket + HMAC)
- Mantém identidade, memória e índice próprios
"""

# Lazy imports para evitar dependências opcionais no import principal
def __getattr__(name: str):
    lazy_modules = {
        # Config
        "BeeConfig": ("bees.config", "BeeConfig"),
        "load_config": ("bees.config", "load_config"),
        "get_default_data_dir": ("bees.config", "get_default_data_dir"),
        "generate_identity": ("bees.config", "generate_identity"),
        "load_identity": ("bees.config", "load_identity"),
        # Service (requer zeroconf)
        "BeeService": ("bees.service", "BeeService"),
        # Components
        "LocalBeeLibrarian": ("bees.librarian", "LocalBeeLibrarian"),
        "BeeMemory": ("bees.memory", "BeeMemory"),
        "BeeDiscoveryService": ("bees.discovery", "BeeDiscoveryService"),
        # Protocol
        "BeeEnvelope": ("bees.protocol.envelope", "BeeEnvelope"),
        "BeeProtocolHandler": ("bees.protocol.handler", "BeeProtocolHandler"),
        # Messages
        "BeeMessageType": ("bees.protocol.messages", "BeeMessageType"),
        "BeeState": ("bees.protocol.messages", "BeeState"),
        "BeeIdentity": ("bees.protocol.messages", "BeeIdentity"),
        "BeeManifesto": ("bees.protocol.messages", "BeeManifesto"),
        "BeeHello": ("bees.protocol.messages", "BeeHello"),
        "BeeHelloAck": ("bees.protocol.messages", "BeeHelloAck"),
        "BeeHeartbeat": ("bees.protocol.messages", "BeeHeartbeat"),
        "BeeHeartbeatAck": ("bees.protocol.messages", "BeeHeartbeatAck"),
        "BeeKnowledgeQuery": ("bees.protocol.messages", "BeeKnowledgeQuery"),
        "BeeKnowledgeResponse": ("bees.protocol.messages", "BeeKnowledgeResponse"),
        "BeeResearchRequest": ("bees.protocol.messages", "BeeResearchRequest"),
        "BeeResearchResult": ("bees.protocol.messages", "BeeResearchResult"),
        "BeeModelRequest": ("bees.protocol.messages", "BeeModelRequest"),
        "BeeModelResponse": ("bees.protocol.messages", "BeeModelResponse"),
        "BeeCapabilityQuery": ("bees.protocol.messages", "BeeCapabilityQuery"),
        "BeeCapabilityResponse": ("bees.protocol.messages", "BeeCapabilityResponse"),
        "BeeStateChange": ("bees.protocol.messages", "BeeStateChange"),
        "BeePeerLost": ("bees.protocol.messages", "BeePeerLost"),
        "BeeError": ("bees.protocol.messages", "BeeError"),
        "BeeErrorCode": ("bees.protocol.messages", "BeeErrorCode"),
    }
    
    if name in lazy_modules:
        module_name, attr_name = lazy_modules[name]
        module = __import__(module_name, fromlist=[attr_name])
        return getattr(module, attr_name)
    
    raise AttributeError(f"module 'bees' has no attribute '{name}'")


__version__ = "1.0.0"

__all__ = [
    # Config
    "BeeConfig",
    "load_config",
    "get_default_data_dir",
    "generate_identity",
    "load_identity",
    # Service
    "BeeService",
    # Components
    "LocalBeeLibrarian",
    "BeeMemory",
    "BeeDiscoveryService",
    # Protocol
    "BeeEnvelope",
    "BeeProtocolHandler",
    # Messages
    "BeeMessageType",
    "BeeState",
    "BeeIdentity",
    "BeeManifesto",
    "BeeHello",
    "BeeHelloAck",
    "BeeHeartbeat",
    "BeeHeartbeatAck",
    "BeeKnowledgeQuery",
    "BeeKnowledgeResponse",
    "BeeResearchRequest",
    "BeeResearchResult",
    "BeeModelRequest",
    "BeeModelResponse",
    "BeeCapabilityQuery",
    "BeeCapabilityResponse",
    "BeeStateChange",
    "BeePeerLost",
    "BeeError",
    "BeeErrorCode",
]