from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone


class EXPAuthError(Exception):
    """Erro de autenticação/assinatura EXP."""


@dataclass(slots=True)
class EXPSecurity:
    shared_secret: str
    allowed_skew_seconds: int = 60

    def _canonical_json(self, payload: dict) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sign_payload(self, payload: dict) -> str:
        raw = self._canonical_json(payload)
        digest = hmac.new(self.shared_secret.encode("utf-8"), raw, hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    def verify_payload(self, payload: dict, signature: str) -> bool:
        expected = self.sign_payload(payload)
        return hmac.compare_digest(expected, signature)

    def sign_http_message(self, body: bytes, timestamp: str) -> str:
        msg = timestamp.encode("utf-8") + b"." + body
        digest = hmac.new(self.shared_secret.encode("utf-8"), msg, hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    def verify_http_message(self, body: bytes, timestamp: str, signature: str) -> None:
        try:
            ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise EXPAuthError("Timestamp inválido") from exc

        now = datetime.now(timezone.utc)
        if abs((now - ts).total_seconds()) > self.allowed_skew_seconds:
            raise EXPAuthError("Timestamp fora da janela permitida")

        expected = self.sign_http_message(body, timestamp)
        if not hmac.compare_digest(expected, signature):
            raise EXPAuthError("Assinatura HMAC inválida")
