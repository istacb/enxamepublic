from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from core.exp.envelope import EXPEnvelope
from core.exp.http import EXP_SIGNATURE_HEADER, EXP_TIMESTAMP_HEADER
from core.exp.input_sanitizer import get_sanitizer
from core.exp.security import EXPAuthError, EXPSecurity
from core.exp.server import EXPServerAdapter
from core.exp.types import EXPMessageType
from guardian import GuardianPatrol

from .service import JuizService

logger = logging.getLogger('juiz.guardian')

NODE_ID = os.getenv('NODE_ID', 'juiz-01')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
EXP_SHARED_SECRET = os.getenv('EXP_SHARED_SECRET', 'enxame-dev-secret')
GUARDIAN_PATROL_INTERVAL = float(os.getenv('GUARDIAN_PATROL_INTERVAL', '15'))

security = EXPSecurity(EXP_SHARED_SECRET)
sanitizer = get_sanitizer(strict_mode=False)
service = JuizService(node_id=NODE_ID, ollama_url=OLLAMA_URL, security=security)
server_adapter = EXPServerAdapter(security=security)

app = FastAPI(title='ENXAME Juiz', version='1.2.0')
installed_plugins: list[dict] = []

# Configurar diretório de arquivos estáticos
static_path = Path(__file__).parent / 'static'
if static_path.exists():
    app.mount('/', StaticFiles(directory=str(static_path), html=True), name='static')

# Ronda do Guardião: como este node é o Juiz, os alertas são entregues por
# chamada direta em processo (sem rede) via service.record_guardian_alert.
# O Juiz também agrega, no mesmo dicionário, os alertas que os demais nodes
# reportam via POST em /api/v1/guardian/report (ver abaixo).
_guardian_patrol = GuardianPatrol(
    node_id=NODE_ID,
    interval_seconds=GUARDIAN_PATROL_INTERVAL,
    local_callback=lambda alert: service.record_guardian_alert(NODE_ID, alert),
)
_guardian_task: asyncio.Task | None = None


@app.on_event('startup')
async def start_guardian_patrol() -> None:
    global _guardian_task
    _guardian_task = asyncio.create_task(_guardian_patrol.run_forever())


@app.on_event('shutdown')
async def stop_guardian_patrol() -> None:
    _guardian_patrol.stop()
    if _guardian_task is not None:
        _guardian_task.cancel()
        try:
            await _guardian_task
        except asyncio.CancelledError:
            pass


@app.get('/api/v1/health')
async def health() -> dict[str, str]:
    return {'status': 'ok', 'node': NODE_ID}


async def verify_hmac_request(request: Request) -> bytes:
    body = await request.body()
    signature = request.headers.get(EXP_SIGNATURE_HEADER)
    timestamp = request.headers.get(EXP_TIMESTAMP_HEADER)
    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail='Headers de autenticação EXP ausentes')
    try:
        security.verify_http_message(body=body, timestamp=timestamp, signature=signature)
    except EXPAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return body


@app.post('/api/v1/task')
async def submit_task(request: Request) -> dict:
    body = await verify_hmac_request(request)
    payload = json.loads(body.decode('utf-8'))
    prompt = str(payload.get('prompt', '')).strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Campo 'prompt' é obrigatório")

    # Guardião: sinaliza tentativas de prompt injection (não bloqueia — o
    # sanitizer abaixo já neutraliza o conteúdo — apenas registra o alerta
    # para auditoria de segurança do cluster).
    if _guardian_patrol.guardian.detect_injection(prompt):
        service.record_guardian_alert(
            NODE_ID,
            {
                'node_id': NODE_ID,
                'anomalies': ['TENTATIVA_DE_PROMPT_INJECTION'],
                'metrics': {},
                'timestamp': datetime.now(UTC).isoformat(),
            },
        )
        logger.warning('Guardião: possível prompt injection detectada em tarefa recebida')

    # Sanitiza o prompt para prevenir prompt injection
    safe_prompt = sanitizer.sanitize_for_llm(prompt)

    task = await service.submit_task(safe_prompt)
    return {
        'task_id': task.task_id,
        'status': task.status,
        'result': task.result,
    }


@app.get('/api/v1/task/{task_id}')
async def get_task(task_id: str, request: Request) -> dict:
    await verify_hmac_request(request)
    task = service.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Tarefa não encontrada')
    return {
        'task_id': task.task_id,
        'status': task.status,
        'result': task.result,
        'error': task.error,
        'updated_at': task.updated_at.isoformat(),
    }


@app.delete('/api/v1/task/{task_id}')
async def cancel_task(task_id: str, request: Request) -> dict:
    await verify_hmac_request(request)
    task = service.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Tarefa não encontrada')
    if task.status in {'completed', 'failed', 'cancelled'}:
        return {'task_id': task_id, 'status': task.status}
    task.status = 'cancelled'
    task.updated_at = datetime.now(UTC)
    return {'task_id': task_id, 'status': task.status}


@app.get('/api/v1/task/{task_id}/stream')
async def stream_task(task_id: str, request: Request) -> StreamingResponse:
    await verify_hmac_request(request)
    task = service.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Tarefa não encontrada')

    async def event_stream():
        sent = 0
        while True:
            while sent < len(task.events):
                ev = task.events[sent]
                yield f'data: {json.dumps(ev, ensure_ascii=False)}\n\n'
                sent += 1
            if task.status in {'completed', 'failed', 'cancelled'} and sent >= len(task.events):
                break
            await asyncio.sleep(0.2)

    return StreamingResponse(event_stream(), media_type='text/event-stream')


@app.get('/api/v1/cluster')
async def cluster_state(request: Request) -> dict:
    await verify_hmac_request(request)
    service._prune_stale_agents()
    return {
        'node': NODE_ID,
        'agents_connected': len(service.agents),
        'tasks_total': len(service.tasks),
        'roles': service.current_roles,
        'zim_distribution': service.zim_distribution,
    }


@app.post('/api/v1/guardian/report')
async def guardian_report(request: Request) -> dict:
    """Recebe a ronda de segurança de nodes que NÃO são o Juiz (Bibliotecário,
    Agentes). A ronda do próprio Juiz é entregue localmente por chamada
    direta (ver start_guardian_patrol), não por este endpoint."""
    body = await verify_hmac_request(request)
    payload = json.loads(body.decode('utf-8'))
    node_id = str(payload.get('node_id', '')).strip()
    if not node_id:
        raise HTTPException(status_code=400, detail="Campo 'node_id' é obrigatório")
    service.record_guardian_alert(node_id, payload)
    return {'status': 'recorded'}


@app.get('/api/v1/guardian')
async def guardian_state(request: Request) -> dict:
    """Estado de segurança agregado pelo Juiz: ronda local + rondas
    reportadas por todos os demais nodes do cluster."""
    await verify_hmac_request(request)
    return service.guardian_summary()


@app.post('/api/v1/election')
async def trigger_election(request: Request) -> dict:
    await verify_hmac_request(request)
    result = await service.run_election_if_possible()
    if result is None:
        return {'status': 'no_agents'}
    return {'status': 'ok', 'result': result}


@app.get('/api/v1/agents')
async def list_agents(request: Request) -> list[dict]:
    await verify_hmac_request(request)
    service._prune_stale_agents()
    out: list[dict] = []
    for conn in service.agents.values():
        out.append(
            {
                'node_id': conn.node.node_id,
                'role': conn.node.role,
                'address': conn.node.address,
                'last_seen': conn.last_seen.isoformat(),
                'active_tasks': conn.active_tasks,
                'models': conn.models,
                'capabilities': conn.capabilities,
                'specialties': conn.specialties,
                'capacity': {
                    'max_concurrency': conn.max_concurrency,
                    'queue_max': conn.queue_max,
                    'queue_size': conn.queue_size,
                    'utilization': conn.utilization,
                },
                'metrics': conn.metrics,
                'fail_count': conn.fail_count,
                'cluster_role': conn.cluster_role,
                'benchmark_score': conn.benchmark_score,
                'benchmark': conn.benchmark,
            }
        )
    return out


@app.post('/api/v1/plugins')
async def install_plugin(request: Request) -> dict:
    body = await verify_hmac_request(request)
    payload = json.loads(body.decode('utf-8'))
    name = str(payload.get('name', '')).strip()
    version = str(payload.get('version', '0.0.0')).strip()
    if not name:
        raise HTTPException(status_code=400, detail="Campo 'name' é obrigatório")
    plugin = {'name': name, 'version': version, 'installed_at': datetime.now(UTC).isoformat()}
    installed_plugins.append(plugin)
    return {'status': 'installed', 'plugin': plugin}


@app.websocket('/exp')
async def exp_socket(websocket: WebSocket) -> None:
    async def handler(envelope: EXPEnvelope, ws: WebSocket) -> None:
        if envelope.type == EXPMessageType.HELLO:
            ack = await service.register_agent(envelope, ws)
            await server_adapter.send(ws, ack)
            return
        if envelope.type == EXPMessageType.HEARTBEAT:
            await service.heartbeat(envelope)
            return
        if envelope.type == EXPMessageType.TASK_RESULT:
            await service.accept_task_result(envelope)
            return
        if envelope.type == EXPMessageType.ROLE_ACK:
            await service.accept_role_ack(envelope)
            return
        if envelope.type == EXPMessageType.QUERY_RESULT:
            await service.accept_query_result(envelope)
            return
        if envelope.type == EXPMessageType.ELECTION_PROPOSE:
            await service.accept_election_propose(envelope)
            return
        if envelope.type == EXPMessageType.ELECTION_VOTE:
            await service.accept_election_vote(envelope)
            return
        if envelope.type == EXPMessageType.TASK_RETRY:
            await service.accept_task_result(
                EXPEnvelope(
                    source=envelope.source,
                    target=envelope.target,
                    correlation_id=envelope.correlation_id,
                    type=EXPMessageType.TASK_RESULT,
                    payload={'result': ''},
                )
            )
            return

    await server_adapter.serve_socket(websocket, handler)
