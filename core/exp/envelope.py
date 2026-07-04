from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from .types import EXP_VERSION, EXPMessageType


class EXPNode(BaseModel):
    node_id: str
    role: str
    address: str | None = None


class EXPEnvelope(BaseModel):
    exp_version: str = Field(default=EXP_VERSION)
    msg_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: EXPNode
    target: EXPNode | None = None
    type: EXPMessageType
    priority: int = 5
    ttl_ms: int = 30000
    signature: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: int) -> int:
        if not 1 <= value <= 10:
            raise ValueError("priority deve estar entre 1 e 10")
        return value

    @field_validator("ttl_ms")
    @classmethod
    def validate_ttl(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("ttl_ms deve ser > 0")
        return value

    @field_validator("exp_version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if value != EXP_VERSION:
            raise ValueError(f"Versão EXP incompatível: {value}")
        return value

    def as_signable_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data.pop("signature", None)
        return data
