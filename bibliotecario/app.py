from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import suppress
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from core.exp.http import build_auth_headers, EXP_SIGNATURE_HEADER, EXP_TIMESTAMP_HEADER
from core.exp.security import EXPAuthError, EXPSecurity
from guardian import GuardianPatrol

from .exp_agent import BibliotecarioEXPAgent
from .search_service import SearchPipelineService

logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger('bibliotecario')

NODE_ID = os.getenv('NODE_ID', 'bib-01')
EXP_SHARED_SECRET = os.getenv('EXP_SHARED_SECRET', 'enxame-dev-secret')
JUIZ_HTTP_URL = os.getenv('JUIZ_HTTP_URL', 'http://localhost:7700')
GUARDIAN_PATROL_INTERVAL = float(os.getenv('GUARDIAN_PATROL_INTERVAL', '15'))

security = EXPSecurity(EXP_SHARED_SECRET)
pipeline = SearchPipelineService()
agent = BibliotecarioEXPAgent(pipeline)

app = FastAPI(title='ENXAME Bibliotecário', version='1.0.0')


async def _report_guardian_alert_to_juiz(alert: dict[str, Any]) -> None:
    """Este node NÃO é o Juiz: a ronda do Guardião é reportada via POST
    assinado em /api/v1/guardian/report, para que o Juiz agregue o estado
    de segurança de todo o cluster."""
    body = json.dumps(alert, ensure_ascii=False).encode('utf-8')
    headers = build_auth_headers(security, body)
    headers['content-type'] = 'application/json'
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(f'{JUIZ_HTTP_URL}/api/v1/guardian/report', content=body, headers=headers)


guardian_patrol = GuardianPatrol(
    node_id=NODE_ID,
    interval_seconds=GUARDIAN_PATROL_INTERVAL,
    remote_reporter=_report_guardian_alert_to_juiz,
)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)


class QueryResponse(BaseModel):
    result: str
    metadata: dict


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


@app.on_event('startup')
async def startup_event() -> None:
    await pipeline.initialize()
    app.state.agent_task = asyncio.create_task(agent.run_forever())
    app.state.index_task = asyncio.create_task(pipeline.auto_reindex_loop())
    app.state.guardian_task = asyncio.create_task(guardian_patrol.run_forever())
    logger.info('Bibliotecário inicializado e conectado ao Juiz')


@app.on_event('shutdown')
async def shutdown_event() -> None:
    guardian_patrol.stop()
    for key in ('agent_task', 'index_task', 'guardian_task'):
        task = getattr(app.state, key, None)
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


@app.get('/api/v1/health')
async def health() -> dict[str, str]:
    return {'status': 'ok', 'node': NODE_ID, 'role': 'bibliotecario'}


@app.post('/api/v1/query', response_model=QueryResponse)
async def run_query(request: Request) -> QueryResponse:
    body = await verify_hmac_request(request)
    payload = json.loads(body.decode('utf-8'))
    query = str(payload.get('query', '')).strip()
    if not query:
        raise HTTPException(status_code=400, detail="Campo 'query' é obrigatório")

    result = await pipeline.search(query)
    return QueryResponse(result=result.answer, metadata=result.metadata)


@app.post('/api/v1/query/open', response_model=QueryResponse)
async def run_query_open(req: QueryRequest) -> QueryResponse:
    """Endpoint opcional para debug local sem HMAC."""
    result = await pipeline.search(req.query)
    return QueryResponse(result=result.answer, metadata=result.metadata)
