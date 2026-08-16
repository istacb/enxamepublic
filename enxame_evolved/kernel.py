#!/usr/bin/env python3
"""
EnxameKernel — Kernel Evoluído do Enxame
========================================
Integra Abelhas standalone com orquestração multi-agente,
auto-descoberta, perfis dinâmicos e execução por EIPs/Sprints.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bees import BeeService, BeeConfig, load_config
from bees.protocol.messages import BeeState

from .discovery import AutoDiscoveryService
from .profiles import AgentProfileManager
from .multimodal import MultimodalProcessor
from .orchestrator import TaskOrchestrator
from .sprint import SprintPlanner

logger = logging.getLogger("enxame.kernel")


@dataclass(slots=True)
class EnxameNode:
    """Nó do Enxame (evolução da Abelha com capacidades expandidas)."""
    node_id: str
    role: str = "enxame-node"
    state: BeeState = BeeState.STARTING
    capabilities: list[str] = field(default_factory=list)
    profiles: list[str] = field(default_factory=list)
    load: float = 0.0
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


class EnxameKernel:
    """
    Kernel principal do Enxame Evoluído.
    
    Responsabilidades:
    - Gerenciar Abelha local (offline-first RAG)
    - Auto-descoberta de peers e capacidades
    - Criar e gerenciar perfis de agentes dinamicamente
    - Processar multimodal (OCR, imagens, arquivos)
    - Orquestrar tarefas conforme EIPs/Sprints
    - Expor API unificada para Web UI
    """

    def __init__(self, config: BeeConfig | None = None) -> None:
        self.config = config or load_config(None)
        self.node_id = self.config.node_id
        
        # Componentes core (herdados da Abelha)
        self._bee: BeeService | None = None
        
        # Novos componentes evoluídos
        self._discovery: AutoDiscoveryService | None = None
        self._profiles: AgentProfileManager | None = None
        self._multimodal: MultimodalProcessor | None = None
        self._orchestrator: TaskOrchestrator | None = None
        self._sprint_planner: SprintPlanner | None = None
        
        # Estado
        self.state = BeeState.STARTING
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._http_runner = None

    async def start(self) -> None:
        """Inicializa todo o Enxame Evoluído."""
        logger.info(f"Iniciando Enxame Kernel {self.node_id}...")
        
        # 1. Iniciar Abelha local (base offline-first)
        self._bee = BeeService(self.config)
        await self._bee.start()
        logger.info("Abelha local iniciada")

        # 2. Auto-descoberta avançada
        self._discovery = AutoDiscoveryService(
            node_id=self.node_id,
            host=self.config.host,
            port=self.config.port,
            capabilities=self._get_full_capabilities(),
            models=self._bee._get_models_list() if self._bee else [],
            on_peer_found=self._on_peer_discovered,
            on_peer_lost=self._on_peer_lost,
        )
        await self._discovery.start()
        logger.info("Auto-descoberta iniciada")

        # 3. Gerenciador de Perfis de Agentes
        self._profiles = AgentProfileManager(
            node_id=self.node_id,
            discovery=self._discovery,
            bee_service=self._bee,
        )
        await self._profiles.initialize()
        logger.info("Perfis de agentes inicializados")

        # 4. Processador Multimodal
        self._multimodal = MultimodalProcessor(
            data_dir=self.config.data_dir,
            ollama_url=self.config.ollama_base_url,
            models=self._bee._get_models_list() if self._bee else [],
        )
        await self._multimodal.initialize()
        logger.info("Processador multimodal inicializado")

        # 5. Orquestrador de Tarefas
        self._orchestrator = TaskOrchestrator(
            kernel=self,
            profiles=self._profiles,
            multimodal=self._multimodal,
            discovery=self._discovery,
            bee=self._bee,
        )
        await self._orchestrator.initialize()
        logger.info("Orquestrador de tarefas inicializado")

        # 6. Planejador de Sprints/EIPs
        self._sprint_planner = SprintPlanner(
            orchestrator=self._orchestrator,
            profiles=self._profiles,
        )
        await self._sprint_planner.initialize()
        logger.info("Planejador de sprints inicializado")

        # 7. Iniciar servidor HTTP unificado (Web Server)
        from .web.server import create_web_server
        self._web_server = await create_web_server(self, self.config.host, self.config.port)
        logger.info(f"Web Server iniciado em {self.config.host}:{self.config.port}")

        # 8. Loops de background
        self._running = True
        self._tasks = [
            asyncio.create_task(self._health_loop()),
            asyncio.create_task(self._capability_sync_loop()),
            asyncio.create_task(self._profile_evolution_loop()),
        ]

        self.state = BeeState.RUNNING
        logger.info(f"Enxame Kernel {self.node_id} ONLINE - Estado: RUNNING")

    async def stop(self) -> None:
        """Finaliza graceful do Kernel."""
        logger.info(f"Parando Enxame Kernel {self.node_id}...")
        self.state = BeeState.STOPPING
        self._running = False

        for task in self._tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        if self._sprint_planner:
            await self._sprint_planner.close()
        if self._orchestrator:
            await self._orchestrator.close()
        if self._multimodal:
            await self._multimodal.close()
        if self._profiles:
            await self._profiles.close()
        if self._discovery:
            await self._discovery.stop()
        if self._bee:
            await self._bee.stop()
        # Fechar web server
        if self._web_server:
            await self._web_server.stop()

        self.state = BeeState.STOPPED
        logger.info(f"Enxame Kernel {self.node_id} OFFLINE")

    def _get_full_capabilities(self) -> list[str]:
        """Retorna capabilities completas incluindo evoluídas."""
        base = ["rag", "vector_search", "embeddings", "query", "index", "memory"]
        evolved = [
            "auto_discovery", "agent_profiles", "dynamic_profiling",
            "ocr", "image_analysis", "document_processing",
            "task_orchestration", "sprint_planning", "eip_compliance",
            "multimodal_rag", "peer_delegation", "swarm_intelligence"
        ]
        if self.config.allow_web:
            base.append("web_fallback")
        return base + evolved

    # =========================================================================
    # Callbacks de Descoberta
    # =========================================================================

    def _on_peer_discovered(self, peer) -> None:
        """Callback quando peer descoberto - cria perfil se necessário."""
        logger.info(f"Peer descoberto: {peer.node_id} - capacidades: {peer.capabilities}")
        if self._profiles:
            asyncio.create_task(self._profiles.evaluate_peer_for_profiles(peer))

    def _on_peer_lost(self, node_id: str) -> None:
        """Callback quando peer perdido."""
        logger.warning(f"Peer perdido: {node_id}")
        if self._orchestrator:
            asyncio.create_task(self._orchestrator.handle_peer_loss(node_id))

    # =========================================================================
    # Loops de Background
    # =========================================================================

    async def _health_loop(self) -> None:
        """Monitora saúde do sistema e peers."""
        while self._running:
            try:
                # Atualizar load
                self._update_load()
                # Verificar peers
                if self._discovery:
                    await self._discovery.cleanup_stale_peers()
                # Health check componentes
                await self._component_health_check()
            except Exception as e:
                logger.error(f"Erro no health loop: {e}")
            await asyncio.sleep(30)

    async def _capability_sync_loop(self) -> None:
        """Sincroniza capacidades com peers."""
        while self._running:
            try:
                if self._discovery and self._profiles:
                    peers = self._discovery.get_active_peers()
                    await self._profiles.sync_capabilities_with_peers(peers)
            except Exception as e:
                logger.error(f"Erro no capability sync: {e}")
            await asyncio.sleep(60)

    async def _profile_evolution_loop(self) -> None:
        """Evolui perfis baseado em uso e feedback."""
        while self._running:
            try:
                if self._profiles:
                    await self._profiles.evolve_profiles()
            except Exception as e:
                logger.error(f"Erro na evolução de perfis: {e}")
            await asyncio.sleep(300)  # 5 min

    async def _component_health_check(self) -> None:
        """Verifica saúde de todos os componentes."""
        checks = {
            "bee": self._bee is not None and self._bee.state == BeeState.RUNNING,
            "discovery": self._discovery is not None,
            "profiles": self._profiles is not None,
            "multimodal": self._multimodal is not None,
            "orchestrator": self._orchestrator is not None,
            "sprint_planner": self._sprint_planner is not None,
        }
        
        if not all(checks.values()):
            logger.warning(f"Componentes degradados: {checks}")
            self.state = BeeState.DEGRADED
        elif self.state == BeeState.DEGRADED:
            self.state = BeeState.RUNNING

    def _update_load(self) -> None:
        """Atualiza métricas de carga."""
        import psutil
        cpu = psutil.cpu_percent(interval=0.1) / 100.0
        mem = psutil.virtual_memory().percent / 100.0
        self.load = (cpu + mem) / 2.0
        if self._discovery:
            self._discovery.update_announcement(self.load, self.state)

    # =========================================================================
    # API Pública para Web UI e Integração
    # =========================================================================

    async def process_chat(self, message: str, context: dict | None = None) -> dict:
        """
        Processa mensagem de chat - ponto de entrada unificado.
        
        Fluxo:
        1. Analisa intenção e complexidade
        2. Seleciona/cria perfil adequado
        3. Processa multimodal se necessário (imagens, arquivos)
        4. Orquestra execução (local -> peer -> web)
        5. Retorna resposta estruturada
        """
        context = context or {}
        
        # 1. Análise de intenção
        analysis = await self._analyze_intent(message, context)
        
        # 2. Seleção de perfil
        profile = await self._profiles.select_or_create_profile(analysis)
        
        # 3. Processamento multimodal (se houver anexos)
        multimodal_context = {}
        if context.get("attachments"):
            multimodal_context = await self._multimodal.process_attachments(
                context["attachments"], profile
            )
        
        # 4. Execução orquestrada
        result = await self._orchestrator.execute_task(
            task=analysis["task"],
            profile=profile,
            context={**context, **multimodal_context},
            message=message,
        )
        
        return {
            "response": result.get("answer", ""),
            "profile_used": profile.profile_id,
            "source": result.get("source", "local"),
            "confidence": result.get("confidence", 0.0),
            "metadata": {
                "analysis": analysis,
                "multimodal": multimodal_context,
                "execution": result.get("metadata", {}),
            }
        }

    async def _analyze_intent(self, message: str, context: dict) -> dict:
        """Analisa intenção da mensagem para roteamento."""
        # Usa LLM local para classificação rápida
        prompt = f"""
Classifique esta mensagem para roteamento no Enxame:

Mensagem: {message}
Contexto: {context}

Retorne JSON:
{{
  "task_type": "query|code|analysis|creative|research|document|image|planning",
  "complexity": "simple|medium|complex",
  "domain": "general|technical|legal|medical|financial|creative",
  "requires_multimodal": true|false,
  "requires_tools": ["search", "code", "ocr", "image", "calc"],
  "suggested_profile": "nome_do_perfil_ideal",
  "estimated_steps": 3
}}
"""
        try:
            from core.ollama.client import OllamaClient, OllamaGenerateRequest
            ollama = OllamaClient(self.config.ollama_base_url)
            resp = await ollama.generate(
                OllamaGenerateRequest(
                    model=self.config.model,
                    prompt=prompt,
                    temperature=0.1,
                    num_ctx=2048,
                )
            )
            import json
            return json.loads(resp.strip())
        except Exception:
            # Fallback heurístico
            return {
                "task_type": "query",
                "complexity": "medium",
                "domain": "general",
                "requires_multimodal": bool(context.get("attachments")),
                "requires_tools": ["search"],
                "suggested_profile": "generalist",
                "estimated_steps": 2,
            }

    async def get_system_status(self) -> dict:
        """Retorna status completo do sistema para Web UI."""
        bee_status = {}
        if self._bee:
            bee_status = {
                "node_id": self._bee.node_id,
                "state": self._bee.state.value,
                "peers": len(self._bee._discovery.get_active_peers()) if self._bee._discovery else 0,
            }
        
        discovery_stats = self._discovery.get_stats() if self._discovery else {}
        profile_stats = self._profiles.get_stats() if self._profiles else {}
        multimodal_stats = self._multimodal.get_stats() if self._multimodal else {}
        orchestrator_stats = self._orchestrator.get_stats() if self._orchestrator else {}
        sprint_stats = self._sprint_planner.get_stats() if self._sprint_planner else {}
        
        return {
            "kernel": {
                "node_id": self.node_id,
                "version": "2.0.0",
                "state": self.state.value,
                "load": self.load,
                "uptime_seconds": 0,  # TODO: implementar
            },
            "bee": bee_status,
            "discovery": discovery_stats,
            "profiles": profile_stats,
            "multimodal": multimodal_stats,
            "orchestrator": orchestrator_stats,
            "sprint": sprint_stats,
            "capabilities": self._get_full_capabilities(),
        }

    async def execute_sprint_task(self, sprint_id: str, task_spec: dict) -> dict:
        """Executa tarefa de sprint conforme especificação EIP."""
        if not self._sprint_planner:
            return {"error": "Sprint planner não inicializado"}
        return await self._sprint_planner.execute_task(sprint_id, task_spec)

    async def create_agent_profile(self, spec: dict) -> dict:
        """Cria novo perfil de agente dinamicamente."""
        if not self._profiles:
            return {"error": "Profile manager não inicializado"}
        return await self._profiles.create_profile(spec)

    # =========================================================================
    # Servidor HTTP Unificado
    # =========================================================================

    async def _start_http_server(self) -> None:
        """Inicia servidor HTTP com API unificada."""
        from aiohttp import web
        from aiohttp.web import Request, Response

        app = web.Application()

        # Middleware CORS
        async def cors_middleware(app, handler):
            async def middleware_handler(request):
                resp = await handler(request)
                resp.headers['Access-Control-Allow-Origin'] = '*'
                resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
                resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
                return resp
            return middleware_handler
        app.middlewares.append(cors_middleware)

        # Health
        async def health(request: Request) -> Response:
            return web.json_response({"status": "ok", "node": self.node_id, "state": self.state.value})

        # Status completo
        async def status(request: Request) -> Response:
            return web.json_response(await self.get_system_status())

        # Chat endpoint
        async def chat(request: Request) -> Response:
            try:
                data = await request.json()
                message = data.get("message", "")
                context = data.get("context", {})
                if not message:
                    return web.json_response({"error": "message required"}, status=400)
                result = await self.process_chat(message, context)
                return web.json_response(result)
            except Exception as e:
                logger.error(f"Erro no chat: {e}")
                return web.json_response({"error": str(e)}, status=500)

        # Multimodal upload
        async def upload(request: Request) -> Response:
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
                result = await self._multimodal.process_files(files)
                return web.json_response(result)
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)

        # Perfis
        async def list_profiles(request: Request) -> Response:
            profiles = await self._profiles.list_profiles() if self._profiles else []
            return web.json_response({"profiles": profiles})

        async def create_profile(request: Request) -> Response:
            data = await request.json()
            result = await self.create_agent_profile(data)
            return web.json_response(result)

        # Sprint/EIP
        async def sprint_status(request: Request) -> Response:
            return web.json_response(self._sprint_planner.get_stats() if self._sprint_planner else {})

        async def sprint_execute(request: Request) -> Response:
            data = await request.json()
            result = await self.execute_sprint_task(data.get("sprint_id", ""), data.get("task", {}))
            return web.json_response(result)

        # Peers
        async def peers(request: Request) -> Response:
            peers = self._discovery.get_active_peers() if self._discovery else []
            return web.json_response({"peers": [p.__dict__ for p in peers]})

        # Rotas
        app.router.add_get("/health", health)
        app.router.add_get("/api/v1/status", status)
        app.router.add_post("/api/v1/chat", chat)
        app.router.add_post("/api/v1/upload", upload)
        app.router.add_get("/api/v1/profiles", list_profiles)
        app.router.add_post("/api/v1/profiles", create_profile)
        app.router.add_get("/api/v1/sprint", sprint_status)
        app.router.add_post("/api/v1/sprint/execute", sprint_execute)
        app.router.add_get("/api/v1/peers", peers)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.config.host, self.config.port)
        await site.start()
        self._http_runner = runner
        logger.info(f"HTTP Server iniciado em {self.config.host}:{self.config.port}")


async def main() -> int:
    import signal
    import argparse
    
    parser = argparse.ArgumentParser(description="Enxame Kernel Evoluído")
    parser.add_argument("--config", type=Path, help="Arquivo de configuração")
    parser.add_argument("--data-dir", type=Path, help="Diretório de dados")
    parser.add_argument("--host", default="0.0.0.0", help="Host de escuta")
    parser.add_argument("--port", type=int, default=8765, help="Porta HTTP")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="URL do Ollama")
    parser.add_argument("--model", help="Modelo Ollama")
    parser.add_argument("--allow-web", action="store_true", help="Permitir fallback web")
    parser.add_argument("--log-level", default="INFO", help="Nível de log")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = load_config(args)
    kernel = EnxameKernel(config)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(getattr(__import__("signal"), sig), lambda: asyncio.create_task(kernel.stop()))
        except (NotImplementedError, AttributeError):
            pass

    try:
        await kernel.start()
        print(f"\n✅ Enxame Kernel {config.node_id} ONLINE")
        print(f"   HTTP: http://{config.host}:{config.port}")
        print(f"   Health: http://{config.host}:{config.port}/health")
        print(f"   Status: http://{config.host}:{config.port}/api/v1/status")
        print("Pressione Ctrl+C para parar\n")
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        await kernel.stop()
        print("Enxame Kernel parado.")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))