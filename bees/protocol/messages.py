"""Tipos de mensagem e estruturas do protocolo BEE."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class BeeMessageType(StrEnum):
    """Tipos de mensagem do protocolo BEE entre Abelhas."""

    # Handshake
    HELLO = "BEE_HELLO"
    HELLO_ACK = "BEE_HELLO_ACK"

    # Heartbeat
    HEARTBEAT = "BEE_HEARTBEAT"
    HEARTBEAT_ACK = "BEE_HEARTBEAT_ACK"

    # Consultas
    KNOWLEDGE_QUERY = "BEE_KNOWLEDGE_QUERY"
    KNOWLEDGE_RESPONSE = "BEE_KNOWLEDGE_RESPONSE"
    RESEARCH_REQUEST = "BEE_RESEARCH_REQUEST"
    RESEARCH_RESULT = "BEE_RESEARCH_RESULT"
    MODEL_REQUEST = "BEE_MODEL_REQUEST"
    MODEL_RESPONSE = "BEE_MODEL_RESPONSE"

    # Estado
    STATE_CHANGE = "BEE_STATE_CHANGE"
    PEER_LOST = "BEE_PEER_LOST"

    # Capability discovery
    CAPABILITY_QUERY = "BEE_CAPABILITY_QUERY"
    CAPABILITY_RESPONSE = "BEE_CAPABILITY_RESPONSE"

    # Erros
    ERROR = "BEE_ERROR"


# Versão atual do protocolo BEE
BEE_PROTOCOL_VERSION = "1.0"


@dataclass(slots=True)
class BeeIdentity:
    """Identidade única de uma Abelha."""

    node_id: str  # UUID v4 único
    public_key: str | None = None  # Chave pública Ed25519 (base64), opcional
    protocol_version: str = field(default=BEE_PROTOCOL_VERSION)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "public_key": self.public_key,
            "protocol_version": self.protocol_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeIdentity:
        return cls(
            node_id=data["node_id"],
            public_key=data.get("public_key"),
            protocol_version=data.get("protocol_version", BEE_PROTOCOL_VERSION),
        )


@dataclass(slots=True)
class BeeManifesto:
    """Metadados que descrevem capacidades e estado de uma Abelha."""

    capabilities: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    indexes: list[str] = field(default_factory=list)
    load: float = 0.0  # 0.0 (ocioso) a 1.0 (sobrecarregado)
    uptime_seconds: int = 0
    last_activity: datetime | None = None
    version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "capabilities": self.capabilities,
            "models": self.models,
            "indexes": self.indexes,
            "load": self.load,
            "uptime_seconds": self.uptime_seconds,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeManifesto:
        last_activity = None
        if data.get("last_activity"):
            last_activity = datetime.fromisoformat(data["last_activity"])
        return cls(
            capabilities=data.get("capabilities", []),
            models=data.get("models", []),
            indexes=data.get("indexes", []),
            load=data.get("load", 0.0),
            uptime_seconds=data.get("uptime_seconds", 0),
            last_activity=last_activity,
            version=data.get("version", "1.0.0"),
        )

    def has_capability(self, capability: str) -> bool:
        """Verifica se esta Abelha possui uma capability específica."""
        return capability in self.capabilities

    def has_model(self, model_name: str) -> bool:
        """Verifica se esta Abelha possui um modelo específico."""
        return model_name in self.models

    def has_index(self, index_name: str) -> bool:
        """Verifica se esta Abelha possui um índice específico."""
        return index_name in self.indexes


# ============================================================================
# Mensagens de Handshake
# ============================================================================


@dataclass(slots=True)
class BeeHello:
    """Mensagem inicial de handshake."""

    identity: BeeIdentity
    manifesto: BeeManifesto
    nonce: str  # Random bytes em base64 para prevenção de replay

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "manifesto": self.manifesto.to_dict(),
            "nonce": self.nonce,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeHello:
        return cls(
            identity=BeeIdentity.from_dict(data["identity"]),
            manifesto=BeeManifesto.from_dict(data["manifesto"]),
            nonce=data["nonce"],
        )


@dataclass(slots=True)
class BeeHelloAck:
    """Resposta ao handshake inicial."""

    identity: BeeIdentity
    manifesto: BeeManifesto
    nonce: str
    echo_nonce: str  # Deve bater com o nonce do HELLO original

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "manifesto": self.manifesto.to_dict(),
            "nonce": self.nonce,
            "echo_nonce": self.echo_nonce,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeHelloAck:
        return cls(
            identity=BeeIdentity.from_dict(data["identity"]),
            manifesto=BeeManifesto.from_dict(data["manifesto"]),
            nonce=data["nonce"],
            echo_nonce=data["echo_nonce"],
        )


# ============================================================================
# Mensagens de Heartbeat
# ============================================================================


class BeeState(StrEnum):
    """Estados possíveis de uma Abelha."""

    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    DEGRADED = "DEGRADED"


@dataclass(slots=True)
class BeeHeartbeat:
    """Mensagem de heartbeat para manter conexão ativa."""

    node_id: str
    state: BeeState
    load: float
    timestamp: datetime
    sequence: int  # Número sequencial para detecção de perda

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "load": self.load,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeHeartbeat:
        return cls(
            node_id=data["node_id"],
            state=BeeState(data["state"]),
            load=data["load"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sequence=data["sequence"],
        )


@dataclass(slots=True)
class BeeHeartbeatAck:
    """Resposta ao heartbeat."""

    node_id: str
    state: BeeState
    load: float
    timestamp: datetime
    sequence: int
    ack_sequence: int  # Sequência do heartbeat sendo reconhecido

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "load": self.load,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
            "ack_sequence": self.ack_sequence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeHeartbeatAck:
        return cls(
            node_id=data["node_id"],
            state=BeeState(data["state"]),
            load=data["load"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sequence=data["sequence"],
            ack_sequence=data["ack_sequence"],
        )


# ============================================================================
# Mensagens de Consulta - Knowledge Query
# ============================================================================


@dataclass(slots=True)
class BeeKnowledgeQuery:
    """Consulta leve para verificar se outra Abelha tem conhecimento relevante."""

    query_id: str
    subject: str
    keywords: list[str] = field(default_factory=list)
    min_confidence: float = 0.6
    timeout_ms: int = 2000

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "subject": self.subject,
            "keywords": self.keywords,
            "min_confidence": self.min_confidence,
            "timeout_ms": self.timeout_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeKnowledgeQuery:
        return cls(
            query_id=data["query_id"],
            subject=data["subject"],
            keywords=data.get("keywords", []),
            min_confidence=data.get("min_confidence", 0.6),
            timeout_ms=data.get("timeout_ms", 2000),
        )


@dataclass(slots=True)
class BeeKnowledgeResponse:
    """Resposta à consulta de conhecimento."""

    query_id: str
    has_knowledge: bool
    confidence: float = 0.0
    document_count: int = 0
    topics: list[str] = field(default_factory=list)
    oldest_doc: str | None = None  # ISO date
    newest_doc: str | None = None  # ISO date

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "has_knowledge": self.has_knowledge,
            "confidence": self.confidence,
            "document_count": self.document_count,
            "topics": self.topics,
            "oldest_doc": self.oldest_doc,
            "newest_doc": self.newest_doc,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeKnowledgeResponse:
        return cls(
            query_id=data["query_id"],
            has_knowledge=data["has_knowledge"],
            confidence=data.get("confidence", 0.0),
            document_count=data.get("document_count", 0),
            topics=data.get("topics", []),
            oldest_doc=data.get("oldest_doc"),
            newest_doc=data.get("newest_doc"),
        )


# ============================================================================
# Mensagens de Consulta - Research Request
# ============================================================================


@dataclass(slots=True)
class BeeResearchRequest:
    """Solicitação de pesquisa completa com RAG local."""

    request_id: str
    query: str
    context: str | None = None
    max_results: int = 10
    include_sources: bool = True
    timeout_ms: int = 30000

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "query": self.query,
            "context": self.context,
            "max_results": self.max_results,
            "include_sources": self.include_sources,
            "timeout_ms": self.timeout_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeResearchRequest:
        return cls(
            request_id=data["request_id"],
            query=data["query"],
            context=data.get("context"),
            max_results=data.get("max_results", 10),
            include_sources=data.get("include_sources", True),
            timeout_ms=data.get("timeout_ms", 30000),
        )


@dataclass(slots=True)
class ResearchResultItem:
    """Item individual de resultado de pesquisa."""

    content: str
    source: str | None = None
    confidence: float = 0.0
    page: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "source": self.source,
            "confidence": self.confidence,
            "page": self.page,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResearchResultItem:
        return cls(
            content=data["content"],
            source=data.get("source"),
            confidence=data.get("confidence", 0.0),
            page=data.get("page"),
            metadata=data.get("metadata", {}),
        )


@dataclass(slots=True)
class BeeResearchResult:
    """Resultado de pesquisa completa."""

    request_id: str
    results: list[ResearchResultItem] = field(default_factory=list)
    total_results: int = 0
    processing_time_ms: int = 0
    model_used: str | None = None
    sources_included: bool = False
    partial: bool = False
    more_available: bool = False
    continue_token: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "results": [r.to_dict() for r in self.results],
            "total_results": self.total_results,
            "processing_time_ms": self.processing_time_ms,
            "model_used": self.model_used,
            "sources_included": self.sources_included,
            "partial": self.partial,
            "more_available": self.more_available,
            "continue_token": self.continue_token,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeResearchResult:
        results = [ResearchResultItem.from_dict(r) for r in data.get("results", [])]
        return cls(
            request_id=data["request_id"],
            results=results,
            total_results=data.get("total_results", 0),
            processing_time_ms=data.get("processing_time_ms", 0),
            model_used=data.get("model_used"),
            sources_included=data.get("sources_included", False),
            partial=data.get("partial", False),
            more_available=data.get("more_available", False),
            continue_token=data.get("continue_token"),
        )


# ============================================================================
# Mensagens de Consulta - Model Request
# ============================================================================


@dataclass(slots=True)
class BeeModelRequest:
    """Solicitação de inferência/generação usando modelo local."""

    request_id: str
    prompt: str
    system_prompt: str | None = None
    max_tokens: int = 500
    temperature: float = 0.7
    timeout_ms: int = 60000

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "prompt": self.prompt,
            "system_prompt": self.system_prompt,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout_ms": self.timeout_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeModelRequest:
        return cls(
            request_id=data["request_id"],
            prompt=data["prompt"],
            system_prompt=data.get("system_prompt"),
            max_tokens=data.get("max_tokens", 500),
            temperature=data.get("temperature", 0.7),
            timeout_ms=data.get("timeout_ms", 60000),
        )


@dataclass(slots=True)
class BeeModelResponse:
    """Resposta de inferência/generação."""

    request_id: str
    generation: str
    model_used: str | None = None
    tokens_used: int = 0
    processing_time_ms: int = 0
    finish_reason: str = "stop"  # stop, length, error

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "generation": self.generation,
            "model_used": self.model_used,
            "tokens_used": self.tokens_used,
            "processing_time_ms": self.processing_time_ms,
            "finish_reason": self.finish_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeModelResponse:
        return cls(
            request_id=data["request_id"],
            generation=data["generation"],
            model_used=data.get("model_used"),
            tokens_used=data.get("tokens_used", 0),
            processing_time_ms=data.get("processing_time_ms", 0),
            finish_reason=data.get("finish_reason", "stop"),
        )


# ============================================================================
# Mensagens de Capability Discovery
# ============================================================================


@dataclass(slots=True)
class BeeCapabilityQuery:
    """Consulta sobre capacidade específica."""

    capability: str
    subject: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "subject": self.subject,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeCapabilityQuery:
        return cls(
            capability=data["capability"],
            subject=data.get("subject"),
        )


@dataclass(slots=True)
class BeeCapabilityResponse:
    """Resposta sobre capacidade."""

    has_capability: bool
    confidence: float = 0.0
    document_count: int = 0
    last_updated: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_capability": self.has_capability,
            "confidence": self.confidence,
            "document_count": self.document_count,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeCapabilityResponse:
        last_updated = None
        if data.get("last_updated"):
            last_updated = datetime.fromisoformat(data["last_updated"])
        return cls(
            has_capability=data["has_capability"],
            confidence=data.get("confidence", 0.0),
            document_count=data.get("document_count", 0),
            last_updated=last_updated,
        )


# ============================================================================
# Mensagens de Estado
# ============================================================================


@dataclass(slots=True)
class BeeStateChange:
    """Notificação de mudança de estado."""

    node_id: str
    new_state: BeeState
    reason: str  # maintenance, overload, error, etc.
    estimated_return_seconds: int | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "new_state": self.new_state.value,
            "reason": self.reason,
            "estimated_return_seconds": self.estimated_return_seconds,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeStateChange:
        return cls(
            node_id=data["node_id"],
            new_state=BeeState(data["new_state"]),
            reason=data["reason"],
            estimated_return_seconds=data.get("estimated_return_seconds"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass(slots=True)
class BeePeerLost:
    """Notificação de peer perdido."""

    node_id: str
    last_seen: datetime
    reason: str  # heartbeat_timeout, network_error, shutdown
    missed_heartbeats: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "last_seen": self.last_seen.isoformat(),
            "reason": self.reason,
            "missed_heartbeats": self.missed_heartbeats,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeePeerLost:
        return cls(
            node_id=data["node_id"],
            last_seen=datetime.fromisoformat(data["last_seen"]),
            reason=data["reason"],
            missed_heartbeats=data.get("missed_heartbeats", 0),
        )


# ============================================================================
# Mensagens de Erro
# ============================================================================


class BeeErrorCode(StrEnum):
    """Códigos de erro do protocolo BEE."""

    OK = "OK"
    NOT_FOUND = "NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    OVERLOADED = "OVERLOADED"
    UNSUPPORTED = "UNSUPPORTED"
    AUTH_FAILED = "AUTH_FAILED"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    BAD_PAYLOAD = "BAD_PAYLOAD"
    CONNECTION_LOST = "CONNECTION_LOST"


@dataclass(slots=True)
class BeeError:
    """Mensagem de erro."""

    code: BeeErrorCode
    detail: str | None = None
    request_id: str | None = None  # Correlaciona com request original

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "detail": self.detail,
            "request_id": self.request_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeError:
        return cls(
            code=BeeErrorCode(data["code"]),
            detail=data.get("detail"),
            request_id=data.get("request_id"),
        )
