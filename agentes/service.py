from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import websockets
try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None  # type: ignore

from core.cluster.benchmark import HardwareBenchmark
from core.cluster.local_search import LocalSearchEngine
from core.cluster.rag import LocalRagIndex
from core.discovery.beacon import Beacon
from core.discovery.mdns import MdnsDiscovery
from core.exp.envelope import EXPEnvelope, EXPNode
from core.exp.http import build_auth_headers
from core.exp.security import EXPSecurity
from core.exp.types import EXPMessageType
from core.ollama.client import OllamaClient, OllamaGenerateRequest
from guardian import GuardianPatrol

from .metrics import MetricsCollector
from .plugin_manager import PluginManager
from .worker_pool import WorkerPool, WorkItem, now_utc

logger = logging.getLogger(__name__)

DEFAULT_DONATION = {
    'enabled': True,
    'max_cpu_pct': 70,
    'min_free_ram_gb': 1.5,
    'max_concurrent': 1,
    'run_when': 'idle',
    'idle_after_s': 120,
    'pause_on_battery': True,
    'allowed_models': [],
    'schedule': '',
}


@dataclass(slots=True)
class DonationPolicy:
    enabled: bool = True
    max_cpu_pct: float = 70.0
    min_free_ram_gb: float = 1.5
    max_concurrent: int = 1
    run_when: str = 'idle'
    idle_after_s: int = 120
    pause_on_battery: bool = True
    allowed_models: list[str] = field(default_factory=list)
    schedule: str = ''


def _load_donation_policy() -> DonationPolicy:
    path = Path(os.getenv('ENXAME_CONFIG_DIR', str(Path.home() / 'enxame'))) / 'node.toml'
    data = {}
    if path.exists() and tomllib is not None:
        try:
            with path.open('rb') as f:
                data = tomllib.load(f).get('donation', {})
        except Exception:
            data = {}
    d = dict(DEFAULT_DONATION)
    d.update(data)
    return DonationPolicy(**d)


class DynamicAgentService:
    """Agente polimórfico com hot-load de plugins e pool interno de workers."""

    def __init__(self) -> None:
        self.node_id = os.getenv('NODE_ID', f'ag-dyn-{uuid4().hex[:8]}')
        self.role = os.getenv('ROLE', 'dynamic')
        self.cluster_role = os.getenv('CLUSTER_ROLE', 'agente')
        self.juiz_url = os.getenv('JUIZ_URL', 'ws://localhost:7700/exp')
        self.juiz_http_url = os.getenv('JUIZ_HTTP_URL', 'http://localhost:7700')
        self.secret = os.getenv('EXP_SHARED_SECRET', 'enxame-dev-secret')
        self.ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        self.model = os.getenv('AGENT_MODEL', None)  # None = seleciona o melhor instalado
        self.heartbeat_interval = float(os.getenv('HEARTBEAT_INTERVAL', '5'))
        self.reconnect_interval = float(os.getenv('RECONNECT_INTERVAL', '2'))
        self.task_timeout = float(os.getenv('TASK_TIMEOUT', '90'))
        self.plugin_refresh_interval = float(os.getenv('PLUGIN_REFRESH_INTERVAL', '2'))
        self.guardian_patrol_interval = float(os.getenv('GUARDIAN_PATROL_INTERVAL', '15'))

        self.security = EXPSecurity(self.secret)
        self.ollama = OllamaClient(self.ollama_url)
        self.node = EXPNode(node_id=self.node_id, role=self.role, address=None)

        self.plugin_manager = PluginManager()
        self.metrics = MetricsCollector()
        self.pool = WorkerPool(workers=1, max_queue=4)  # 1 slot por padrão (poltrona de idoso)

        docs_dir = os.getenv('NODE_DOCS_DIR', os.getenv('BIB_DOCS_DIR', str(Path.home() / 'enxame' / 'docs')))
        zim_dir = os.getenv('NODE_ZIM_DIR', os.getenv('BIB_ZIM_DIR', str(Path.home() / 'enxame' / 'zim')))
        self.search_engine = LocalSearchEngine(docs_dir=docs_dir, zim_dir=zim_dir)
        # RAG local: este nó indexa seus próprios arquivos (não-sistema).
        self.rag = LocalRagIndex(
            db_path=str(Path.home() / 'enxame' / f'rag_{self.node_id}.db'),
            roots=[docs_dir],
        )
        self.benchmark_profile = HardwareBenchmark().run()
        self.assigned_zim_files: list[str] = []

        # Política de doação (o nó se autoregula; o Juiz não pode sobrescrever).
        self.donation = _load_donation_policy()
        self._paused = False

        self._task_specialty_override: dict[str, str] = {}
        self._running = False
        self._cancel_flags: dict[str, bool] = {}

        # Beacon de descoberta LAN.
        http_port = int(os.getenv('ENXAME_HTTP_PORT', '8000'))
        ws_port = int(os.getenv('ENXAME_WS_PORT', '8000'))
        self._beacon = Beacon(
            node_id=self.node_id,
            ip='0.0.0.0',
            http_port=http_port,
            ws_port=ws_port,
            role=self.cluster_role,
            score=self.benchmark_profile.overall_score,
            models=[self.model] if self.model else [],
            on_peer=self._on_peer,
        )
        # mDNS real via zeroconf (opcional; silencioso se não instalado).
        self._mdns = MdnsDiscovery(
            node_id=self.node_id,
            ip='0.0.0.0',
            port=ws_port,
            role=self.cluster_role,
            score=self.benchmark_profile.overall_score,
            models=[self.model] if self.model else [],
            on_peer=self._on_peer_mdns,
        )
        self._known_peers: dict[str, dict] = {}

        # Ronda do Guardião.
        self.guardian_patrol = GuardianPatrol(
            node_id=self.node_id,
            interval_seconds=self.guardian_patrol_interval,
            remote_reporter=self._report_guardian_alert,
        )
        self._guardian_task: asyncio.Task | None = None

    async def _report_guardian_alert(self, alert: dict) -> None:
        body = json.dumps(alert, ensure_ascii=False).encode('utf-8')
        headers = build_auth_headers(self.security, body)
        headers['content-type'] = 'application/json'
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f'{self.juiz_http_url}/api/v1/guardian/report', content=body, headers=headers)

    async def run_forever(self) -> None:
        self.plugin_manager.load_all()
        await self.pool.start(self._execute_item)
        self._running = True
        self._guardian_task = asyncio.create_task(self.guardian_patrol.run_forever())

        # Indexa arquivos locais para RAG (não-sistema).
        try:
            n = self.rag.index_files()
            if n:
                logger.info('RAG local indexou %d arquivo(s)', n)
        except Exception as exc:  # pragma: no cover
            logger.warning('Falha ao indexar RAG local: %s', exc)

        # Seleciona o melhor modelo instalado ou baixa o recomendado para o hardware.
        if not self.model:
            try:
                ram_gb = float(self.benchmark_profile.ram_total_gb)
                # vram não é exposto pelo benchmark simples; assume 0 (CPU).
                # Se o usuário tiver GPU, pode sobrescrever via AGENT_MODEL ou node.toml.
                chosen = await self.ollama.ensure_model(ram_gb, 0.0)
                if chosen:
                    self.model = chosen
                    logger.info('Modelo selecionado/baixado: %s', chosen)
            except Exception as exc:  # pragma: no cover
                logger.warning('Não foi possível selecionar/baixar modelo: %s', exc)

        self._beacon.start()
        self._mdns.start()
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
                logger.warning('Falha de conexão com Juiz (%s): %s', self.juiz_url, exc)
                await asyncio.sleep(self.reconnect_interval)

    async def stop(self) -> None:
        self._running = False
        self.guardian_patrol.stop()
        if self._guardian_task is not None:
            self._guardian_task.cancel()
        self._beacon.stop()
        self._mdns.stop()
        self.rag.close()
        await self.pool.stop()

    async def _send(self, ws, envelope: EXPEnvelope) -> None:
        envelope.signature = self.security.sign_payload(envelope.as_signable_dict())
        await ws.send(envelope.model_dump_json())

    async def _send_hello(self, ws) -> None:
        # Política de doação: o Juiz não pode sobrescrever o gate local.
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            free_ram_gb = mem.available / (1024 ** 3)
        except Exception:
            cpu = 0.0
            free_ram_gb = 999.0

        gate_ok = self._gate_ok(cpu, free_ram_gb)
        payload = {
            'models': [self.model] if self.model else [],
            'capabilities': [
                'polymorphic', 'hotload', 'metrics', 'worker_pool', 'local_search',
                'zim_local', 'rag_local', 'discovery',
            ],
            'specialties': [m.name for m in self.plugin_manager.list_plugins()],
            'cluster_role': self.cluster_role,
            'benchmark': self.benchmark_profile.as_dict(),
            'capacity': {
                'max_concurrency': self.pool.workers,
                'queue_max': self.pool.queue.maxsize,
            },
            'metrics': self.metrics.snapshot(),
            'load': {
                'queue_size': self.pool.queue.qsize(),
                'utilization': self.pool.load_snapshot()['utilization'],
                'cpu_pct': cpu,
                'free_ram_gb': round(free_ram_gb, 2),
                'est_tps': self.metrics.est_tps(),
                'recent_fail_rate': self.metrics.recent_fail_rate(),
            },
            'donation': {
                'enabled': self.donation.enabled,
                'max_cpu_pct': self.donation.max_cpu_pct,
                'min_free_ram_gb': self.donation.min_free_ram_gb,
                'max_concurrent': self.donation.max_concurrent,
                'run_when': self.donation.run_when,
                'pause_on_battery': self.donation.pause_on_battery,
            },
            'paused': self._paused,
            'ready': gate_ok and not self._paused,
        }
        hello = EXPEnvelope(source=self.node, type=EXPMessageType.HELLO, payload=payload)
        await self._send(ws, hello)

    async def _send_election_messages(self, ws) -> None:
        propose = EXPEnvelope(
            source=self.node,
            type=EXPMessageType.ELECTION_PROPOSE,
            payload={'node_id': self.node_id, 'benchmark': self.benchmark_profile.as_dict()},
        )
        await self._send(ws, propose)

        vote = EXPEnvelope(
            source=self.node,
            type=EXPMessageType.ELECTION_VOTE,
            payload={'candidate': self.node_id, 'approve': True},
        )
        await self._send(ws, vote)

    def _gate_ok(self, cpu_pct: float, free_ram_gb: float) -> bool:
        """Gate de doação local: o nó se autoregula, o Juiz não pode sobrescrever."""
        if not self.donation.enabled or self._paused:
            return False
        if cpu_pct > self.donation.max_cpu_pct:
            return False
        if free_ram_gb < self.donation.min_free_ram_gb:
            return False
        if self.donation.pause_on_battery:
            try:
                import psutil

                bat = psutil.sensors_battery()
                if bat is not None and not bat.power_plugged:
                    return False
            except Exception:
                pass
        return True

    def _on_peer(self, peer) -> None:
        self._known_peers[peer.node_id] = {
            'ip': peer.ip,
            'http_port': peer.http_port,
            'ws_port': peer.ws_port,
            'role': peer.role,
            'score': peer.score,
            'models': peer.models,
            'last_seen': peer.last_seen,
        }

    def _on_peer_mdns(self, peer) -> None:
        self._known_peers[peer.node_id] = {
            'ip': peer.ip,
            'http_port': peer.port,
            'ws_port': peer.port,
            'role': peer.role,
            'score': peer.score,
            'models': peer.models,
            'last_seen': peer.last_seen if hasattr(peer, 'last_seen') else 0,
            'source': 'mdns',
        }

    async def _heartbeat_loop(self, ws) -> None:
        while True:
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=0.1)
                mem = psutil.virtual_memory()
                free_ram_gb = mem.available / (1024 ** 3)
            except Exception:
                cpu = 0.0
                free_ram_gb = 999.0

            ready = self._gate_ok(cpu, free_ram_gb)
            hb = EXPEnvelope(
                source=self.node,
                type=EXPMessageType.HEARTBEAT,
                payload=self._status_payload(cpu, free_ram_gb, ready),
            )
            await self._send(ws, hb)
            await asyncio.sleep(self.heartbeat_interval)

    async def _hotload_loop(self) -> None:
        while True:
            changed = self.plugin_manager.refresh_changed()
            if changed:
                logger.info('Plugins recarregados automaticamente: %s', [p.name for p in changed])
            await asyncio.sleep(self.plugin_refresh_interval)

    def _decode_envelope(self, raw: str) -> EXPEnvelope | None:
        try:
            data = json.loads(raw)
            signature = data.get('signature')
            signable = {k: v for k, v in data.items() if k != 'signature'}
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
        if envelope.type == EXPMessageType.TASK_CANCEL:
            await self._handle_task_cancel(envelope)
            return

    async def _handle_role_assign(self, ws, envelope: EXPEnvelope) -> None:
        specialty = str(envelope.payload.get('specialty', '')).strip().lower()
        task_id = str(envelope.payload.get('task_id', '')).strip()
        accepted = bool(specialty and self.plugin_manager.get(specialty))
        if accepted and task_id:
            self._task_specialty_override[task_id] = specialty

        ack = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id or envelope.msg_id,
            type=EXPMessageType.ROLE_ACK,
            payload={
                'accepted': accepted,
                'specialty': specialty,
                'task_id': task_id,
                'available_specialties': [m.name for m in self.plugin_manager.list_plugins()],
            },
        )
        await self._send(ws, ack)

    async def _handle_plugin_control(self, ws, envelope: EXPEnvelope) -> None:
        action = str(envelope.payload.get('action', 'list')).strip().lower()
        plugin_name = str(envelope.payload.get('plugin', '')).strip().lower()

        status = 'ok'
        detail: dict = {}

        if action == 'load' and plugin_name:
            meta = self.plugin_manager.load_plugin(plugin_name)
            if not meta:
                status = 'error'
                detail = {'message': f'Plugin {plugin_name} inválido'}
            else:
                detail = {'plugin': meta.name, 'version': meta.version}
        elif action == 'unload' and plugin_name:
            removed = self.plugin_manager.unload_plugin(plugin_name)
            detail = {'plugin': plugin_name, 'removed': removed}
        elif action == 'reload' and plugin_name:
            meta = self.plugin_manager.reload_plugin(plugin_name)
            if not meta:
                status = 'error'
                detail = {'message': f'Plugin {plugin_name} não recarregado'}
            else:
                detail = {'plugin': meta.name, 'version': meta.version}
        elif action == 'refresh':
            changed = self.plugin_manager.refresh_changed()
            detail = {'changed': [p.name for p in changed]}
        else:
            detail = {
                'plugins': [
                    {
                        'name': p.name,
                        'version': p.version,
                        'description': p.description,
                    }
                    for p in self.plugin_manager.list_plugins()
                ]
            }

        response = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id or envelope.msg_id,
            type=EXPMessageType.QUERY_RESULT,
            payload={'status': status, 'action': action, **detail},
        )
        await self._send(ws, response)

    async def _handle_role_change(self, ws, envelope: EXPEnvelope) -> None:
        target_node = str(envelope.payload.get('node_id', '')).strip()
        new_role = str(envelope.payload.get('new_role', '')).strip()
        if target_node == self.node_id and new_role:
            self.cluster_role = new_role
            zim_files = envelope.payload.get('zim_files', [])
            if isinstance(zim_files, list):
                self.assigned_zim_files = [str(v) for v in zim_files]

        ack = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id or envelope.msg_id,
            type=EXPMessageType.ROLE_ACK,
            payload={'accepted': target_node == self.node_id, 'cluster_role': self.cluster_role},
        )
        await self._send(ws, ack)

    async def _handle_query(self, ws, envelope: EXPEnvelope) -> None:
        action = str(envelope.payload.get('action', 'status')).strip().lower()
        if action == 'local_search':
            query = str(envelope.payload.get('query', '')).strip()
            hit = self.search_engine.search(query, limit=3)
            payload = {
                'action': 'local_search',
                'found': hit.found,
                'source': hit.source,
                'snippets': hit.snippets,
                'sources': hit.sources,
                'cluster_role': self.cluster_role,
            }
        elif action == 'zim_inventory':
            payload = {
                'action': 'zim_inventory',
                'cluster_role': self.cluster_role,
                'zim_files': self.search_engine.list_zim_files(),
                'assigned_zim_files': self.assigned_zim_files,
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
        task_id = str(payload.get('task_id', '')).strip() or f't-{uuid4().hex[:10]}'
        subtask = str(payload.get('subtask', '')).strip()
        explicit_specialty = str(payload.get('specialty', '')).strip().lower() or None
        context = str(payload.get('context', '')).strip() or None

        # Gate de doação: se não estiver apto, NACK para o Juiz re-filar.
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            free_ram_gb = mem.available / (1024 ** 3)
        except Exception:
            # Sem psutil: não bloquear por falta de métrica.
            cpu = 0.0
            free_ram_gb = 999.0

        if not self._gate_ok(cpu, free_ram_gb):
            await self._send(
                ws,
                EXPEnvelope(
                    source=self.node,
                    target=envelope.source,
                    correlation_id=envelope.correlation_id or envelope.msg_id,
                    type=EXPMessageType.TASK_NACK,
                    payload={
                        'task_id': task_id,
                        'reason': 'overloaded',
                        'load': self.pool.load_snapshot(),
                    },
                ),
            )
            return

        # Seleciona o melhor modelo instalado neste nó (não depende do Juiz).
        model = self.model or await self._select_model()
        if not model:
            await self._send(
                ws,
                EXPEnvelope(
                    source=self.node,
                    target=envelope.source,
                    correlation_id=envelope.correlation_id or envelope.msg_id,
                    type=EXPMessageType.TASK_NACK,
                    payload={'task_id': task_id, 'reason': 'model_missing'},
                ),
            )
            return

        specialty = explicit_specialty or self._task_specialty_override.get(task_id)
        self._cancel_flags[task_id] = False

        item = WorkItem(
            correlation_id=envelope.correlation_id or envelope.msg_id,
            task_id=task_id,
            subtask=subtask,
            specialty=specialty,
            context=context,
            source_node=envelope.source.model_dump(mode='json'),
            enqueued_at=now_utc(),
        )

        try:
            fut = await self.pool.submit(item)
        except asyncio.QueueFull:
            await self._send(
                ws,
                EXPEnvelope(
                    source=self.node,
                    target=envelope.source,
                    correlation_id=item.correlation_id,
                    type=EXPMessageType.TASK_RETRY,
                    payload={
                        'task_id': task_id,
                        'reason': 'overloaded',
                        'load': self.pool.load_snapshot(),
                    },
                ),
            )
            return

        asyncio.create_task(self._finalize_task(ws, envelope.source, item, fut, model))

    async def _handle_task_cancel(self, envelope: EXPEnvelope) -> None:
        task_id = str(envelope.payload.get('task_id', '')).strip()
        self._cancel_flags[task_id] = True

    async def _finalize_task(self, ws, target: EXPNode, item: WorkItem, fut: asyncio.Future[str], model: str) -> None:
        try:
            answer = await asyncio.wait_for(fut, timeout=self.task_timeout)
            if self._cancel_flags.pop(item.task_id, False):
                return  # cancelado pelo Juiz, não envia resultado
            envelope = EXPEnvelope(
                source=self.node,
                target=target,
                correlation_id=item.correlation_id,
                type=EXPMessageType.TASK_RESULT,
                payload={
                    'task_id': item.task_id,
                    'result': answer,
                    'specialty': item.specialty,
                    'metrics': self.metrics.snapshot(),
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
                payload={'task_id': item.task_id, 'reason': 'timeout'},
            )
            await self._send(ws, retry_msg)
        except Exception as exc:  # pragma: no cover
            self.metrics.track_failure()
            error_msg = EXPEnvelope(
                source=self.node,
                target=target,
                correlation_id=item.correlation_id,
                type=EXPMessageType.ERROR,
                payload={'task_id': item.task_id, 'message': str(exc)},
            )
            await self._send(ws, error_msg)
        finally:
            self._task_specialty_override.pop(item.task_id, None)
            self._cancel_flags.pop(item.task_id, None)

    async def _execute_item(self, item: WorkItem) -> str:
        # 1) RAG local: responde a partir do próprio conhecimento do nó antes do modelo.
        local_hit = self.search_engine.search(item.subtask, limit=3)
        if not local_hit.found:
            local_hit = self.rag.search(item.subtask, limit=3)
        if local_hit.found:
            self.metrics.track_success()
            return '\n'.join(local_hit.snippets)

        # 2) Se cancelado, interrompe imediatamente.
        if self._cancel_flags.get(item.task_id):
            raise asyncio.CancelledError()

        plugin = self.plugin_manager.get(item.specialty or '') if item.specialty else None
        if plugin is None:
            plugin = self.plugin_manager.best_for(item.subtask)

        selected_specialty = plugin.name
        item.specialty = selected_specialty

        prompt = plugin.build_prompt(subtask=item.subtask, context=item.context)
        started = time.perf_counter()
        try:
            # Modelo escolhido por este nó (melhor instalado), não imposto pelo Juiz.
            model = item.context.get('model') if isinstance(item.context, dict) else None
            if not model:
                model = self.model or await self._select_model()
            answer = await self.ollama.generate(
                OllamaGenerateRequest(
                    model=model,
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

    async def _select_model(self) -> str | None:
        try:
            return await self.ollama.select_best_model()
        except Exception:
            return self.model

    def _status_payload(self, cpu_pct: float = 0.0, free_ram_gb: float = 0.0, ready: bool = False) -> dict:
        return {
            'timestamp': datetime.now(UTC).isoformat(),
            'model': self.model,
            'cluster_role': self.cluster_role,
            'benchmark': self.benchmark_profile.as_dict(),
            'assigned_zim_files': self.assigned_zim_files,
            'specialties': [m.name for m in self.plugin_manager.list_plugins()],
            'capacity': {
                'max_concurrency': self.pool.workers,
                'queue_max': self.pool.queue.maxsize,
            },
            'load': {
                'queue_size': self.pool.queue.qsize(),
                'utilization': self.pool.load_snapshot()['utilization'],
                'cpu_pct': cpu_pct,
                'free_ram_gb': round(free_ram_gb, 2),
                'est_tps': self.metrics.est_tps(),
                'recent_fail_rate': self.metrics.recent_fail_rate(),
            },
            'metrics': self.metrics.snapshot(),
            'ready': ready,
            'paused': self._paused,
        }
