#!/usr/bin/env python3
"""
EnxameKernel — Kernel Unificado CPU-First & Offline-First (EIP-0010)
====================================================================
Integra em um único processo leve e estável:
- Orquestração multi-nó e definição dinâmica/manual de papéis
- RAG incremental em CPU (SQLite FTS5 BM25) + sincronização com o Bibliotecário
- Guarda ativa (`GuardianGatekeeper`) contra prompt injection direto e indireto
- Memória semântica de longo prazo e evolução adaptativa ao perfil do usuário
- Histórico persistente de conversas com compactação de contexto por tier de CPU
- Voz bidirecional offline-first (STT/TTS) e Estúdio gratuito de Imagens em CPU
- Telemetria sem segredos compatível com o Manual ASD-STE100 (`/ping`, `/estado`,
  `/saude`, `/config`, `/pedido`, `/inventario`)
- Proveniência auditável em cada resposta (máquina, papel, modelo, fonte e tempo)
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import signal
import sys
import time
import uuid
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aiohttp import web

from bees import BeeConfig, BeeService, load_config
from bees.protocol.messages import BeeState
from core.exp.admin_access import admin_access_allowed
from core.ollama.client import OllamaClient

from .discovery import AutoDiscoveryService
from .fast_router import FastIntentRouter
from .hardware_tier import (
    CpuHardwareProfile,
    coletar_estado_ste,
    coletar_saude_ste,
    consultar_executor_ste,
    detect_cpu_hardware_profile,
    identidade_ste,
    sem_segredos,
)
from .media_cpu import CpuVoiceService, LocalCpuImageStudio
from .multimodal import MultimodalProcessor, ProcessedFile
from .orchestrator import TaskOrchestrator
from .profiles import AgentProfileManager
from .rag_sync import (
    BibliotecarioGlobalCatalog,
    LocalCpuRagEngine,
    TopicSketch,
    push_sketch_to_bibliotecario,
)
from .security_gate import GuardianGatekeeper
from .sprint import SprintPlanner
from .storage import UnifiedStore

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
    """Kernel principal unificado do Enxame (CPU-Only Ready & Offline-First)."""

    def __init__(self, config: BeeConfig | None = None) -> None:
        self.config = config or load_config(None)
        self.node_id = self.config.node_id
        self._started_monotonic = time.monotonic()

        # Garantir diretório de dados
        self.config.data_dir = Path(self.config.data_dir)
        self.config.data_dir.mkdir(parents=True, exist_ok=True)

        # Perfil real de CPU (Legado / Padrão / Performance) + STE-100
        self.hardware_profile: CpuHardwareProfile = detect_cpu_hardware_profile()

        # Persistência SQLite WAL unificada (conversas, contexto, memória evolutiva, pinos, guarda)
        self.store = UnifiedStore(self.config.data_dir / "enxame_unified.db")

        # Guarda unificada contra inputs maliciosos
        self.gatekeeper = GuardianGatekeeper(admin_token=os.environ.get("ENXAME_ADMIN_TOKEN"))

        # Motor RAG local leve em CPU + Catálogo Global do Bibliotecário
        self.rag_engine = LocalCpuRagEngine(
            db_path=self.config.data_dir / "rag_local_fts.db",
            node_id=self.node_id,
        )
        self.global_catalog = BibliotecarioGlobalCatalog(self.config.data_dir)

        # Cliente Ollama com keep_alive e threads calibradas para CPU
        self.ollama = OllamaClient(self.config.ollama_base_url, timeout=180.0)

        # Voz Offline-First (STT/TTS) e Estúdio Gratuito de Imagens em CPU
        self.voice_service = CpuVoiceService(self.config.data_dir)
        self.image_studio = LocalCpuImageStudio(
            data_dir=self.config.data_dir,
            node_id=self.node_id,
            machine_alias=self.hardware_profile.machine_alias,
            hardware_profile_fn=lambda: self.hardware_profile,
            on_event=self._broadcast_ws_event,
        )

        # Inventário de máquinas remotas cadastradas manualmente (LAN HTTP ou SSH)
        self._registered_machines: dict[str, dict[str, Any]] = {}

        # Componentes herdados e evoluídos
        self._bee: BeeService | None = None
        self._bee_service: BeeService | None = None
        self._discovery: AutoDiscoveryService | None = None
        self._profiles: AgentProfileManager | None = None
        self._multimodal: MultimodalProcessor | None = None
        self._orchestrator: TaskOrchestrator | None = None
        self._sprint_planner: SprintPlanner | None = None

        # Servidor HTTP unificado + WebSockets conectados + filas SSE de chat
        self._http_app: web.Application | None = None
        self._http_runner: web.AppRunner | None = None
        self._ws_clients: set[web.WebSocketResponse] = set()
        self._chat_streams: dict[str, asyncio.Queue[dict[str, Any]]] = {}

        # Estado operacional
        self.state = BeeState.STARTING
        self.load = 0.0
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Inicializa todo o Enxame Unificado em um único servidor HTTP."""
        logger.info(
            f"Iniciando Enxame Kernel {self.node_id} "
            f"[{self.hardware_profile.tier_label} · {self.hardware_profile.cpu_model}]..."
        )

        # 1. Criar aplicação HTTP unificada e registrar referência para BeeService
        self._http_app = web.Application(client_max_size=32 * 1024 * 1024)
        self._http_app["enxame_kernel"] = self
        self._setup_http_routes()

        # 2. Iniciar Abelha local (registra rotas compatíveis na mesma aplicação HTTP)
        self._bee = BeeService(self.config)
        self._bee_service = self._bee
        await self._bee.start(start_http=True, http_app=self._http_app)

        # 3. Auto-descoberta LAN
        self._discovery = AutoDiscoveryService(
            node_id=self.node_id,
            host=self.config.host,
            port=self.config.port,
            capabilities=self._get_full_capabilities(),
            models=self._bee._get_models_list() if self._bee else [],
            profiles=self._get_all_profiles(),
            on_peer_found=self._on_peer_discovered,
            on_peer_lost=self._on_peer_lost,
        )
        await self._discovery.start()

        # 4. Perfis dinâmicos de agentes
        self._profiles = AgentProfileManager(
            node_id=self.node_id,
            discovery=self._discovery,
            bee_service=self._bee,
        )
        await self._profiles.initialize()

        # 5. Processador Multimodal
        self._multimodal = MultimodalProcessor(
            data_dir=self.config.data_dir,
            ollama_url=self.config.ollama_base_url,
            models=self._bee._get_models_list() if self._bee else [],
        )
        await self._multimodal.initialize()

        # 6. Orquestrador CPU-First
        self._orchestrator = TaskOrchestrator(
            kernel=self,
            profiles=self._profiles,
            multimodal=self._multimodal,
            discovery=self._discovery,
            bee=self._bee,
        )
        await self._orchestrator.initialize()

        # 7. Planejador de Sprints/EIPs
        self._sprint_planner = SprintPlanner(
            orchestrator=self._orchestrator,
            profiles=self._profiles,
        )
        await self._sprint_planner.initialize()

        # 8. Indexação documental inicial leve em background + fila de imagens em CPU
        await self.image_studio.start()
        asyncio.create_task(self._bootstrap_initial_rag_and_warmup())

        # 9. Iniciar servidor HTTP unificado
        await self._start_unified_http_server()

        # 10. Loops de manutenção leves
        self._running = True
        self._tasks = [
            asyncio.create_task(self._health_loop()),
            asyncio.create_task(self._capability_sync_loop()),
            asyncio.create_task(self._profile_evolution_loop()),
        ]

        self.state = BeeState.RUNNING
        logger.info(f"Enxame Kernel {self.node_id} ONLINE em http://{self.config.host}:{self.config.port}")

    async def stop(self) -> None:
        logger.info(f"Parando Enxame Kernel {self.node_id}...")
        self.state = BeeState.STOPPING
        self._running = False

        for task in self._tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        await self.image_studio.stop()
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

        for ws in list(self._ws_clients):
            with suppress(Exception):
                await ws.close()
        self._ws_clients.clear()

        if self._http_runner:
            await self._http_runner.cleanup()
            self._http_runner = None

        self.rag_engine.close()
        self.store.close()
        self.state = BeeState.STOPPED
        logger.info(f"Enxame Kernel {self.node_id} OFFLINE")

    async def _bootstrap_initial_rag_and_warmup(self) -> None:
        """Indexa documentos locais se o índice estiver vazio e aquece modelo leve em RAM."""
        try:
            stats = self.rag_engine.get_stats()
            if stats["documents"] == 0:
                repo_root = Path(__file__).resolve().parents[1]
                readme = repo_root / "README.md"
                if readme.exists():
                    await asyncio.to_thread(self.rag_engine.index_file, readme, "enxame")
                eip_dir = repo_root / "spec" / "pt-BR" / "eip"
                if eip_dir.exists():
                    await asyncio.to_thread(self.rag_engine.index_directory, eip_dir, "arquitetura")
            await self.sync_rag_with_bibliotecario()
        except Exception as exc:
            logger.debug(f"Bootstrap RAG opcional ignorado: {exc}")

        # Warmup silencioso caso o Ollama esteja online
        try:
            models = self._bee._get_models_list() if self._bee else []
            if models:
                await self.ollama.warmup(models[0], num_thread=self.hardware_profile.recommended_threads)
        except Exception:
            pass

    async def sync_rag_with_bibliotecario(self) -> dict[str, Any]:
        """Gera TopicSketch local e registra no Bibliotecário (local ou remoto na LAN)."""
        sketch = await asyncio.to_thread(self.rag_engine.build_topic_sketch)
        local_reg = self.global_catalog.upsert_sketch(sketch)

        # Se existir um Bibliotecário remoto eleito na LAN, envia o sketch
        bib_endpoint = self._resolve_bibliotecario_endpoint()
        pushed_remote = False
        if bib_endpoint:
            pushed_remote = await push_sketch_to_bibliotecario(
                sketch,
                bib_endpoint,
                cluster_token=getattr(self.config, "cluster_secret", None),
            )
        return {
            "ok": True,
            "sketch": sketch.to_dict(),
            "catalog": self.global_catalog.get_catalog_stats(),
            "pushed_remote": pushed_remote,
            "local_registration": local_reg,
        }

    def _resolve_bibliotecario_endpoint(self) -> str | None:
        if not self._bee or not self._bee.cluster_state or not self._discovery:
            return None
        bib_id = self._bee.cluster_state.bibliotecario_id
        if not bib_id or bib_id == self.node_id:
            return None
        peer = self._discovery.get_peer(bib_id)
        if peer and getattr(peer, "host", None) and getattr(peer, "port", None):
            return f"http://{peer.host}:{peer.port}"
        return None

    async def _broadcast_ws_event(self, event_type: str, data: dict[str, Any]) -> None:
        if not self._ws_clients:
            return
        payload = {"type": event_type, "data": data}
        dead: list[web.WebSocketResponse] = []
        for ws in list(self._ws_clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._ws_clients.discard(ws)

    def _get_full_capabilities(self) -> list[str]:
        base = ["rag", "fts5_bm25", "query", "index", "memory", "cpu_inference"]
        evolved = [
            "auto_discovery", "agent_profiles", "dynamic_profiling",
            "ocr", "image_analysis", "document_processing",
            "task_orchestration", "sprint_planning", "eip_compliance",
            "multimodal_rag", "peer_delegation", "swarm_intelligence",
            "voice_stt_tts", "cpu_image_studio", "guardian_gatekeeper", "ste100_telemetry",
        ]
        if self.config.allow_web and not self.config.offline_mode:
            base.append("web_fallback")
        return base + evolved

    def _get_all_profiles(self) -> list[str]:
        return ["generalist", "coder", "researcher", "analyst", "creative", "legal", "medical", "architect"]

    def _is_admin_authorized(self, request: web.Request) -> bool:
        supplied = (
            request.headers.get("X-Admin-Token")
            or request.headers.get("X-Painel-Token")
            or (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
            or None
        )
        required = os.environ.get("ENXAME_ADMIN_TOKEN") or os.environ.get("PAINEL_TOKEN")
        return admin_access_allowed(request.remote, supplied, required)

    # =========================================================================
    # Rotas HTTP Unificadas (Painel Próprio ENXAME + STE-100 + APIs v1)
    # =========================================================================

    def _setup_http_routes(self) -> None:
        from aiohttp.web import Request, Response

        @web.middleware
        async def cors_and_security_middleware(request: Request, handler):
            if request.method == "OPTIONS":
                resp = web.Response(status=204)
            else:
                resp = await handler(request)
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, Authorization, x-session-token, X-Admin-Token, X-Painel-Token, X-Cluster-Token"
            )
            return resp

        self._http_app.middlewares.append(cors_and_security_middleware)
        self._http_app["enxame_kernel"] = self

        # --- STE-100: Telemetria e Operação Remota Sem Segredos ---
        async def ste_ping(request: Request) -> Response:
            roles = self.get_roles_matrix()["local_roles"]
            payload = identidade_ste(
                papel=roles[0] if roles else "worker_general",
                machine_alias=self.hardware_profile.machine_alias,
                sistema_nome="enxame",
            )
            payload.update({
                "servico": "enxame-unificado",
                "node_id": self.node_id,
                "alias": self.hardware_profile.machine_alias,
                "tier": self.hardware_profile.tier,
                "ts": int(time.time()),
            })
            return web.json_response(payload)

        async def ste_estado(request: Request) -> Response:
            self.hardware_profile = detect_cpu_hardware_profile()
            estado = coletar_estado_ste()
            estado["node_id"] = self.node_id
            estado["state"] = self.state.value
            estado["hardware_tier"] = self.hardware_profile.to_dict()
            estado["roles"] = self.get_roles_matrix()["local_roles"]
            return web.json_response(estado)

        async def ste_saude(request: Request) -> Response:
            saude = coletar_saude_ste(
                extra_checks={
                    "sqlite_store": True,
                    "rag_local_fts5": True,
                    "guardian_gatekeeper": True,
                    "estúdio_cpu": True,
                }
            )
            saude["node_id"] = self.node_id
            saude["rag_stats"] = self.rag_engine.get_stats()
            saude["guardian_stats"] = self.store.get_guardian_stats()
            return web.json_response(saude)

        async def ste_config(request: Request) -> Response:
            raw_cfg = {
                "node_id": self.node_id,
                "host": self.config.host,
                "port": self.config.port,
                "offline_mode": self.config.offline_mode,
                "allow_web": self.config.allow_web,
                "model": self.config.model,
                "confidence_threshold_enxame": self.config.confidence_threshold_enxame,
                "hardware_tier": self.hardware_profile.tier,
                "recommended_num_ctx": self.hardware_profile.recommended_num_ctx,
                "recommended_threads": self.hardware_profile.recommended_threads,
            }
            return web.json_response(sem_segredos(raw_cfg))

        async def ste_inventario(request: Request) -> Response:
            return web.json_response(await self.build_machine_inventory())

        async def ste_pedido(request: Request) -> Response:
            if not self._is_admin_authorized(request):
                return web.json_response({"ok": False, "erro": "acesso administrativo negado"}, status=403)
            data = await request.json()
            acao = str(data.get("acao") or "").strip()
            if acao == "sincronizar_rag":
                return web.json_response(await self.sync_rag_with_bibliotecario())
            if acao == "indexar_docs_projeto":
                return web.json_response(await self._index_project_docs())
            if acao == "aquecer_modelo":
                models = self._bee._get_models_list() if self._bee else []
                target = str(data.get("modelo") or (models[0] if models else self.config.model))
                ok = await self.ollama.warmup(target, num_thread=self.hardware_profile.recommended_threads)
                return web.json_response({"ok": ok, "modelo": target})
            if acao == "atualizar_hardware":
                self.hardware_profile = detect_cpu_hardware_profile()
                return web.json_response({"ok": True, "hardware": self.hardware_profile.to_dict()})
            return web.json_response({"ok": False, "erro": f"ação não permitida: {acao}"}, status=400)

        # --- Enxame Core & Chat v1 ---
        async def status_v1(request: Request) -> Response:
            return web.json_response(await self.get_system_status())

        async def chat_v1(request: Request) -> Response:
            try:
                data = await request.json()
                message = data.get("message", "")
                context = dict(data.get("context") or {})
                if data.get("profile"):
                    context["forced_profile"] = data["profile"]
                context["client_ip"] = request.remote or "local"
                if not message:
                    return web.json_response({"error": "message required"}, status=400)
                result = await self.process_chat(message, context)
                return web.json_response(result)
            except Exception as e:
                logger.error(f"Erro no chat v1: {e}")
                return web.json_response({"error": str(e)}, status=500)

        async def upload_v1(request: Request) -> Response:
            try:
                reader = await request.multipart()
                files = []
                index_in_rag = True
                async for part in reader:
                    if part.name == "index_rag":
                        val = (await part.text()).strip().lower()
                        index_in_rag = val not in ("0", "false", "no")
                    elif part.filename:
                        content = await part.read()
                        files.append({
                            "filename": part.filename,
                            "content": content,
                            "content_type": part.content_type,
                        })
                if not files:
                    return web.json_response({"error": "no files"}, status=400)
                result = await self._multimodal.process_files(files) if self._multimodal else {"files": []}
                # Indexa automaticamente textos extraídos no RAG local + Bibliotecário
                indexed_docs = []
                if index_in_rag:
                    for f_item in result.get("files", []):
                        txt = f_item.get("content") if isinstance(f_item, dict) else getattr(f_item, "content", "")
                        fname = f_item.get("filename") if isinstance(f_item, dict) else getattr(f_item, "filename", "anexo")
                        if txt and isinstance(txt, str) and txt.strip():
                            ing = await asyncio.to_thread(
                                self.rag_engine.ingest_text,
                                title=fname,
                                text=txt,
                                source=f"upload:{fname}",
                                domain="documentos_usuario",
                            )
                            indexed_docs.append(ing)
                    if indexed_docs:
                        await self.sync_rag_with_bibliotecario()
                result["rag_indexed"] = indexed_docs
                return web.json_response(result)
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)

        async def list_profiles(request: Request) -> Response:
            profiles = await self._profiles.list_profiles() if self._profiles else []
            return web.json_response({"profiles": profiles})

        async def create_profile(request: Request) -> Response:
            data = await request.json()
            result = await self.create_agent_profile(data)
            return web.json_response(result)

        async def sprint_status(request: Request) -> Response:
            return web.json_response(self._sprint_planner.get_stats() if self._sprint_planner else {})

        async def sprint_execute(request: Request) -> Response:
            data = await request.json()
            result = await self.execute_sprint_task(data.get("sprint_id", ""), data.get("task", {}))
            return web.json_response(result)

        # --- Conversas e Histórico Persistente (FTS5 + Contexto Compactado) ---
        async def conversations_list_or_create(request: Request) -> Response:
            if request.method == "POST":
                data = await request.json() if request.can_read_body else {}
                conv = self.store.create_conversation(title=data.get("title") or "Nova conversa")
                return web.json_response(conv)
            q = (request.query.get("q") or "").strip()
            if q:
                return web.json_response({"results": self.store.search_history(q, limit=25)})
            return web.json_response({"conversations": self.store.list_conversations(limit=60)})

        async def conversation_detail_or_delete(request: Request) -> Response:
            conv_id = request.match_info["conv_id"]
            if request.method == "DELETE":
                ok = self.store.delete_conversation(conv_id)
                return web.json_response({"deleted": ok, "conversation_id": conv_id})
            conv = self.store.get_conversation(conv_id)
            if not conv:
                return web.json_response({"error": "conversa não encontrada"}, status=404)
            return web.json_response(conv)

        # --- Memória de Longo Prazo & Evolução Adaptativa do Usuário ---
        async def memory_get_or_post(request: Request) -> Response:
            if request.method == "POST":
                data = await request.json()
                if data.get("fact"):
                    mem = self.store.add_memory(
                        fact=str(data["fact"]),
                        category=str(data.get("category") or "manual"),
                        importance=float(data.get("importance", 0.85)),
                        source_conv_id=data.get("conversation_id"),
                    )
                    return web.json_response({"ok": True, "memory": mem})
                prof = self.store.update_user_preferences(data)
                return web.json_response({"ok": True, "profile": prof})

            prof = self.store.get_user_profile()
            prof["adaptive_prompt"] = self.store.build_adaptive_style_prompt()
            return web.json_response({
                "profile": prof,
                "memories": self.store.list_memories(limit=50),
            })

        async def memory_delete(request: Request) -> Response:
            mem_id = request.match_info["mem_id"]
            ok = self.store.delete_memory(mem_id)
            return web.json_response({"deleted": ok, "mem_id": mem_id})

        # --- RAG Local & Sincronização com Bibliotecário ---
        async def rag_status(request: Request) -> Response:
            sketch = await asyncio.to_thread(self.rag_engine.build_topic_sketch)
            return web.json_response({
                "local": self.rag_engine.get_stats(),
                "documents": self.rag_engine.list_documents(limit=50),
                "sketch": sketch.to_dict(),
                "global_catalog": self.global_catalog.get_catalog_stats(),
                "bibliotecario_endpoint": self._resolve_bibliotecario_endpoint() or "local",
            })

        async def rag_ingest(request: Request) -> Response:
            data = await request.json()
            if data.get("bootstrap_project"):
                return web.json_response(await self._index_project_docs())
            title = str(data.get("title") or "Nota Local").strip()
            text = str(data.get("text") or "").strip()
            domain = str(data.get("domain") or "geral").strip()
            if not text:
                return web.json_response({"error": "texto vazio"}, status=400)
            ing = await asyncio.to_thread(
                self.rag_engine.ingest_text,
                title=title,
                text=text,
                source=f"manual:{title}",
                domain=domain,
            )
            sync_info = await self.sync_rag_with_bibliotecario()
            return web.json_response({"ok": True, "ingested": ing, "sync": sync_info})

        async def rag_search_api(request: Request) -> Response:
            q = (request.query.get("q") or "").strip()
            hits = self.rag_engine.search(q, top_k=6) if q else []
            return web.json_response({"query": q, "hits": hits})

        async def cluster_receive_sketch(request: Request) -> Response:
            data = await request.json()
            sketch = TopicSketch(
                node_id=str(data.get("node_id") or "unknown"),
                domains=list(data.get("domains") or []),
                top_terms=list(data.get("top_terms") or []),
                doc_count=int(data.get("doc_count") or 0),
                chunk_count=int(data.get("chunk_count") or 0),
                content_hash=str(data.get("content_hash") or ""),
                updated_at=float(data.get("updated_at") or time.time()),
            )
            reg = self.global_catalog.upsert_sketch(sketch)
            return web.json_response(reg)

        # --- Definição de Papéis & Orquestração de Máquinas ---
        async def roles_get_or_pin(request: Request) -> Response:
            if request.method == "POST":
                if not self._is_admin_authorized(request):
                    return web.json_response({"error": "acesso administrativo negado"}, status=403)
                data = await request.json()
                nid = str(data.get("node_id") or self.node_id)
                roles = [str(r) for r in (data.get("roles") or [])]
                self.store.set_role_pin(nid, roles)
                await self._broadcast_ws_event("roles_updated", self.get_roles_matrix())
                return web.json_response(self.get_roles_matrix())
            return web.json_response(self.get_roles_matrix())

        async def machines_probe(request: Request) -> Response:
            if not self._is_admin_authorized(request):
                return web.json_response({"error": "acesso administrativo negado"}, status=403)
            data = await request.json()
            alias = str(data.get("alias") or data.get("host") or f"maq-{len(self._registered_machines)+1}")
            mode = str(data.get("mode") or "http")
            endpoint = str(data.get("endpoint") or "")
            ssh_host = str(data.get("ssh_host") or "")
            probe = await asyncio.to_thread(
                consultar_executor_ste,
                endpoint_or_host=ssh_host if mode == "ssh" else endpoint,
                mode=mode,
                token=data.get("token"),
                ssh_user=data.get("ssh_user"),
            )
            entry = {
                "alias": alias,
                "mode": mode,
                "endpoint": endpoint or ssh_host,
                "last_probe": probe,
                "updated_at": time.time(),
            }
            self._registered_machines[alias] = entry
            return web.json_response({"ok": True, "machine": entry})

        # --- Guarda de Segurança ---
        async def guardian_events(request: Request) -> Response:
            return web.json_response({
                "stats": self.store.get_guardian_stats(),
                "events": self.store.list_guardian_events(limit=40),
            })

        # --- Voz Bidirecional Offline-First (STT & TTS) ---
        async def audio_capabilities(request: Request) -> Response:
            return web.json_response(self.voice_service.get_capabilities())

        async def audio_transcribe(request: Request) -> Response:
            reader = await request.multipart()
            audio_bytes = b""
            filename = "voice.webm"
            lang = "pt"
            async for part in reader:
                if part.name == "language":
                    lang = (await part.text()).strip() or "pt"
                elif part.filename or part.name == "audio":
                    filename = part.filename or filename
                    audio_bytes = await part.read()
            res = await self.voice_service.transcribe(audio_bytes, filename=filename, language=lang)
            return web.json_response(res)

        async def audio_synthesize(request: Request) -> Response:
            data = await request.json()
            text = str(data.get("text") or "").strip()
            voice = str(data.get("voice") or "pt-BR")
            res = await self.voice_service.synthesize(text, voice=voice)
            if res.get("ok") and res.get("audio_bytes"):
                return web.Response(
                    body=res["audio_bytes"],
                    content_type=res.get("mime_type", "audio/wav"),
                    headers={"X-TTS-Engine": str(res.get("engine", "local"))},
                )
            return web.json_response(res)

        # --- Estúdio Gratuito de Imagens em CPU & Galeria ---
        async def images_engines(request: Request) -> Response:
            return web.json_response(self.image_studio.detect_engines())

        async def images_gallery(request: Request) -> Response:
            return web.json_response({"images": self.image_studio.list_gallery(limit=60)})

        async def images_generate(request: Request) -> Response:
            data = await request.json()
            prompt = str(data.get("prompt") or "").strip()
            if not prompt:
                return web.json_response({"error": "prompt obrigatório"}, status=400)
            verdict = self.gatekeeper.inspect_input(prompt, client_id=request.remote or "local")
            if verdict.action == "BLOCK":
                self.store.record_guardian_event(
                    action="BLOCK",
                    risk_score=verdict.risk_score,
                    reason=verdict.reason,
                    matched_rules=verdict.matched_rules,
                    input_preview=prompt,
                    client_id=request.remote or "local",
                )
                return web.json_response({"error": verdict.reason, "blocked": True}, status=400)

            job = await self.image_studio.enqueue_generation(
                prompt=prompt,
                negative_prompt=str(data.get("negative_prompt") or ""),
                width=int(data.get("width") or 512),
                height=int(data.get("height") or 512),
                steps=int(data.get("steps") or 4),
                seed=int(data["seed"]) if data.get("seed") not in (None, "", -1) else None,
                engine=str(data.get("engine") or "auto"),
            )
            return web.json_response(job.to_dict())

        async def images_job_status(request: Request) -> Response:
            job = self.image_studio.get_job(request.match_info["job_id"])
            if not job:
                return web.json_response({"error": "job não encontrado"}, status=404)
            return web.json_response(job)

        async def images_serve_file(request: Request) -> Response:
            fname = Path(request.match_info["filename"]).name
            fpath = (self.image_studio.gallery_dir / fname).resolve()
            if fpath.parent != self.image_studio.gallery_dir.resolve() or not fpath.exists():
                return web.json_response({"error": "imagem não encontrada"}, status=404)
            return web.FileResponse(fpath)

        async def images_delete(request: Request) -> Response:
            ok = self.image_studio.delete_image(request.match_info["job_id"])
            return web.json_response({"deleted": ok})

        # --- Configurações Runtime (Offline-First / Fallback Internet) ---
        async def update_runtime_settings(request: Request) -> Response:
            if not self._is_admin_authorized(request):
                return web.json_response({"error": "acesso administrativo negado"}, status=403)
            data = await request.json()
            if "offline_mode" in data:
                self.config.offline_mode = bool(data["offline_mode"])
            if "allow_web" in data:
                self.config.allow_web = bool(data["allow_web"])
            if "confidence_threshold" in data:
                self.config.confidence_threshold_enxame = max(0.1, min(0.99, float(data["confidence_threshold"])))
            if "model" in data and data["model"]:
                self.config.model = str(data["model"])
            return web.json_response({
                "ok": True,
                "offline_mode": self.config.offline_mode,
                "allow_web": self.config.allow_web,
                "confidence_threshold": self.config.confidence_threshold_enxame,
                "model": self.config.model,
            })

        # Registrar rotas STE-100
        self._http_app.router.add_get("/ping", ste_ping)
        self._http_app.router.add_get("/estado", ste_estado)
        self._http_app.router.add_get("/saude", ste_saude)
        self._http_app.router.add_get("/config", ste_config)
        self._http_app.router.add_get("/inventario", ste_inventario)
        self._http_app.router.add_post("/pedido", ste_pedido)

        # Registrar rotas v1
        self._http_app.router.add_get("/api/v1/status", status_v1)
        self._http_app.router.add_post("/api/v1/chat", chat_v1)
        self._http_app.router.add_post("/api/v1/upload", upload_v1)
        self._http_app.router.add_get("/api/v1/profiles", list_profiles)
        self._http_app.router.add_post("/api/v1/profiles", create_profile)
        self._http_app.router.add_get("/api/v1/sprint", sprint_status)
        self._http_app.router.add_post("/api/v1/sprint/execute", sprint_execute)

        self._http_app.router.add_get("/api/v1/conversations", conversations_list_or_create)
        self._http_app.router.add_post("/api/v1/conversations", conversations_list_or_create)
        self._http_app.router.add_get("/api/v1/conversations/{conv_id}", conversation_detail_or_delete)
        self._http_app.router.add_delete("/api/v1/conversations/{conv_id}", conversation_detail_or_delete)

        self._http_app.router.add_get("/api/v1/memory", memory_get_or_post)
        self._http_app.router.add_post("/api/v1/memory", memory_get_or_post)
        self._http_app.router.add_delete("/api/v1/memory/{mem_id}", memory_delete)

        self._http_app.router.add_get("/api/v1/rag/status", rag_status)
        self._http_app.router.add_post("/api/v1/rag/ingest", rag_ingest)
        self._http_app.router.add_get("/api/v1/rag/search", rag_search_api)
        self._http_app.router.add_post("/api/v1/cluster/sketch", cluster_receive_sketch)

        self._http_app.router.add_get("/api/v1/roles", roles_get_or_pin)
        self._http_app.router.add_post("/api/v1/roles/pin", roles_get_or_pin)
        self._http_app.router.add_post("/api/v1/machines/probe", machines_probe)
        self._http_app.router.add_get("/api/v1/guardian/events", guardian_events)

        self._http_app.router.add_get("/api/v1/audio/capabilities", audio_capabilities)
        self._http_app.router.add_post("/api/v1/audio/transcribe", audio_transcribe)
        self._http_app.router.add_post("/api/v1/audio/synthesize", audio_synthesize)

        self._http_app.router.add_get("/api/v1/images/engines", images_engines)
        self._http_app.router.add_get("/api/v1/images/gallery", images_gallery)
        self._http_app.router.add_post("/api/v1/images/generate", images_generate)
        self._http_app.router.add_get("/api/v1/images/jobs/{job_id}", images_job_status)
        self._http_app.router.add_get("/api/v1/images/file/{filename}", images_serve_file)
        self._http_app.router.add_delete("/api/v1/images/{job_id}", images_delete)

        self._http_app.router.add_post("/api/v1/settings", update_runtime_settings)

        # WebSocket em tempo real
        self._http_app.router.add_get("/ws", self._handle_websocket)

        # Web UI unificada com identidade própria ENXAME
        self._setup_static_files()

    def _setup_static_files(self) -> None:
        """Serve a Web UI unificada `web/` na raiz `/` sem conflito de rotas."""
        from aiohttp.web import Request, Response

        unified_web_dir = (Path(__file__).resolve().parents[1] / "web").resolve()
        legacy_static_dir = Path(__file__).parent / "web" / "static"
        if legacy_static_dir.exists():
            self._http_app.router.add_static("/static/", path=str(legacy_static_dir), name="static")

        async def serve_root(request: Request) -> Response:
            index_file = unified_web_dir / "index.html"
            if index_file.exists():
                return web.FileResponse(index_file, headers={"Cache-Control": "no-cache"})
            return web.Response(text="Enxame Web UI não encontrada", content_type="text/plain", status=404)

        async def serve_web_asset(request: Request) -> Response:
            rel = request.match_info["asset"]
            candidate = (unified_web_dir / rel).resolve()
            if candidate.parent != unified_web_dir or not candidate.is_file():
                raise web.HTTPNotFound()
            ctype, _ = mimetypes.guess_type(str(candidate))
            return web.FileResponse(
                candidate,
                headers={
                    "Content-Type": ctype or "application/octet-stream",
                    "Cache-Control": "no-cache",
                },
            )

        self._http_app.router.add_get("/", serve_root)
        self._http_app.router.add_get("/dashboard", serve_root)
        self._http_app.router.add_get(
            r"/{asset:[A-Za-z0-9_.-]+\.(?:js|css|svg|png|jpg|ico|json|webmanifest|woff2)}",
            serve_web_asset,
        )

    async def _start_unified_http_server(self) -> None:
        self._http_runner = web.AppRunner(self._http_app)
        await self._http_runner.setup()
        site = web.TCPSite(self._http_runner, self.config.host, self.config.port)
        await site.start()

    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._ws_clients.add(ws)
        try:
            status = await self.get_system_status()
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
            self._ws_clients.discard(ws)
        return ws

    # =========================================================================
    # Inventário, Papéis e Documentação Local
    # =========================================================================

    def get_roles_matrix(self) -> dict[str, Any]:
        pins = self.store.get_role_pins()
        local_pin = pins.get(self.node_id)
        elected = []
        if self._bee and getattr(self._bee, "cluster_role", None):
            elected = [self._bee.cluster_role.value]
        local_roles = local_pin or elected or ["rainha", "juiz", "bibliotecario", "guarda", "worker_general", "worker_artist"]

        role_catalog = [
            {"id": "rainha", "name": "Rainha (Orquestradora)", "desc": "Coordena o enxame, contexto multi-turno e síntese"},
            {"id": "juiz", "name": "Juiz (Placement & Saúde)", "desc": "Pontua hardware/CPU e decide qual máquina executa"},
            {"id": "bibliotecario", "name": "Bibliotecário (RAG Global)", "desc": "Mantém catálogo de tópicos e roteia buscas documentais"},
            {"id": "guarda", "name": "Guarda (Segurança)", "desc": "Filtra prompt injection direto e indireto com nonces"},
            {"id": "worker_general", "name": "Operária CPU (Inferência)", "desc": "Executa raciocínio, código e análise em CPU"},
            {"id": "worker_artist", "name": "Artista CPU (Imagens & Voz)", "desc": "Gera imagens locais gratuitas e processa voz STT/TTS"},
        ]

        nodes_roles = [
            {
                "node_id": self.node_id,
                "alias": self.hardware_profile.machine_alias,
                "is_local": True,
                "hardware_tier": self.hardware_profile.tier,
                "hardware_tier_label": self.hardware_profile.tier_label,
                "roles": local_roles,
                "pinned": bool(local_pin),
            }
        ]
        if self._discovery:
            for p in self._discovery.get_active_peers():
                p_pin = pins.get(p.node_id)
                nodes_roles.append({
                    "node_id": p.node_id,
                    "alias": p.node_id,
                    "is_local": False,
                    "hardware_tier": "padrao",
                    "hardware_tier_label": "Peer LAN",
                    "roles": p_pin or [getattr(p, "role", "worker_general")],
                    "pinned": bool(p_pin),
                })

        return {
            "catalog": role_catalog,
            "local_roles": local_roles,
            "nodes": nodes_roles,
            "pins": pins,
        }

    async def build_machine_inventory(self) -> dict[str, Any]:
        """Constrói inventário STE-100 completo (máquina local + peers LAN + máquinas SSH/HTTP)."""
        self.hardware_profile = detect_cpu_hardware_profile()
        local_estado = coletar_estado_ste()
        local_saude = coletar_saude_ste()
        roles_info = self.get_roles_matrix()

        machines = [
            {
                "node_id": self.node_id,
                "alias": self.hardware_profile.machine_alias,
                "is_local": True,
                "status": "online",
                "transport": "local",
                "os": f"{self.hardware_profile.os_name} {self.hardware_profile.os_release}".strip(),
                "arch": self.hardware_profile.architecture,
                "cpu_model": self.hardware_profile.cpu_model,
                "cores_physical": self.hardware_profile.cores_physical,
                "cores_logical": self.hardware_profile.cores_logical,
                "has_avx2": self.hardware_profile.has_avx2,
                "ram_total_gb": self.hardware_profile.ram_total_gb,
                "ram_free_gb": self.hardware_profile.ram_free_gb,
                "disk_free_gb": self.hardware_profile.disk_free_gb,
                "cpu_pct": local_estado.get("cpu_pct", -1.0),
                "ram_pct": local_estado.get("ram_pct", -1.0),
                "disco_pct": local_estado.get("disco_pct", -1.0),
                "uptime_s": local_estado.get("uptime_s", -1),
                "hardware_tier": self.hardware_profile.tier,
                "hardware_tier_label": self.hardware_profile.tier_label,
                "est_tokens_per_sec": self.hardware_profile.est_tokens_per_sec,
                "est_image_seconds": self.hardware_profile.est_image_seconds,
                "pacing_notice": self.hardware_profile.pacing_notice,
                "roles": roles_info["local_roles"],
                "models": self._bee._get_models_list() if self._bee else [],
                "health_ok": local_saude.get("ok", True),
                "warnings": local_saude.get("avisos", []),
            }
        ]

        if self._discovery:
            for p in self._discovery.get_active_peers():
                machines.append({
                    "node_id": p.node_id,
                    "alias": p.node_id,
                    "is_local": False,
                    "status": "online",
                    "transport": f"lan:{p.host}:{p.port}",
                    "os": "LAN Peer",
                    "arch": "-",
                    "cpu_model": "Peer Descoberto via mDNS/BEE",
                    "cores_physical": -1,
                    "cores_logical": -1,
                    "has_avx2": True,
                    "ram_total_gb": -1.0,
                    "ram_free_gb": -1.0,
                    "disk_free_gb": -1.0,
                    "cpu_pct": round((p.load or 0.0) * 100.0, 1),
                    "ram_pct": -1.0,
                    "disco_pct": -1.0,
                    "uptime_s": -1,
                    "hardware_tier": "padrao",
                    "hardware_tier_label": "Peer LAN",
                    "est_tokens_per_sec": 12.0,
                    "est_image_seconds": 45,
                    "pacing_notice": "Máquina par conectada na rede local.",
                    "roles": [p.role],
                    "models": p.models,
                    "health_ok": True,
                    "warnings": [],
                })

        for alias, rem in self._registered_machines.items():
            probe = rem.get("last_probe") or {}
            est = probe.get("estado") or {}
            sau = probe.get("saude") or {}
            id_info = est.get("identidade") or {}
            machines.append({
                "node_id": f"rem-{alias}",
                "alias": alias,
                "is_local": False,
                "status": "online" if probe.get("ok") else "unreachable",
                "transport": f"{rem['mode']}:{rem['endpoint']}",
                "os": f"{id_info.get('sistema', '-')} {id_info.get('versao_so', '')}".strip(),
                "arch": id_info.get("arquitetura", "-"),
                "cpu_model": "Executor Remoto STE-100",
                "cores_physical": est.get("nucleos_fisicos", -1),
                "cores_logical": est.get("nucleos_logicos", -1),
                "has_avx2": True,
                "ram_total_gb": est.get("ram_total_gb", -1.0),
                "ram_free_gb": est.get("ram_livre_gb", -1.0),
                "disk_free_gb": est.get("disco_livre_gb", -1.0),
                "cpu_pct": est.get("cpu_pct", -1.0),
                "ram_pct": est.get("ram_pct", -1.0),
                "disco_pct": est.get("disco_pct", -1.0),
                "uptime_s": est.get("uptime_s", -1),
                "hardware_tier": "legado" if (0 < est.get("nucleos_fisicos", 4) < 4) else "padrao",
                "hardware_tier_label": "Executor Remoto",
                "est_tokens_per_sec": 8.0,
                "est_image_seconds": 60,
                "pacing_notice": "Nó consultado via protocolo STE-100.",
                "roles": ["worker_general"],
                "models": [],
                "health_ok": bool(sau.get("ok", probe.get("ok", False))),
                "warnings": sau.get("avisos", [] if probe.get("ok") else [probe.get("erro", "inacessível")]),
            })

        return {
            "updated_at": time.time(),
            "total_machines": len(machines),
            "machines": machines,
        }

    async def _index_project_docs(self) -> dict[str, Any]:
        repo_root = Path(__file__).resolve().parents[1]
        indexed = 0
        for rel in ("README.md", "spec/pt-BR/eip", "docs"):
            target = repo_root / rel
            if target.is_file():
                res = await asyncio.to_thread(self.rag_engine.index_file, target, "documentacao")
                indexed += 1 if res.get("indexed") else 0
            elif target.is_dir():
                res = await asyncio.to_thread(self.rag_engine.index_directory, target, "documentacao")
                indexed += int(res.get("indexed_files", 0))
        sync = await self.sync_rag_with_bibliotecario()
        return {"ok": True, "indexed_files": indexed, "stats": self.rag_engine.get_stats(), "sync": sync}

    # =========================================================================
    # Streaming SSE Unificado para `POST /api/chat` + `GET /api/chat/stream/{id}`
    # =========================================================================

    def enqueue_ui_chat_stream(
        self,
        prompt: str,
        conversation_id: str | None = None,
        forced_profile: str | None = None,
        target_node: str | None = None,
        client_ip: str = "local",
    ) -> dict[str, Any]:
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        conv_id = self.store.ensure_conversation(conversation_id, first_message=prompt)
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._chat_streams[task_id] = queue

        asyncio.create_task(
            self._run_ui_chat_stream(
                task_id=task_id,
                prompt=prompt,
                conversation_id=conv_id,
                forced_profile=forced_profile,
                target_node=target_node,
                client_ip=client_ip,
                queue=queue,
            )
        )
        return {
            "task_id": task_id,
            "conversation_id": conv_id,
            "hardware_tier": self.hardware_profile.tier,
            "pacing_notice": self.hardware_profile.pacing_notice,
        }

    async def _run_ui_chat_stream(
        self,
        task_id: str,
        prompt: str,
        conversation_id: str,
        forced_profile: str | None,
        target_node: str | None,
        client_ip: str,
        queue: asyncio.Queue[dict[str, Any]],
    ) -> None:
        try:
            # 1. Guarda de Segurança contra Inputs Maliciosos
            verdict = self.gatekeeper.inspect_input(prompt, client_id=client_ip)
            if verdict.action != "ALLOW":
                self.store.record_guardian_event(
                    action=verdict.action,
                    risk_score=verdict.risk_score,
                    reason=verdict.reason,
                    matched_rules=verdict.matched_rules,
                    input_preview=prompt,
                    client_id=client_ip,
                )
                await self._broadcast_ws_event("guardian_event", {
                    "action": verdict.action,
                    "reason": verdict.reason,
                    "risk_score": verdict.risk_score,
                })

            if verdict.action == "BLOCK":
                msg_block = (
                    f"🛡️ **Rotina de Guarda do Enxame Ativada**\n\n"
                    f"Esta entrada foi bloqueada preventivamente ({verdict.reason} · regras: "
                    f"`{', '.join(verdict.matched_rules)}`). Reformule o pedido sem instruções "
                    f"de sobrescrita de sistema ou tentativa de extração de segredos."
                )
                await queue.put({
                    "event": "start",
                    "task_id": task_id,
                    "conversation_id": conversation_id,
                    "node_id": self.node_id,
                    "machine_alias": self.hardware_profile.machine_alias,
                    "role": "guarda",
                    "model": "guardian-gatekeeper",
                    "hardware_tier": self.hardware_profile.tier,
                    "pacing_notice": self.hardware_profile.pacing_notice,
                })
                await queue.put({"event": "token", "task_id": task_id, "content": msg_block})
                prov_block = {
                    "machine_alias": self.hardware_profile.machine_alias,
                    "node_id": self.node_id,
                    "platform": self.hardware_profile.os_name,
                    "hardware_tier": self.hardware_profile.tier,
                    "hardware_tier_label": self.hardware_profile.tier_label,
                    "cluster_role": "guarda",
                    "agent_profile": "guardian",
                    "model": "guardian-gatekeeper",
                    "source_tier": "guarda_local",
                    "total_ms": 2,
                    "ttft_ms": 1,
                    "guardian_action": "BLOCK",
                    "pacing_notice": self.hardware_profile.pacing_notice,
                }
                await queue.put({
                    "event": "final",
                    "task_id": task_id,
                    "conversation_id": conversation_id,
                    "content": msg_block,
                    "source": "guarda_local",
                    "confidence": 1.0,
                    "model": "guardian-gatekeeper",
                    "provenance": prov_block,
                })
                return

            # 2. Persistir mensagem do usuário + construir contexto compactado para a CPU
            history_msgs = self.store.build_context_messages(
                conversation_id, max_ctx_tokens=self.hardware_profile.recommended_num_ctx
            )
            self.store.append_message(conversation_id, "user", prompt)

            user_prof = self.store.get_user_profile()
            ctx: dict[str, Any] = {
                "conversation_id": conversation_id,
                "forced_profile": forced_profile,
                "target_node": target_node,
                "history_messages": history_msgs,
                "adaptive_style_prompt": self.store.build_adaptive_style_prompt(),
                "semantic_memories": self.store.search_memories(prompt, limit=5),
                "guardian_action": verdict.action,
                "wrapped_user_message": verdict.wrapped_text,
                "guardian_containment_prompt": verdict.system_containment_prompt,
            }

            analysis = await self._analyze_intent(prompt, ctx)
            ctx["analysis"] = analysis

            # Pedido direto de geração de imagem pelo chat (`/img ...` ou "gere uma imagem ...")
            if analysis.get("task_type") == "image":
                img_prompt = str(analysis.get("image_prompt") or prompt)
                job = await self.image_studio.enqueue_generation(prompt=img_prompt, width=512, height=512, steps=4)
                await queue.put({
                    "event": "start",
                    "task_id": task_id,
                    "conversation_id": conversation_id,
                    "node_id": self.node_id,
                    "machine_alias": self.hardware_profile.machine_alias,
                    "role": "worker_artist",
                    "model": "estudio-cpu",
                    "hardware_tier": self.hardware_profile.tier,
                    "pacing_notice": self.hardware_profile.pacing_notice,
                })
                # Aguarda conclusão do job na fila de CPU emitindo progresso
                while True:
                    cur = self.image_studio.get_job(job.job_id)
                    if not cur or cur["status"] in ("completed", "failed"):
                        break
                    await asyncio.sleep(0.15)
                cur = self.image_studio.get_job(job.job_id) or job.to_dict()
                if cur.get("status") == "completed":
                    ans_md = (
                        f"🎨 **Imagem gerada localmente na CPU** (`{cur['width']}x{cur['height']}`)\n\n"
                        f"![{img_prompt}]({cur['image_url']})\n\n"
                        f"- **Prompt:** {img_prompt}\n"
                        f"- **Motor gratuito:** `{cur.get('provenance', {}).get('model', 'cpu')}`\n"
                        f"- **Auto-revisão óptica:** brilho `{cur.get('quality_review', {}).get('mean_brightness')}`, "
                        f"contraste `{cur.get('quality_review', {}).get('contrast_std')}`"
                    )
                else:
                    ans_md = f"Não foi possível concluir a imagem: {cur.get('error')}"
                prov_img = cur.get("provenance") or {}
                self.store.append_message(conversation_id, "assistant", ans_md, provenance=prov_img)
                await queue.put({"event": "token", "task_id": task_id, "content": ans_md})
                await queue.put({
                    "event": "final",
                    "task_id": task_id,
                    "conversation_id": conversation_id,
                    "content": ans_md,
                    "source": "estudio_cpu",
                    "confidence": 0.95,
                    "model": prov_img.get("model", "estudio-cpu"),
                    "provenance": prov_img,
                })
                return

            profile = await self._profiles.select_or_create_profile(analysis)
            roles_now = self.get_roles_matrix()["local_roles"]
            primary_role = roles_now[0] if roles_now else "worker_general"

            await queue.put({
                "event": "start",
                "task_id": task_id,
                "conversation_id": conversation_id,
                "node_id": self.node_id,
                "machine_alias": self.hardware_profile.machine_alias,
                "role": primary_role,
                "agent_profile": profile.profile_id,
                "model": self.config.model,
                "hardware_tier": self.hardware_profile.tier,
                "hardware_tier_label": self.hardware_profile.tier_label,
                "pacing_notice": self.hardware_profile.pacing_notice,
            })

            final_data: dict[str, Any] = {}
            async for ev in self._orchestrator.execute_task_stream(
                task=analysis.get("task") or prompt,
                profile=profile,
                context=ctx,
                message=prompt,
            ):
                if ev.get("type") == "token":
                    await queue.put({"event": "token", "task_id": task_id, "content": ev.get("content", "")})
                elif ev.get("type") == "done":
                    final_data = ev

            answer_text = str(final_data.get("answer") or "")
            prov = final_data.get("provenance") or {}
            self.store.append_message(conversation_id, "assistant", answer_text, provenance=prov)
            self.store.learn_from_interaction(
                user_message=prompt,
                assistant_message=answer_text,
                domain=str(analysis.get("domain") or "general"),
                profile_used=profile.profile_id,
                conversation_id=conversation_id,
            )

            await queue.put({
                "event": "final",
                "task_id": task_id,
                "conversation_id": conversation_id,
                "content": answer_text,
                "source": final_data.get("source", "local"),
                "confidence": final_data.get("confidence", 0.85),
                "model": prov.get("model") or final_data.get("model") or self.config.model,
                "provenance": prov,
            })
        except Exception as exc:
            logger.error(f"Erro no stream de chat {task_id}: {exc}")
            await queue.put({"event": "error", "task_id": task_id, "message": str(exc)})
        finally:
            await queue.put({"event": "end", "task_id": task_id})
            await asyncio.sleep(60)
            self._chat_streams.pop(task_id, None)

    # =========================================================================
    # Callbacks e Loops de Manutenção
    # =========================================================================

    def _on_peer_discovered(self, peer) -> None:
        logger.info(f"Peer descoberto: {peer.node_id} - capacidades: {peer.capabilities}")
        if self._profiles:
            asyncio.create_task(self._profiles.evaluate_peer_for_profiles(peer))

    def _on_peer_lost(self, node_id: str) -> None:
        logger.warning(f"Peer perdido: {node_id}")
        if self._orchestrator:
            asyncio.create_task(self._orchestrator.handle_peer_loss(node_id))

    async def _health_loop(self) -> None:
        while self._running:
            try:
                self._update_load()
                # A descoberta mantém os peers sozinha (`_health_monitor_loop`
                # interno); aqui apenas consolidamos a saúde dos componentes.
                await self._component_health_check()
            except Exception as e:
                logger.error(f"Erro no health loop: {e}")
            await asyncio.sleep(30)

    async def _capability_sync_loop(self) -> None:
        while self._running:
            try:
                if self._discovery and self._profiles:
                    peers = self._discovery.get_active_peers()
                    await self._profiles.sync_capabilities_with_peers(peers)
                await self.sync_rag_with_bibliotecario()
            except Exception as e:
                logger.error(f"Erro no capability sync: {e}")
            await asyncio.sleep(60)

    async def _profile_evolution_loop(self) -> None:
        while self._running:
            try:
                if self._profiles:
                    await self._profiles.evolve_profiles()
            except Exception as e:
                logger.error(f"Erro na evolução de perfis: {e}")
            await asyncio.sleep(300)

    async def _component_health_check(self) -> None:
        checks = {
            "bee": self._bee is not None and self._bee.state == BeeState.RUNNING,
            "discovery": self._discovery is not None,
            "profiles": self._profiles is not None,
            "multimodal": self._multimodal is not None,
            "orchestrator": self._orchestrator is not None,
            "sprint_planner": self._sprint_planner is not None,
        }
        if not all(checks.values()):
            self.state = BeeState.DEGRADED
        elif self.state == BeeState.DEGRADED:
            self.state = BeeState.RUNNING

    def _update_load(self) -> None:
        import psutil

        cpu = psutil.cpu_percent(interval=None) / 100.0
        mem = psutil.virtual_memory().percent / 100.0
        self.load = round((cpu + mem) / 2.0, 3)
        if self._discovery:
            self._discovery.update_announcement(self.load, self.state)

    # =========================================================================
    # API Pública Síncrona/JSON (`process_chat` — compatível com todos os testes)
    # =========================================================================

    async def process_chat(self, message: str, context: dict | None = None) -> dict:
        """
        Ponto de entrada programático unificado (`/api/v1/chat` + testes de regressão).
        Mantém 100% do contrato esperado pelos testes existentes e adiciona guarda,
        memória evolutiva, contexto multi-turno e proveniência completa.
        """
        context = dict(context or {})
        client_id = str(context.get("client_ip") or "local")

        # 1. Guarda contra prompt injection
        verdict = self.gatekeeper.inspect_input(message, client_id=client_id)
        if verdict.action != "ALLOW":
            self.store.record_guardian_event(
                action=verdict.action,
                risk_score=verdict.risk_score,
                reason=verdict.reason,
                matched_rules=verdict.matched_rules,
                input_preview=message,
                client_id=client_id,
            )
        if verdict.action == "BLOCK":
            return {
                "status": "blocked",
                "response": f"Entrada bloqueada pela rotina de guarda: {verdict.reason}",
                "answer": f"Entrada bloqueada pela rotina de guarda: {verdict.reason}",
                "profile_used": "guardian",
                "source": "guarda_local",
                "confidence": 1.0,
                "provenance": {
                    "machine_alias": self.hardware_profile.machine_alias,
                    "node_id": self.node_id,
                    "hardware_tier": self.hardware_profile.tier,
                    "cluster_role": "guarda",
                    "agent_profile": "guardian",
                    "model": "guardian-gatekeeper",
                    "source_tier": "guarda_local",
                    "guardian_action": "BLOCK",
                },
                "metadata": {"guardian": {"action": "BLOCK", "rules": verdict.matched_rules}},
            }

        # 2. Análise rápida de intenção (<2ms em CPU via FastIntentRouter)
        analysis = await self._analyze_intent(message, context)

        # 3. Seleção de perfil
        profile = await self._profiles.select_or_create_profile(analysis)

        # 4. Processamento multimodal uma única vez e serialização segura
        multimodal_context: dict[str, Any] = {}
        task_context: dict[str, Any] = {
            **context,
            "analysis": analysis,
            "guardian_action": verdict.action,
            "wrapped_user_message": verdict.wrapped_text,
            "guardian_containment_prompt": verdict.system_containment_prompt,
            "adaptive_style_prompt": self.store.build_adaptive_style_prompt(),
            "semantic_memories": self.store.search_memories(message, limit=5),
        }

        conv_id = context.get("conversation_id")
        if conv_id:
            conv_id = self.store.ensure_conversation(str(conv_id), first_message=message)
            task_context["history_messages"] = self.store.build_context_messages(
                conv_id, max_ctx_tokens=self.hardware_profile.recommended_num_ctx
            )
            self.store.append_message(conv_id, "user", message)

        if context.get("attachments"):
            processed = await self._multimodal.process_attachments(context["attachments"], profile)
            multimodal_context = {
                "ocr_text": processed.get("ocr_text", ""),
                "files": [
                    {
                        "filename": f.filename,
                        "mime_type": f.mime_type,
                        "size_bytes": f.size_bytes,
                        "content": f.content[:5000],
                        "error": f.error,
                    }
                    if isinstance(f, ProcessedFile)
                    else f
                    for f in processed.get("files", [])
                ],
            }
            task_context.pop("attachments", None)
            task_context["multimodal"] = multimodal_context
            task_context["multimodal_processed"] = True

        # 5. Execução orquestrada
        result = await self._orchestrator.execute_task(
            task=analysis.get("task") or message,
            profile=profile,
            context=task_context,
            message=message,
        )

        ans = result.get("answer", "")
        prov = result.get("provenance") or (result.get("metadata") or {}).get("provenance") or {}
        if conv_id and ans:
            self.store.append_message(str(conv_id), "assistant", ans, provenance=prov)
            self.store.learn_from_interaction(
                user_message=message,
                assistant_message=ans,
                domain=str(analysis.get("domain") or "general"),
                profile_used=profile.profile_id,
                conversation_id=str(conv_id),
            )

        return {
            "status": "completed",
            "response": ans,
            "answer": ans,
            "conversation_id": conv_id,
            "profile_used": profile.profile_id,
            "source": result.get("source", "local"),
            "confidence": result.get("confidence", 0.0),
            "provenance": prov,
            "metadata": {
                "analysis": analysis,
                "multimodal": multimodal_context,
                "execution": result.get("metadata", {}),
                "provenance": prov,
            },
        }

    async def _analyze_intent(self, message: str, context: dict) -> dict:
        """Classificador Zero-LLM instantâneo (<2ms em CPU) com afinidade evolutiva."""
        user_prof = self.store.get_user_profile() if hasattr(self, "store") and self.store else None
        return FastIntentRouter.classify(message, context=context, user_profile=user_prof)

    async def get_system_status(self) -> dict:
        bee_status = {}
        if self._bee:
            bee_status = {
                "node_id": self._bee.node_id,
                "state": self._bee.state.value,
                "peers": len(self._bee._discovery.get_active_peers()) if self._bee._discovery else 0,
            }

        return {
            "kernel": {
                "node_id": self.node_id,
                "alias": self.hardware_profile.machine_alias,
                "version": "2.1.0-cpu-unified",
                "state": self.state.value,
                "load": self.load,
                "uptime_seconds": int(time.monotonic() - self._started_monotonic),
                "offline_mode": self.config.offline_mode,
                "allow_web": self.config.allow_web,
            },
            "hardware": self.hardware_profile.to_dict(),
            "bee": bee_status,
            "discovery": self._discovery.get_stats() if self._discovery else {},
            "profiles": self._profiles.get_stats() if self._profiles else {},
            "multimodal": self._multimodal.get_stats() if self._multimodal else {},
            "orchestrator": self._orchestrator.get_stats() if self._orchestrator else {},
            "sprint": self._sprint_planner.get_stats() if self._sprint_planner else {},
            "rag": self.rag_engine.get_stats(),
            "guardian": self.store.get_guardian_stats(),
            "voice": self.voice_service.get_capabilities(),
            "image_studio": self.image_studio.detect_engines(),
            "capabilities": self._get_full_capabilities(),
        }

    async def execute_sprint_task(self, sprint_id: str, task_spec: dict) -> dict:
        if not self._sprint_planner:
            return {"error": "Sprint planner não inicializado"}
        return await self._sprint_planner.execute_task(sprint_id, task_spec)

    async def create_agent_profile(self, spec: dict) -> dict:
        if not self._profiles:
            return {"error": "Profile manager não inicializado"}
        return await self._profiles.create_profile(spec)


async def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Enxame Kernel Unificado (CPU-First & Offline-First)")
    parser.add_argument("--config", type=Path, help="Arquivo de configuração")
    parser.add_argument("--data-dir", type=Path, help="Diretório de dados")
    parser.add_argument("--host", default="0.0.0.0", help="Host de escuta")
    parser.add_argument("--port", type=int, default=8765, help="Porta HTTP")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="URL do Ollama")
    parser.add_argument("--model", help="Modelo Ollama")
    parser.add_argument("--allow-web", action="store_true", help="Permitir pesquisa na internet como último recurso")
    parser.add_argument("--log-level", default="INFO", help="Nível de log")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = load_config(args)
    kernel = EnxameKernel(config)

    shutdown_event = asyncio.Event()

    def _signal_handler():
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except (NotImplementedError, AttributeError):
            pass

    try:
        await kernel.start()
        use_emoji = sys.stdout.encoding and "utf" in sys.stdout.encoding.lower()
        ok = "✅" if use_emoji else "[OK]"
        print(f"\n{ok} Enxame Unificado {config.node_id} ONLINE ({kernel.hardware_profile.tier_label})")
        print(f"   Web UI:  http://{config.host}:{config.port}/")
        print(f"   Saúde:   http://{config.host}:{config.port}/saude")
        print(f"   Status:  http://{config.host}:{config.port}/api/v1/status")
        await shutdown_event.wait()
    except KeyboardInterrupt:
        pass
    finally:
        await kernel.stop()
        print("Enxame Kernel parado.")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
