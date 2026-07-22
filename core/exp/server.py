from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import WebSocket

from .envelope import EXPEnvelope
from .security import EXPSecurity

Handler = Callable[[EXPEnvelope, WebSocket], Awaitable[None]]


class EXPServerAdapter:
    """Adaptador de mensagens EXP para endpoints WS do FastAPI."""

    def __init__(self, security: EXPSecurity):
        self.security = security

    async def serve_socket(self, websocket: WebSocket, handler: Handler) -> None:
        await websocket.accept()
        try:
            while True:
                raw = await websocket.receive_text()
                data: dict[str, Any] = json.loads(raw)
                signature = data.get("signature")
                signable = {k: v for k, v in data.items() if k != "signature"}
                if not signature or not self.security.verify_payload(signable, signature):
                    await websocket.send_json({"type": "ERROR", "payload": {"code": "BAD_SIGNATURE"}})
                    continue
                envelope = EXPEnvelope.model_validate(data)
                await handler(envelope, websocket)
        finally:
            await websocket.close()

    async def send(self, websocket: WebSocket, envelope: EXPEnvelope) -> None:
        envelope.signature = self.security.sign_payload(envelope.as_signable_dict())
        await websocket.send_text(envelope.model_dump_json())
