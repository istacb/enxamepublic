from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import suppress

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from core.exp.http import EXP_SIGNATURE_HEADER, EXP_TIMESTAMP_HEADER
from core.exp.security import EXPAuthError, EXPSecurity

from .exp_agent import BibliotecarioEXPAgent
from .search_service import SearchPipelineService

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("bibliotecario")

NODE_ID = os.getenv("NODE_ID", "bib-01")
EXP_SHARED_SECRET = os.getenv("EXP_SHARED_SECRET", "enxame-dev-secret")

security = EXPSecurity(EXP_SHARED_SECRET)
pipeline = SearchPipelineService()
agent = BibliotecarioEXPAgent(pipeline)

app = FastAPI(title="ENXAME Bibliotecário", version="1.0.0")


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
        raise HTTPException(status_code=401, detail="Headers de autenticação EXP ausentes")
    try:
        security.verify_http_message(body=body, timestamp=timestamp, signature=signature)
    except EXPAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return body


@app.on_event("startup")
async def startup_event() -> None:
    await pipeline.initialize()
    app.state.agent_task = asyncio.create_task(agent.run_forever())
    app.state.index_task = asyncio.create_task(pipeline.auto_reindex_loop())
    logger.info("Bibliotecário inicializado e conectado ao Juiz")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    for key in ("agent_task", "index_task"):
        task = getattr(app.state, key, None)
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "node": NODE_ID, "role": "bibliotecario"}


@app.post("/api/v1/query", response_model=QueryResponse)
async def run_query(request: Request) -> QueryResponse:
    body = await verify_hmac_request(request)
    payload = json.loads(body.decode("utf-8"))
    query = str(payload.get("query", "")).strip()
    if not query:
        raise HTTPException(status_code=400, detail="Campo 'query' é obrigatório")

    result = await pipeline.search(query)
    return QueryResponse(result=result.answer, metadata=result.metadata)


@app.post("/api/v1/query/open", response_model=QueryResponse)
async def run_query_open(req: QueryRequest) -> QueryResponse:
    """Endpoint opcional para debug local sem HMAC."""
    result = await pipeline.search(req.query)
    return QueryResponse(result=result.answer, metadata=result.metadata)
