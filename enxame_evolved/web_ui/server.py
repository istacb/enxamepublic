"""
Web UI Server — Interface de Chat e Monitoramento
=================================================
Servidor FastAPI com:
- Chat em tempo real (WebSocket)
- Dashboard de status do agente
- Visualização de peers do enxame
- Métricas e perfis
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import suppress
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from enxame_evolved.agents.evolved_agent import EvolvedAgent, AgentCapability

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enxame.web_ui")


class ChatMessage(BaseModel):
    role: str  # user, assistant, system
    content: str
    attachments: list[dict] | None = None


class QueryRequest(BaseModel):
    query: str
    attachments: list[dict] | None = None


class ProfileCreateRequest(BaseModel):
    name: str
    capabilities: list[str]
    specialties: list[str] = []
    model: str = "llama3.2:3b"
    system_prompt: str = ""


class SprintPlanRequest(BaseModel):
    name: str
    goal: str
    tasks: list[dict]
    duration_days: int = 14


def create_web_app(agent: EvolvedAgent) -> FastAPI:
    """Cria aplicação FastAPI com rotas para o agente."""
    
    app = FastAPI(
        title="ENXAME Evolved - Web UI",
        version="2.0.0",
        description="Interface de chat e monitoramento para agente evoluído",
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # WebSocket connections ativas
    active_connections: list[WebSocket] = []
    
    # Servir arquivos estáticos
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve a página principal do chat."""
        return FileResponse(str(static_dir / "index.html"))
    
    @app.get("/api/v1/status")
    async def get_status():
        """Status completo do agente."""
        return agent.get_status()
    
    @app.get("/api/v1/profile")
    async def get_profile():
        """Perfil atual do agente."""
        profile = agent._current_profile or agent.profile_manager.get_default()
        return {
            "name": profile.name,
            "capabilities": [c.value for c in profile.capabilities],
            "specialties": profile.specialties,
            "model": profile.model,
            "system_prompt": profile.system_prompt,
            "metrics": {
                "success_rate": profile.success_rate,
                "avg_latency_ms": profile.avg_latency_ms,
                "tasks_completed": profile.tasks_completed,
            },
        }
    
    @app.get("/api/v1/profiles")
    async def list_profiles():
        """Lista todos os perfis disponíveis."""
        return agent.profile_manager.list_all()
    
    @app.post("/api/v1/profiles")
    async def create_profile(request: ProfileCreateRequest):
        """Cria novo perfil de agente."""
        from enxame_evolved.profiles.profile_manager import AgentProfileSpec
        
        spec = AgentProfileSpec(
            agent_id=agent.agent_id,
            name=request.name,
            capabilities=[AgentCapability(c) for c in request.capabilities],
            specialties=request.specialties,
            model=request.model,
            system_prompt=request.system_prompt,
        )
        profile = await agent.create_agent_profile(spec)
        return {"status": "created", "profile": profile.name}
    
    @app.post("/api/v1/query")
    async def process_query(request: QueryRequest):
        """Processa query via agente (REST)."""
        result = await agent.process_query(request.query, request.attachments)
        return result
    
    @app.post("/api/v1/sprint/plan")
    async def plan_sprint(request: SprintPlanRequest):
        """Planeja uma sprint."""
        sprint_spec = {
            "name": request.name,
            "goal": request.goal,
            "tasks": request.tasks,
            "duration_days": request.duration_days,
        }
        result = await agent.plan_sprint(sprint_spec)
        return result
    
    @app.post("/api/v1/sprint/execute")
    async def execute_sprint(sprint_id: str):
        """Executa uma sprint planejada."""
        result = await agent.task_orchestrator.execute_sprint(sprint_id)
        return result
    
    @app.get("/api/v1/peers")
    async def get_peers():
        """Lista peers descobertos no enxame."""
        return {
            "peers": agent._peer_agents,
            "count": len(agent._peer_agents),
        }
    
    @app.get("/api/v1/metrics")
    async def get_metrics():
        """Métricas do agente."""
        return agent.metrics.snapshot()
    
    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket):
        """WebSocket para chat em tempo real."""
        await websocket.accept()
        active_connections.append(websocket)
        
        try:
            # Enviar status inicial
            await websocket.send_json({
                "type": "status",
                "data": agent.get_status(),
            })
            
            while True:
                data = await websocket.receive_json()
                
                if data.get("type") == "query":
                    query = data.get("query", "")
                    attachments = data.get("attachments")
                    
                    # Enviar "pensando"
                    await websocket.send_json({
                        "type": "thinking",
                        "data": {"message": "Processando..."}
                    })
                    
                    # Processar query
                    result = await agent.process_query(query, attachments)
                    
                    # Enviar resposta
                    await websocket.send_json({
                        "type": "response",
                        "data": result,
                    })
                
                elif data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                
                elif data.get("type") == "get_status":
                    await websocket.send_json({
                        "type": "status",
                        "data": agent.get_status(),
                    })
        
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"Erro no WebSocket: {e}")
        finally:
            if websocket in active_connections:
                active_connections.remove(websocket)
    
    @app.websocket("/ws/monitor")
    async def websocket_monitor(websocket: WebSocket):
        """WebSocket para monitoramento em tempo real."""
        await websocket.accept()
        
        try:
            while True:
                status = agent.get_status()
                await websocket.send_json({
                    "type": "status_update",
                    "data": status,
                })
                await asyncio.sleep(2)  # Atualizar a cada 2s
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"Erro no monitor WebSocket: {e}")
    
    # Broadcast para todas as conexões
    async def broadcast(message: dict):
        for conn in active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                pass
    
    # Expor broadcast no app state
    app.state.broadcast = broadcast
    app.state.agent = agent
    
    return app


async def run_web_server(agent: EvolvedAgent, host: str = "0.0.0.0", port: int = 8080):
    """Inicia servidor web."""
    import uvicorn
    
    app = create_web_app(agent)
    
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()