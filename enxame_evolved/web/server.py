#!/usr/bin/env python3
"""
Web Server — Servidor HTTP para Enxame Evoluído
================================================
Serve:
- Interface Web (templates/index.html)
- API REST unificada
- WebSocket para tempo real
- Arquivos estáticos
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any

from aiohttp import web
from aiohttp.web import Request, Response, WebSocketResponse
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger("enxame.web")


class EnxameWebServer:
    """
    Servidor Web unificado para Enxame Evoluído.
    
    Integra com Kernel para expor:
    - Dashboard HTML (system status + chat)
    - API REST (/api/v1/*)
    - WebSocket para updates em tempo real
    """

    def __init__(self, kernel: Any, host: str = "0.0.0.0", port: int = 8765) -> None:
        self.kernel = kernel
        self.host = host
        self.port = port
        
        # Paths
        self.web_dir = Path(__file__).parent
        self.templates_dir = self.web_dir / "templates"
        self.static_dir = self.web_dir / "static"
        
        # Jinja2
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=True,
        )
        
        # App
        self.app = web.Application()
        self._websockets: set[WebSocketResponse] = set()
        self._setup_routes()
        self._setup_static()
        self._runner: web.AppRunner | None = None

    def _setup_routes(self) -> None:
        """Configura rotas da API e páginas."""
        # Páginas
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/dashboard", self.handle_index)
        
        # API - Status
        self.app.router.add_get("/api/v1/status", self.handle_status)
        self.app.router.add_get("/api/v1/peers", self.handle_peers)
        self.app.router.add_get("/api/v1/profiles", self.handle_profiles)
        self.app.router.add_get("/api/v1/sprint", self.handle_sprint_status)
        self.app.router.add_post("/api/v1/sprint/execute", self.handle_sprint_execute)
        
        # API - Chat
        self.app.router.add_post("/api/v1/chat", self.handle_chat)
        
        # API - Upload multimodal
        self.app.router.add_post("/api/v1/upload", self.handle_upload)
        
        # WebSocket para tempo real
        self.app.router.add_get("/ws", self.handle_websocket)

    def _setup_static(self) -> None:
        """Configura arquivos estáticos."""
        if self.static_dir.exists():
            self.app.router.add_static("/static/", path=str(self.static_dir), name="static")

    async def handle_index(self, request: Request) -> Response:
        """Serve página principal do dashboard."""
        template = self.jinja_env.get_template("index.html")
        html = template.render(
            node_id=self.kernel.node_id,
            version="2.0.0",
        )
        return web.Response(text=html, content_type="text/html")

    async def handle_status(self, request: Request) -> Response:
        """Retorna status completo do sistema."""
        status = await self.kernel.get_system_status()
        return web.json_response(status)

    async def handle_peers(self, request: Request) -> Response:
        """Lista peers descobertos."""
        if not self.kernel._discovery:
            return web.json_response({"peers": [], "active_peers": 0, "total_discovered": 0})
        
        peers = self.kernel._discovery.get_active_peers()
        return web.json_response({
            "peers": [
                {
                    "node_id": p.node_id,
                    "role": p.role,
                    "host": p.host,
                    "port": p.port,
                    "state": p.state.value,
                    "load": p.load,
                    "capabilities": p.capabilities,
                    "models": p.models,
                    "profiles": p.profiles,
                    "latency_ms": p._latency_ms,
                    "reliability": p._reliability_score,
                }
                for p in peers
            ],
            "active_peers": len(peers),
            "total_discovered": len(self.kernel._discovery._peers),
        })

    async def handle_profiles(self, request: Request) -> Response:
        """Lista perfis de agentes."""
        if not self.kernel._profiles:
            return web.json_response({"profiles": [], "total_profiles": 0})
        
        stats = self.kernel._profiles.get_stats()
        return web.json_response(stats)

    async def handle_chat(self, request: Request) -> Response:
        """Processa mensagem de chat via orquestrador."""
        try:
            data = await request.json()
            message = data.get("message", "").strip()
            context = data.get("context", {})
            
            if not message:
                return web.json_response({"error": "message required"}, status=400)
            
            result = await self.kernel.process_chat(message, context)
            return web.json_response(result)
            
        except Exception as e:
            logger.error(f"Erro no chat: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_upload(self, request: Request) -> Response:
        """Processa upload de arquivos multimodais."""
        try:
            reader = await request.multipart()
            files = []
            async for part in reader:
                if part.filename:
                    content = await part.read()
                    files.append({
                        "filename": part.filename,
                        "content": content,
                        "content_type": part.content_type,
                    })
            
            if not files:
                return web.json_response({"error": "no files"}, status=400)
            
            result = await self.kernel._multimodal.process_files(files)
            return web.json_response(result)
            
        except Exception as e:
            logger.error(f"Erro no upload: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_sprint_status(self, request: Request) -> Response:
        """Status do planejador de sprints."""
        if not self.kernel._sprint_planner:
            return web.json_response({"error": "sprint planner not initialized"}, status=503)
        
        return web.json_response(self.kernel._sprint_planner.get_stats())

    async def handle_sprint_execute(self, request: Request) -> Response:
        """Executa tarefa de sprint."""
        if not self.kernel._sprint_planner:
            return web.json_response({"error": "sprint planner not initialized"}, status=503)
        
        try:
            data = await request.json()
            result = await self.kernel._sprint_planner.execute_task(
                data.get("sprint_id", ""),
                data.get("task", {})
            )
            return web.json_response(result)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_websocket(self, request: Request) -> WebSocketResponse:
        """WebSocket para updates em tempo real."""
        ws = WebSocketResponse()
        await ws.prepare(request)
        
        self._websockets.add(ws)
        logger.info(f"WebSocket conectado. Total: {len(self._websockets)}")
        
        try:
            # Enviar status inicial
            status = await self.kernel.get_system_status()
            await ws.send_json({"type": "status", "data": status})
            
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        if data.get("type") == "ping":
                            await ws.send_json({"type": "pong"})
                    except Exception:
                        pass
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
        finally:
            self._websockets.discard(ws)
            logger.info(f"WebSocket desconectado. Total: {len(self._websockets)}")
        
        return ws

    async def broadcast(self, event: str, data: Any) -> None:
        """Broadcast para todos WebSocket conectados."""
        if not self._websockets:
            return
        
        message = json.dumps({"type": event, "data": data})
        dead = set()
        
        for ws in self._websockets:
            try:
                await ws.send_str(message)
            except Exception:
                dead.add(ws)
        
        for ws in dead:
            self._websockets.discard(ws)

    async def start(self) -> None:
        """Inicia servidor HTTP."""
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        logger.info(f"Web Server iniciado em http://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Para servidor."""
        # Fechar WebSockets
        for ws in self._websockets:
            await ws.close()
        self._websockets.clear()
        
        if self._runner:
            await self._runner.cleanup()
        logger.info("Web Server parado")


async def create_web_server(kernel: Any, host: str = "0.0.0.0", port: int = 8765) -> EnxameWebServer:
    """Factory para criar e iniciar web server."""
    server = EnxameWebServer(kernel, host, port)
    await server.start()
    return server