from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import websockets
from websockets.client import WebSocketClientProtocol

from .envelope import EXPEnvelope
from .security import EXPSecurity


class EXPWebSocketClient:
    def __init__(self, url: str, security: EXPSecurity, reconnect_interval: float = 2.0) -> None:
        self.url = url
        self.security = security
        self.reconnect_interval = reconnect_interval
        self._ws: WebSocketClientProtocol | None = None

    async def connect(self) -> None:
        self._ws = await websockets.connect(self.url, ping_interval=15, ping_timeout=15)

    async def ensure_connection(self) -> None:
        if self._ws is None or self._ws.closed:
            await self.connect()

    async def send(self, envelope: EXPEnvelope) -> None:
        await self.ensure_connection()
        envelope.signature = self.security.sign_payload(envelope.as_signable_dict())
        await self._ws.send(envelope.model_dump_json())

    async def receive_loop(self) -> AsyncIterator[EXPEnvelope]:
        while True:
            try:
                await self.ensure_connection()
                raw = await self._ws.recv()
                data = json.loads(raw)
                signature = data.get("signature")
                payload = {k: v for k, v in data.items() if k != "signature"}
                if not signature or not self.security.verify_payload(payload, signature):
                    continue
                yield EXPEnvelope.model_validate(data)
            except websockets.ConnectionClosed:
                await asyncio.sleep(self.reconnect_interval)
