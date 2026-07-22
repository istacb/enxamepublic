from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from uuid import uuid4

import websockets

from core.exp.envelope import EXPEnvelope, EXPNode
from core.exp.security import EXPSecurity
from core.exp.types import EXPMessageType
from core.cluster import HardwareBenchmark, LocalSearchEngine
from core.ollama.client import OllamaClient, OllamaGenerateRequest

from .metrics import MetricsCollector
from .plugin_manager import PluginManager
from .worker_pool import WorkItem, WorkerPool, now_utc

logger = logging.getLogger(__name__)


class DynamicAgentService:
    """Agente polimórfico com hot-load de plugins e pool interno de workers."""

    def __init__(self) -> None:
        self.node_id = os.getenv("NODE_ID", f"ag-dyn-{uuid4().hex[:8]}")
        self.role = os.getenv("ROLE", "dynamic")
        self.cluster_role = os.getenv("CLUSTER_ROLE", "agente")
        self.juiz_url = os.getenv("JUIZ_URL", "ws://localhost:7700/exp")
        self.secret = os.getenv("EXP_SHARED_SECRET", "enxame-dev-secret")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.model = os.getenv("AGENT_MODEL", "gemma2:2b-it-qat")
        self.heartbeat_interval = float(os.getenv("HEARTBEAT_INTERVAL", "5"))
        self.reconnect_interval = float(os.getenv("RECONNECT_INTERVAL", "2"))
        self.task_timeout = float(os.getenv("TASK_TIMEOUT", "90"))
        self.plugin_refresh_interval = float(os.getenv("PLUGIN_REFRESH_INTERVAL", "2"))

        max_workers = int(os.getenv("WORKER_POOL_SIZE", "4"))
        max_queue = int(os.getenv("WORKER_MAX_QUEUE", "128"))

        self.security = EXPSecurity(self.secret)
        self.ollama = OllamaClient(self.ollama_url)
        self.node = EXPNode(node_id=self.node_id, role=self.role, address=None)

        self.plugin_manager = PluginManager()
        self.metrics = MetricsCollector()
        self.pool = WorkerPool(workers=max_workers, max_queue=max_queue)

        docs_dir = os.getenv("NODE_DOCS_DIR", os.getenv("BIB_DOCS_DIR", "/data/docs"))
        zim_dir = os.getenv("NODE_ZIM_DIR", os.getenv("BIB_ZIM_DIR", "/data/zim"))
        self.search_engine = LocalSearchEngine(docs_dir=docs_dir, zim_dir=zim_dir)
        self.benchmark_profile = HardwareBenchmark().run()
        self.assigned_zim_files: list[str] = []

        self._task_specialty_override: dict[str, str] = {}
        self._running = False

    async def run_forever(self) -> None:
        self.plugin_manager.load_all()
        await self.pool.start(self._execute_item)
        self._running = True

        while self._running:
            try:
                async with websockets.connect(self.juiz_url, ping_interval=15, ping_timeout=15) as ws:
                    await self._send_hello(ws)
                    await self._send_election_messages(ws)
                    hb_task = asyncio.create_task(self._heartbeat_loop(ws))
                    hotload_task = asyncio.create_task(self._hotload_loop())
                    try:
                        async for raw in ws:
                            envelope = self._decode_envelope(raw)
                            if envelope is None:
                                continue
                            await self._handle_message(ws, envelope)
                    finally:
                        hb_task.cancel()
                        hotload_task.cancel()
                        await asyncio.gather(hb_task, hotload_task, return_exceptions=True)
            except Exception as exc:  # pragma: no cover
                logger.warning("Falha de conexão com Juiz (%s): %s", self.juiz_url, exc)
                await asyncio.sleep(self.reconnect_interval)

    async def stop(self) -> None:
        self._running = False
        await self.pool.stop()

    async def _send(self, ws, envelope: EXPEnvelope) -> None:
        envelope.signature = self.security.sign_payload(envelope.as_signable_dict())
        await ws.send(envelope.model_dump_json())

    async def _send_hello(self, ws) -> None:
        payload = {
            "models": [self.model],
            "capabilities": ["polymorphic", "hotload", "metrics", "worker_pool", "local_search", "zim_local"],
            "specialties": [m.name for m in self.plugin_manager.list_plugins()],
            "cluster_role": self.cluster_role,
            "benchmark": self.benchmark_profile.as_dict(),
            "capacity": {
                "max_concurrency": self.pool.workers,
                "queue_max": self.pool.queue.maxsize,
            },
            "metrics": self.metrics.snapshot(),
        }
        hello = EXPEnvelope(source=self.node, type=EXPMessageType.HELLO, payload=payload)
        await self._send(ws, hello)

    async def _send_election_messages(self, ws) -> None:
        propose = EXPEnvelope(
            source=self.node,
            type=EXPMessageType.ELECTION_PROPOSE,
            payload={"node_id": self.node_id, "benchmark": self.benchmark_profile.as_dict()},
        )
        await self._send(ws, propose)

        vote = EXPEnvelope(
            source=self.node,
            type=EXPMessageType.ELECTION_VOTE,
            payload={"candidate": self.node_id, "approve": True},
        )
        await self._send(ws, vote)

    async def _heartbeat_loop(self, ws) -> None:
        while True:
            hb = EXPEnvelope(
                source=self.node,
                type=EXPMessageType.HEARTBEAT,
                payload=self._status_payload(),
            )
            await self._send(ws, hb)
            await asyncio.sleep(self.heartbeat_interval)

    async def _hotload_loop(self) -> None:
        while True:
            changed = self.plugin_manager.refresh_changed()
            if changed:
                logger.info("Plugins recarregados automaticamente: %s", [p.name for p in changed])
            await asyncio.sleep(self.plugin_refresh_interval)

    def _decode_envelope(self, raw: str) -> EXPEnvelope | None:
        try:
            data = json.loads(raw)
            signature = data.get("signature")
            signable = {k: v for k, v in data.items() if k != "signature"}
            if not signature or not self.security.verify_payload(signable, signature):
                return None
            return EXPEnvelope.model_validate(data)
        except Exception:
            return None

    async def _handle_message(self, ws, envelope: EXPEnvelope) -> None:
        if envelope.type == EXPMessageType.TASK_DISPATCH:
            await self._handle_task_dispatch(ws, envelope)
            return
        if envelope.type == EXPMessageType.ROLE_ASSIGN:
            await self._handle_role_assign(ws, envelope)
            return
        if envelope.type == EXPMessageType.PLUGIN_LOAD:
            await self._handle_plugin_control(ws, envelope)
            return
        if envelope.type == EXPMessageType.ROLE_CHANGE:
            await self._handle_role_change(ws, envelope)
            return
        if envelope.type == EXPMessageType.QUERY:
            await self._handle_query(ws, envelope)
            return

    async def _handle_role_assign(self, ws, envelope: EXPEnvelope) -> None:
        specialty = str(envelope.payload.get("specialty", "")).strip().lower()
        task_id = str(envelope.payload.get("task_id", "")).strip()
        accepted = bool(specialty and self.plugin_manager.get(specialty))
        if accepted and task_id:
            self._task_specialty_override[task_id] = specialty

        ack = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id or envelope.msg_id,
            type=EXPMessageType.ROLE_ACK,
            payload={
                "accepted": accepted,
                "specialty": specialty,
                "task_id": task_id,
                "available_specialties": [m.name for m in self.plugin_manager.list_plugins()],
            },
        )
        await self._send(ws, ack)

    async def _handle_plugin_control(self, ws, envelope: EXPEnvelope) -> None:
        action = str(envelope.payload.get("action", "list")).strip().lower()
        plugin_name = str(envelope.payload.get("plugin", "")).strip().lower()

        status = "ok"
        detail: dict = {}

        if action == "load" and plugin_name:
            meta = self.plugin_manager.load_plugin(plugin_name)
            if not meta:
                status = "error"
                detail = {"message": f"Plugin {plugin_name} inválido"}
            else:
                detail = {"plugin": meta.name, "version": meta.version}
        elif action == "unload" and plugin_name:
            removed = self.plugin_manager.unload_plugin(plugin_name)
            detail = {"plugin": plugin_name, "removed": removed}
        elif action == "reload" and plugin_name:
            meta = self.plugin_manager.reload_plugin(plugin_name)
            if not meta:
                status = "error"
                detail = {"message": f"Plugin {plugin_name} não recarregado"}
            else:
                detail = {"plugin": meta.name, "version": meta.version}
        elif action == "refresh":
            changed = self.plugin_manager.refresh_changed()
            detail = {"changed": [p.name for p in changed]}
        else:
            detail = {
                "plugins": [
                    {
                        "name": p.name,
                        "version": p.version,
                        "description": p.description,
                    }
                    for p in self.plugin_manager.list_plugins()
                ]
            }

        response = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id or envelope.msg_id,
            type=EXPMessageType.QUERY_RESULT,
            payload={"status": status, "action": action, **detail},
        )
        await self._send(ws, response)

    async def _handle_role_change(self, ws, envelope: EXPEnvelope) -> None:
        target_node = str(envelope.payload.get("node_id", "")).strip()
        new_role = str(envelope.payload.get("new_role", "")).strip()
        if target_node == self.node_id and new_role:
            self.cluster_role = new_role
            zim_files = envelope.payload.get("zim_files", [])
            if isinstance(zim_files, list):
                self.assigned_zim_files = [str(v) for v in zim_files]

        ack = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id or envelope.msg_id,
            type=EXPMessageType.ROLE_ACK,
            payload={"accepted": target_node == self.node_id, "cluster_role": self.cluster_role},
        )
        await self._send(ws, ack)

    async def _handle_query(self, ws, envelope: EXPEnvelope) -> None:
        action = str(envelope.payload.get("action", "status")).strip().lower()
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
            payload = self._status_payload()

        response = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id or envelope.msg_id,
            type=EXPMessageType.QUERY_RESULT,
            payload=payload,
        )
        await self._send(ws, response)

    async def _handle_task_dispatch(self, ws, envelope: EXPEnvelope) -> None:
        payload = envelope.payload
        task_id = str(payload.get("task_id", "")).strip() or f"t-{uuid4().hex[:10]}"
        subtask = str(payload.get("subtask", "")).strip()
        explicit_specialty = str(payload.get("specialty", "")).strip().lower() or None
        context = str(payload.get("context", "")).strip() or None

        specialty = explicit_specialty or self._task_specialty_override.get(task_id)

        item = WorkItem(
            correlation_id=envelope.correlation_id or envelope.msg_id,
            task_id=task_id,
            subtask=subtask,
            specialty=specialty,
            context=context,
            source_node=envelope.source.model_dump(mode="json"),
            enqueued_at=now_utc(),
        )

        try:
            fut = await self.pool.submit(item)
        except asyncio.QueueFull:
            retry_msg = EXPEnvelope(
                source=self.node,
                target=envelope.source,
                correlation_id=item.correlation_id,
                type=EXPMessageType.TASK_RETRY,
                payload={
                    "task_id": task_id,
                    "reason": "overloaded",
                    "load": self.pool.load_snapshot(),
                },
            )
            await self._send(ws, retry_msg)
            return

        asyncio.create_task(self._finalize_task(ws, envelope.source, item, fut))

    async def _finalize_task(self, ws, target: EXPNode, item: WorkItem, fut: asyncio.Future[str]) -> None:
        try:
            answer = await asyncio.wait_for(fut, timeout=self.task_timeout)
            envelope = EXPEnvelope(
                source=self.node,
                target=target,
                correlation_id=item.correlation_id,
                type=EXPMessageType.TASK_RESULT,
                payload={
                    "task_id": item.task_id,
                    "result": answer,
                    "specialty": item.specialty,
                    "metrics": self.metrics.snapshot(),
                },
            )
            await self._send(ws, envelope)
        except TimeoutError:
            self.metrics.track_failure()
            retry_msg = EXPEnvelope(
                source=self.node,
                target=target,
                correlation_id=item.correlation_id,
                type=EXPMessageType.TASK_RETRY,
                payload={"task_id": item.task_id, "reason": "timeout"},
            )
            await self._send(ws, retry_msg)
        except Exception as exc:  # pragma: no cover
            self.metrics.track_failure()
            error_msg = EXPEnvelope(
                source=self.node,
                target=target,
                correlation_id=item.correlation_id,
                type=EXPMessageType.ERROR,
                payload={"task_id": item.task_id, "message": str(exc)},
            )
            await self._send(ws, error_msg)
        finally:
            self._task_specialty_override.pop(item.task_id, None)

    async def _execute_item(self, item: WorkItem) -> str:
        local_hit = self.search_engine.search(item.subtask, limit=3)
        if local_hit.found:
            self.metrics.track_success()
            return "\n".join(local_hit.snippets)

        plugin = self.plugin_manager.get(item.specialty or "") if item.specialty else None
        if plugin is None:
            plugin = self.plugin_manager.best_for(item.subtask)

        selected_specialty = plugin.name
        item.specialty = selected_specialty

        prompt = plugin.build_prompt(subtask=item.subtask, context=item.context)
        started = time.perf_counter()
        try:
            answer = await self.ollama.generate(
                OllamaGenerateRequest(
                    model=self.model,
                    prompt=prompt,
                    temperature=0.35,
                    num_ctx=4096,
                )
            )
            self.metrics.track_success()
            return answer
        finally:
            latency_ms = (time.perf_counter() - started) * 1000
            self.metrics.track_latency(latency_ms)

    def _status_payload(self) -> dict:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": self.model,
            "cluster_role": self.cluster_role,
            "benchmark": self.benchmark_profile.as_dict(),
            "assigned_zim_files": self.assigned_zim_files,
            "specialties": [m.name for m in self.plugin_manager.list_plugins()],
            "capacity": {
                "max_concurrency": self.pool.workers,
                "queue_max": self.pool.queue.maxsize,
            },
            "load": self.pool.load_snapshot(),
            "metrics": self.metrics.snapshot(),
        }
