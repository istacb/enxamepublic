from __future__ import annotations

import asyncio
import json
import os

import websockets

from core.exp.envelope import EXPEnvelope, EXPNode
from core.exp.security import EXPSecurity
from core.exp.types import EXPMessageType
from core.ollama.client import OllamaClient, OllamaGenerateRequest


async def main() -> None:
    node_id = os.getenv("NODE_ID", "ag-stub-01")
    role = os.getenv("ROLE", "dynamic")
    juiz_url = os.getenv("JUIZ_URL", "ws://localhost:7700/exp")
    secret = os.getenv("EXP_SHARED_SECRET", "enxame-dev-secret")
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    model = os.getenv("AGENT_MODEL", "gemma2:2b-it-qat")

    security = EXPSecurity(secret)
    ollama = OllamaClient(ollama_url)
    source = EXPNode(node_id=node_id, role=role, address=None)

    while True:
        try:
            async with websockets.connect(juiz_url, ping_interval=15, ping_timeout=15) as ws:
                hello = EXPEnvelope(source=source, type=EXPMessageType.HELLO, payload={"models": [model]})
                hello.signature = security.sign_payload(hello.as_signable_dict())
                await ws.send(hello.model_dump_json())

                async def heartbeat_loop() -> None:
                    while True:
                        hb = EXPEnvelope(source=source, type=EXPMessageType.HEARTBEAT, payload={})
                        hb.signature = security.sign_payload(hb.as_signable_dict())
                        await ws.send(hb.model_dump_json())
                        await asyncio.sleep(5)

                hb_task = asyncio.create_task(heartbeat_loop())
                try:
                    async for raw in ws:
                        data = json.loads(raw)
                        signature = data.get("signature")
                        signable = {k: v for k, v in data.items() if k != "signature"}
                        if not signature or not security.verify_payload(signable, signature):
                            continue
                        msg = EXPEnvelope.model_validate(data)
                        if msg.type != EXPMessageType.TASK_DISPATCH:
                            continue

                        subtask = str(msg.payload.get("subtask", ""))
                        answer = await ollama.generate(
                            OllamaGenerateRequest(
                                model=model,
                                prompt=f"Resolva em português brasileiro com objetividade:\n{subtask}",
                                temperature=0.4,
                                num_ctx=2048,
                            )
                        )
                        result = EXPEnvelope(
                            source=source,
                            target=msg.source,
                            correlation_id=msg.correlation_id,
                            type=EXPMessageType.TASK_RESULT,
                            payload={"task_id": msg.payload.get("task_id"), "result": answer},
                        )
                        result.signature = security.sign_payload(result.as_signable_dict())
                        await ws.send(result.model_dump_json())
                finally:
                    hb_task.cancel()
        except Exception:
            await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
