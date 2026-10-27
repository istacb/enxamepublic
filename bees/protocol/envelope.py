"""Envelope para mensagens do protocolo BEE.

Reutiliza estrutura similar ao EXP Envelope, mas adaptada para Abelhas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .messages import BeeMessageType, BEE_PROTOCOL_VERSION


@dataclass(slots=True)
class BeeEnvelope:
    """Envelope para mensagens do protocolo BEE.

    Attributes:
        protocol_version: Versão do protocolo BEE (ex: "1.0")
        msg_id: UUID único desta mensagem
        correlation_id: ID para correlacionar request/response
        timestamp: Momento de criação da mensagem
        source_node_id: ID da Abelha origem
        target_node_id: ID da Abelha destino (None = broadcast)
        msg_type: Tipo de mensagem (HELLO, QUERY, etc.)
        priority: Prioridade 1-10 (5 = normal)
        ttl_ms: Time-to-live em milissegundos
        signature: Assinatura HMAC (opcional)
        payload: Dados da mensagem
    """

    protocol_version: str = field(default=BEE_PROTOCOL_VERSION)
    msg_id: str = field(default_factory=lambda: str(uuid4()))
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_node_id: str = ""
    target_node_id: str | None = None
    msg_type: BeeMessageType = BeeMessageType.ERROR
    priority: int = 5
    ttl_ms: int = 30000
    signature: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Converte envelope para dicionário serializável."""
        return {
            "protocol_version": self.protocol_version,
            "msg_id": self.msg_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "msg_type": self.msg_type.value,
            "priority": self.priority,
            "ttl_ms": self.ttl_ms,
            "signature": self.signature,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeeEnvelope:
        """Cria envelope a partir de dicionário."""
        return cls(
            protocol_version=data.get("protocol_version", BEE_PROTOCOL_VERSION),
            msg_id=data["msg_id"],
            correlation_id=data.get("correlation_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source_node_id=data["source_node_id"],
            target_node_id=data.get("target_node_id"),
            msg_type=BeeMessageType(data["msg_type"]),
            priority=data.get("priority", 5),
            ttl_ms=data.get("ttl_ms", 30000),
            signature=data.get("signature"),
            payload=data.get("payload", {}),
        )

    def to_json(self) -> str:
        """Serializa envelope para JSON."""
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_json(cls, json_str: str) -> BeeEnvelope:
        """Deserializa envelope de JSON."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def as_signable_dict(self) -> dict[str, Any]:
        """Retorna dicionário para assinatura (exclui signature)."""
        data = self.to_dict()
        data.pop("signature", None)
        return data

    def is_expired(self) -> bool:
        """Verifica se envelope expirou baseado no TTL."""
        now = datetime.now(UTC)
        elapsed_ms = (now - self.timestamp).total_seconds() * 1000
        return elapsed_ms > self.ttl_ms

    def validate(self) -> list[str]:
        """Valida envelope e retorna lista de erros."""
        errors = []

        if not self.protocol_version.startswith("1."):
            errors.append(f"Versão incompatível: {self.protocol_version}")

        if not self.source_node_id:
            errors.append("source_node_id é obrigatório")

        if not self.msg_id:
            errors.append("msg_id é obrigatório")

        if self.priority < 1 or self.priority > 10:
            errors.append("priority deve estar entre 1 e 10")

        if self.ttl_ms <= 0:
            errors.append("ttl_ms deve ser > 0")

        return errors

    @classmethod
    def create_request(
        cls,
        source_node_id: str,
        target_node_id: str | None,
        msg_type: BeeMessageType,
        payload: dict[str, Any],
        correlation_id: str | None = None,
        priority: int = 5,
        ttl_ms: int = 30000,
    ) -> BeeEnvelope:
        """Cria envelope para mensagem de request."""
        return cls(
            protocol_version=BEE_PROTOCOL_VERSION,
            msg_id=str(uuid4()),
            correlation_id=correlation_id or str(uuid4()),
            timestamp=datetime.now(UTC),
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            msg_type=msg_type,
            priority=priority,
            ttl_ms=ttl_ms,
            payload=payload,
        )

    @classmethod
    def create_response(
        cls,
        source_node_id: str,
        target_node_id: str,
        msg_type: BeeMessageType,
        payload: dict[str, Any],
        correlation_id: str,
        priority: int = 5,
        ttl_ms: int = 30000,
    ) -> BeeEnvelope:
        """Cria envelope para mensagem de response."""
        return cls(
            protocol_version=BEE_PROTOCOL_VERSION,
            msg_id=str(uuid4()),
            correlation_id=correlation_id,
            timestamp=datetime.now(UTC),
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            msg_type=msg_type,
            priority=priority,
            ttl_ms=ttl_ms,
            payload=payload,
        )
