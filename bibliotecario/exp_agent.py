from __future__ import annotations

import asyncio
import logging
import os

from core.cluster import HardwareBenchmark, LocalSearchEngine
from core.exp.client import EXPWebSocketClient
from core.exp.envelope import EXPEnvelope, EXPNode
from core.exp.security import EXPSecurity
from core.exp.types import EXPMessageType

from .search_service import SearchPipelineService

logger = logging.getLogger(__name__)


class BibliotecarioEXPAgent:
    def __init__(self, pipeline: SearchPipelineService) -> None:
        self.node_id = os.getenv("NODE_ID", "bib-01")
        self.role = os.getenv("ROLE", "bibliotecario")
        self.cluster_role = os.getenv("CLUSTER_ROLE", "bibliotecaria")
        self.juiz_url = os.getenv("JUIZ_URL", "ws://juiz:7700/exp")
        secret = os.getenv("EXP_SHARED_SECRET", "enxame-dev-secret")
        self.security = EXPSecurity(secret)
        self.client = EXPWebSocketClient(url=self.juiz_url, security=self.security)
        self.node = EXPNode(node_id=self.node_id, role=self.role, address=None)
        self.pipeline = pipeline
        docs_dir = os.getenv("BIB_DOCS_DIR", "/data/docs")
        zim_dir = os.getenv("BIB_ZIM_DIR", "/data/zim")
        self.search_engine = LocalSearchEngine(docs_dir=docs_dir, zim_dir=zim_dir)
        self.benchmark_profile = HardwareBenchmark().run()
        self.assigned_zim_files: list[str] = []

    async def _send_hello(self) -> None:
        hello = EXPEnvelope(
            source=self.node,
            type=EXPMessageType.HELLO,
            payload={
                "models": [os.getenv("BIB_MODEL", "gemma2:9b")],
                "cluster_role": self.cluster_role,
                "benchmark": self.benchmark_profile.as_dict(),
                "capabilities": [
                    "redis_cache",
                    "qdrant_search",
                    "local_file_search",
                    "zim_search",
                    "internet_search_last_resort",
                    "ptbr_translation",
                ],
            },
        )
        await self.client.send(hello)
        propose = EXPEnvelope(
            source=self.node,
            type=EXPMessageType.ELECTION_PROPOSE,
            payload={"node_id": self.node_id, "benchmark": self.benchmark_profile.as_dict()},
        )
        await self.client.send(propose)
        vote = EXPEnvelope(
            source=self.node,
            type=EXPMessageType.ELECTION_VOTE,
            payload={"candidate": self.node_id, "approve": True},
        )
        await self.client.send(vote)
        logger.info("HELLO + eleição enviados ao Juiz")

    async def _heartbeat_loop(self) -> None:
        while True:
            hb = EXPEnvelope(
                source=self.node,
                type=EXPMessageType.HEARTBEAT,
                payload={
                    "cluster_role": self.cluster_role,
                    "benchmark": self.benchmark_profile.as_dict(),
                    "capacity": {"max_concurrency": 1, "queue_max": 8},
                    "load": {"queue_size": 0, "utilization": 0.1},
                },
            )
            await self.client.send(hb)
            await asyncio.sleep(5)

    async def _handle_task_dispatch(self, envelope: EXPEnvelope) -> None:
        subtask = str(envelope.payload.get("subtask", "")).strip()
        if not subtask:
            return

        local_hit = self.search_engine.search(subtask, limit=4)
        if local_hit.found:
            response = EXPEnvelope(
                source=self.node,
                target=envelope.source,
                correlation_id=envelope.correlation_id,
                type=EXPMessageType.TASK_RESULT,
                payload={
                    "task_id": envelope.payload.get("task_id"),
                    "result": "\n".join(local_hit.snippets),
                    "metadata": {
                        "source": local_hit.source,
                        "sources": local_hit.sources,
                        "local_only": True,
                        "internet_used": False,
                    },
                },
            )
            await self.client.send(response)
            return

        allow_internet = bool(envelope.payload.get("allow_internet", self.cluster_role == "bibliotecaria"))
        result = await self.pipeline.search(subtask, allow_internet=allow_internet)
        response = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id,
            type=EXPMessageType.TASK_RESULT,
            payload={
                "task_id": envelope.payload.get("task_id"),
                "result": result.answer,
                "metadata": result.metadata,
            },
        )
        await self.client.send(response)
        logger.info("TASK_RESULT enviado (source=%s)", result.metadata.get("source"))

    async def _handle_query(self, envelope: EXPEnvelope) -> None:
        action = str(envelope.payload.get("action", "")).strip().lower()
        if action == "local_search":
            query = str(envelope.payload.get("query", "")).strip()
            hit = self.search_engine.search(query, limit=3)
            payload = {
                "action": "local_search",
                "found": hit.found,
                "source": hit.source,
                "snippets": hit.snippets,
                "sources": hit.sources,
                "cluster_role": self.cluster_role,
            }
        elif action == "zim_inventory":
            payload = {
                "action": "zim_inventory",
                "cluster_role": self.cluster_role,
                "zim_files": self.search_engine.list_zim_files(),
                "assigned_zim_files": self.assigned_zim_files,
            }
        else:
            payload = {
                "action": action or "status",
                "cluster_role": self.cluster_role,
                "benchmark": self.benchmark_profile.as_dict(),
            }

        response = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id,
            type=EXPMessageType.QUERY_RESULT,
            payload=payload,
        )
        await self.client.send(response)

    async def _handle_role_change(self, envelope: EXPEnvelope) -> None:
        target_node = str(envelope.payload.get("node_id", "")).strip()
        new_role = str(envelope.payload.get("new_role", "")).strip()
        accepted = bool(target_node == self.node_id and new_role)
        if accepted:
            self.cluster_role = new_role
            zim_files = envelope.payload.get("zim_files", [])
            if isinstance(zim_files, list):
                self.assigned_zim_files = [str(v) for v in zim_files]

        ack = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id,
            type=EXPMessageType.ROLE_ACK,
            payload={"accepted": accepted, "cluster_role": self.cluster_role},
        )
        await self.client.send(ack)

    async def run_forever(self) -> None:
        hb_task: asyncio.Task | None = None
        while True:
            try:
                await self.client.connect()
                await self._send_hello()
                hb_task = asyncio.create_task(self._heartbeat_loop())
                async for envelope in self.client.receive_loop():
                    if envelope.type == EXPMessageType.TASK_DISPATCH:
                        await self._handle_task_dispatch(envelope)
                    elif envelope.type == EXPMessageType.QUERY:
                        await self._handle_query(envelope)
                    elif envelope.type == EXPMessageType.ROLE_CHANGE:
                        await self._handle_role_change(envelope)
            except Exception as exc:  # pragma: no cover
                logger.warning("Conexão EXP interrompida: %s", exc)
                await asyncio.sleep(3)
            finally:
                if hb_task:
                    hb_task.cancel()
