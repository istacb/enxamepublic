#!/usr/bin/env python3
"""
BEE-0001 — Standalone Bee Service
=================================
Uma Abelha autônoma que opera offline-first, descobre peers via mDNS,
e segue a política LOCAL -> ENXAME -> WEB.

Este é o ponto de entrada principal para executar uma Abelha standalone.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import signal
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

from core.exp.security import EXPSecurity

from .protocol.envelope import BeeEnvelope
from .protocol.handler import BeeProtocolHandler
from .protocol.messages import BeeMessageType, BeeState, BeeVisionRequest, BeeVisionResponse, BeeStateChange, BeePeerLost
from .librarian import LocalBeeLibrarian
from .memory import BeeMemory
from .discovery import BeeDiscoveryService
from .config import BeeConfig, load_config
from .capabilities.discovery import discover_capabilities
from .capabilities.selector import recommend_model
from .cluster import (
    ClusterMonitor,
    ClusterState,
    ClusterRole,
    load_cluster_state,
    save_cluster_state,
    elect_roles,
    InternetGate,
    InternetPurpose,
    GlobalIndex,
    build_global_index,
    start_monitoring,
    stop_monitoring,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bee")


class BeeService:
    """Serviço principal da Abelha - stand-alone, offline-first."""

    def __init__(self, config: BeeConfig) -> None:
        self.config = config
        self.node_id = config.node_id
        self.state = BeeState.STARTING

        self._security = EXPSecurity(config.shared_secret) if config.shared_secret else None
        self._handler = BeeProtocolHandler(
            node_id=self.node_id,
            shared_secret=config.shared_secret,
        )

        self._librarian: LocalBeeLibrarian | None = None
        self._memory: BeeMemory | None = None
        self._discovery: BeeDiscoveryService | None = None

        self._running = False
        self._tasks: list[asyncio.Task] = []

        self._register_protocol_handlers()

        # Capacidades descobertas (BEE-0003)
        self._capabilities: dict[str, Any] | None = None

        # Cluster (EIP-0009)
        self.cluster_state: ClusterState | None = None
        self.cluster_role: ClusterRole | None = None
        self._cluster_monitor: ClusterMonitor | None = None
        self._internet_gate: InternetGate | None = None
        self._global_index: GlobalIndex | None = None

    def _register_protocol_handlers(self) -> None:
        """Registra handlers para mensagens do protocolo BEE."""
        from .protocol.messages import (
            BeeHello,
            BeeHelloAck,
            BeeHeartbeat,
            BeeKnowledgeQuery,
            BeeKnowledgeResponse,
            BeeResearchRequest,
            BeeResearchResult,
            BeeModelRequest,
            BeeModelResponse,
            BeeCapabilityQuery,
            BeeCapabilityResponse,
            BeeStateChange,
            BeePeerLost,
        )

        self._handler.register_handler(BeeMessageType.HELLO, self._handle_hello)
        self._handler.register_handler(BeeMessageType.HELLO_ACK, self._handle_hello_ack)
        self._handler.register_handler(BeeMessageType.HEARTBEAT, self._handle_heartbeat)
        self._handler.register_handler(BeeMessageType.HEARTBEAT_ACK, self._handle_heartbeat_ack)
        self._handler.register_handler(BeeMessageType.KNOWLEDGE_QUERY, self._handle_knowledge_query)
        self._handler.register_handler(BeeMessageType.RESEARCH_REQUEST, self._handle_research_request)
        self._handler.register_handler(BeeMessageType.MODEL_REQUEST, self._handle_model_request)
        self._handler.register_handler(BeeMessageType.VISION_REQUEST, self._handle_vision_request)
        self._handler.register_handler(BeeMessageType.CAPABILITY_QUERY, self._handle_capability_query)
        self._handler.register_handler(BeeMessageType.STATE_CHANGE, self._handle_state_change)
        self._handler.register_handler(BeeMessageType.PEER_LOST, self._handle_peer_lost)

    async def start(self, *, start_http: bool = True, http_app: "web.Application | None" = None) -> None:
        """
        Inicializa todos os componentes da Abelha.
        
        Args:
            start_http: Se True, inicia servidor HTTP próprio.
                       Se False, usa http_app fornecido (para integração com EnxameKernel).
            http_app: Aplicação aiohttp externa para adicionar rotas da Abelha.
        """
        logger.info(f"Iniciando Abelha {self.node_id}...")

        # 1. Carregar identidade persistente
        await self._load_identity()

        # 2. Descobrir capacidades (BEE-0003) - hardware, Ollama, capacidades locais
        logger.info("Descobrindo capacidades do sistema...")
        self._capabilities = await discover_capabilities(
            enxame_data_path=str(self.config.data_dir),
            ollama_base_url=self.config.ollama_base_url,
        )
        
        # Selecionar melhor modelo baseado no hardware (BEE-0003 §9)
        if self._capabilities and self._capabilities.ollama and self._capabilities.ollama.available:
            hw = self._capabilities.hardware
            ollama = self._capabilities.ollama
            recommended = recommend_model(
                available_models=ollama.models,
                ram_gb=hw.ram_total_gb,
                gpu_vram_gb=hw.gpu_vram_gb,
                has_gpu=hw.gpu_available,
            )
            if recommended:
                self.config.model = recommended
                logger.info(f"Modelo recomendado pelo hardware: {recommended}")
            else:
                logger.warning("Nenhum modelo adequado encontrado, usando configuração padrão")

        # 3. Inicializar memória local (SQLite)
        self._memory = BeeMemory(self.config.data_dir / "memory.db")
        await self._memory.initialize()
        logger.info("Memória local inicializada")

        # 4. Inicializar Bibliotecário Local (RAG offline)
        self._librarian = LocalBeeLibrarian(
            data_dir=self.config.data_dir,
            ollama_url=self.config.ollama_base_url,
            model=self.config.model,
            memory=self._memory,
        )
        await self._librarian.initialize()
        logger.info("Bibliotecário local inicializado")

        # 5. Inicializar descoberta de peers (mDNS) com capacidades descobertas
        self._discovery = BeeDiscoveryService(
            node_id=self.node_id,
            host=self.config.host,
            port=self.config.port,
            capabilities=self._get_capabilities_list(),
            models=self._get_models_list(),
            on_peer_found=self._on_peer_discovered,
            on_peer_lost=self._on_peer_lost,
        )
        await self._discovery.start()
        logger.info("Descoberta mDNS iniciada")

        # 6. Anunciar presença via mDNS usando BeeDiscoveryService (não NodeAnnouncer)
        self._discovery.start_announcement()
        logger.info(f"Anunciando via mDNS em {self.config.host_ip}:{self.config.port}")

        # 7. Inicializar Cluster (EIP-0009) - aguardar descoberta inicial
        await self._initialize_cluster()

        # 8. Servidor HTTP
        self._own_http_server = False
        if start_http:
            if http_app is not None:
                # Modo integração: adicionar rotas da Abelha à app externa
                await self._add_routes_to_app(http_app)
            else:
                # Modo standalone: iniciar servidor próprio
                await self._start_http_server()
                self._own_http_server = True

        # 9. Iniciar loops de background
        self._running = True
        self._tasks = [
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._peer_maintenance_loop()),
            asyncio.create_task(self._load_metrics_loop()),
        ]

        self.state = BeeState.RUNNING
        logger.info(f"Abelha {self.node_id} ONLINE - Estado: RUNNING")

    async def stop(self) -> None:
        """Finaliza graceful da Abelha."""
        logger.info(f"Parando Abelha {self.node_id}...")
        self.state = BeeState.STOPPING
        self._running = False

        # Notificar peers sobre parada
        if self._handler:
            state_change = self._handler.create_state_change(
                new_state=BeeState.STOPPING,
                reason="shutdown",
                estimated_return_seconds=None,
            )
            # Broadcast para peers ativos
            if self._discovery:
                for peer in self._discovery.get_active_peers():
                    state_change.target_node_id = peer.node_id
                    await self._send_to_peer(peer, state_change)

        # Cancelar tasks de background
        for task in self._tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        # Parar monitoramento de cluster
        if self._cluster_monitor:
            await stop_monitoring(self._cluster_monitor)
            self._cluster_monitor = None

        # Parar servidor HTTP próprio (se iniciamos)
        if self._own_http_server and self._http_runner:
            await self._http_runner.cleanup()
            self._http_runner = None

        # Parar anúncio mDNS
        if self._discovery:
            self._discovery.stop_announcement()

        # Parar descoberta
        if self._discovery:
            await self._discovery.stop()

        # Fechar bibliotecário
        if self._librarian:
            await self._librarian.close()

        # Fechar memória
        if self._memory:
            await self._memory.close()

        self.state = BeeState.STOPPED
        logger.info(f"Abelha {self.node_id} OFFLINE")

    async def _initialize_cluster(self) -> None:
        """Inicializa cluster: carrega estado, elege papéis se 3+ peers, inicia monitoramento."""
        # Carregar estado persistido
        self.cluster_state = load_cluster_state(self.config.data_dir)
        
        # Aguardar descoberta inicial de peers (2s)
        await asyncio.sleep(2)
        
        peers = []
        if self._discovery:
            peers = self._discovery.get_active_peers()
        
        logger.info(f"Peers descobertos para cluster: {len(peers)}")
        
        if len(peers) >= 3:
            # Eleger papéis
            self.cluster_state = elect_roles(peers, self.cluster_state)
            self.cluster_role = self.cluster_state.get_role(self.node_id)
            
            # Determinar se é Worker Artist
            if self.cluster_role == ClusterRole.WORKER and self.node_id in self.cluster_state.artist_workers:
                self.cluster_role = ClusterRole.WORKER_ARTIST
            
            logger.info(f"Cluster eleito: Juiz={self.cluster_state.juiz_id}, Bib={self.cluster_state.bibliotecario_id}, Guarda={self.cluster_state.guarda_id}, Workers={len(self.cluster_state.workers)}")
            logger.info(f"Meu papel: {self.cluster_role.value}")
            
            # Salvar estado
            save_cluster_state(self.config.data_dir, self.cluster_state)
            
            # Inicializar InternetGate
            self._internet_gate = InternetGate(self.cluster_state, self.node_id)
            
            # Se sou Bibliotecário, construir índice global
            if self.cluster_role == ClusterRole.BIBLIOTECARIO:
                self._global_index = await build_global_index(self, peers)
                self.cluster_state.global_index = self._global_index.data
                save_cluster_state(self.config.data_dir, self.cluster_state)
            
            # Iniciar monitoramento de failover
            self._cluster_monitor = await start_monitoring(
                self, self.cluster_state, save_cluster_state, check_interval=60.0
            )
        else:
            logger.info(f"Menos de 3 peers ({len(peers)}), operando como standalone")
            self.cluster_role = ClusterRole.WORKER
            if self.node_id in (self.cluster_state.artist_workers if self.cluster_state else []):
                self.cluster_role = ClusterRole.WORKER_ARTIST

    def _get_capabilities_list(self) -> list[str]:
        """Retorna lista de capabilities da Abelha baseada em descoberta BEE-0003."""
        if not self._capabilities:
            # Fallback básico
            caps = ["rag", "vector_search", "embeddings", "query", "index", "memory"]
        else:
            caps = self._capabilities.to_manifesto_dict().get("capabilities", [])
            # Adicionar capabilities básicas se não estiverem
            for base in ["rag", "vector_search", "embeddings", "query", "index", "memory"]:
                if base not in caps:
                    caps.append(base)
        
        if self._librarian and self._librarian.has_ocr():
            if "ocr" not in caps:
                caps.append("ocr")
        if self._librarian and self._librarian.has_vision():
            if "vision" not in caps:
                caps.append("vision")
        if self._librarian and self._librarian.has_zim():
            if "zim" not in caps:
                caps.append("zim")
        if self.config.allow_web:
            if "web_fallback" not in caps:
                caps.append("web_fallback")
        return caps

    def _get_models_list(self) -> list[str]:
        """Retorna lista de modelos disponíveis baseada em descoberta BEE-0003."""
        if self._capabilities and self._capabilities.ollama and self._capabilities.ollama.available:
            return self._capabilities.to_manifesto_dict().get("models", [])
        if self._librarian:
            return self._librarian.get_available_models()
        return []

    def _on_peer_discovered(self, peer: "DiscoveredPeer") -> None:
        """Callback quando novo peer é descoberto."""
        logger.info(f"Peer descoberto: {peer.node_id} ({peer.role}) em {peer.host}:{peer.port}")

    def _on_peer_lost(self, node_id: str) -> None:
        """Callback quando peer é perdido."""
        logger.warning(f"Peer perdido: {node_id}")

    async def _load_identity(self) -> None:
        """Carrega ou gera identidade persistente."""
        identity_file = self.config.data_dir / "identity.json"
        if identity_file.exists():
            import json
            with open(identity_file) as f:
                data = json.load(f)
            self.node_id = data.get("node_id", self.node_id)
            logger.info(f"Identidade carregada: {self.node_id}")
        else:
            # Identidade já foi gerada no config
            logger.info(f"Nova identidade: {self.node_id}")

    async def _start_http_server(self) -> None:
        """Inicia servidor HTTP para API e WebSocket."""
        from aiohttp import web
        from aiohttp.web import Request, Response

        app = web.Application()

        # Health check
        async def health(request: Request) -> Response:
            return web.json_response({
                "status": "ok",
                "node_id": self.node_id,
                "state": self.state.value,
                "peers": len(self._discovery.get_active_peers()) if self._discovery else 0,
            })

        # Query endpoint (processa LOCAL -> ENXAME -> WEB)
        async def query(request: Request) -> Response:
            try:
                data = await request.json()
                query_text = data.get("query", "").strip()
                if not query_text:
                    return web.json_response({"error": "query required"}, status=400)

                result = await self.process_query(query_text)
                return web.json_response(result)
            except Exception as e:
                logger.error(f"Erro no query: {e}")
                return web.json_response({"error": str(e)}, status=500)

        # Capabilities endpoint
        async def capabilities(request: Request) -> Response:
            return web.json_response({
                "capabilities": self._get_capabilities_list(),
                "models": self._get_models_list(),
                "indexes": ["documents"] if self._librarian else [],
                "load": self._calculate_load(),
            })

        # Peer discovery endpoint
        async def peers(request: Request) -> Response:
            if not self._discovery:
                return web.json_response({"peers": []})
            peers = self._discovery.get_active_peers()
            return web.json_response({"peers": [
                {
                    "node_id": p.node_id,
                    "role": p.role,
                    "host": p.host,
                    "port": p.port,
                    "capabilities": p.capabilities,
                    "models": p.models,
                }
                for p in peers
            ]})

        app.router.add_get("/health", health)
        app.router.add_post("/api/v1/query", query)
        app.router.add_get("/api/v1/capabilities", capabilities)
        app.router.add_get("/api/v1/peers", peers)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.config.host, self.config.port)
        await site.start()
        logger.info(f"Servidor HTTP iniciado em {self.config.host}:{self.config.port}")

        self._http_runner = runner

    async def _add_routes_to_app(self, app: "web.Application") -> None:
        """Adiciona rotas da Abelha a uma aplicação aiohttp externa (para EnxameKernel)."""
        from aiohttp.web import Request, Response

        # Health check
        async def health(request: Request) -> Response:
            return web.json_response({
                "status": "ok",
                "node_id": self.node_id,
                "state": self.state.value,
                "peers": len(self._discovery.get_active_peers()) if self._discovery else 0,
            })

        # Query endpoint (processa LOCAL -> ENXAME -> WEB)
        async def query(request: Request) -> Response:
            try:
                data = await request.json()
                query_text = data.get("query", "").strip()
                if not query_text:
                    return web.json_response({"error": "query required"}, status=400)

                result = await self.process_query(query_text)
                return web.json_response(result)
            except Exception as e:
                logger.error(f"Erro no query: {e}")
                return web.json_response({"error": str(e)}, status=500)

        # Capabilities endpoint
        async def capabilities(request: Request) -> Response:
            caps = self._get_capabilities_list()
            if self.cluster_state:
                caps.append("cluster")
            return web.json_response({
                "capabilities": caps,
                "models": self._get_models_list(),
                "indexes": ["documents"] if self._librarian else [],
                "load": self._calculate_load(),
            })

        # Cluster status endpoint (EIP-0009)
        async def cluster_status(request: Request) -> Response:
            if not self.cluster_state:
                return web.json_response({
                    "cluster": False,
                    "message": "Operando como standalone (menos de 3 peers)"
                })
            
            return web.json_response({
                "cluster": True,
                "epoch": self.cluster_state.epoch,
                "my_role": self.cluster_role.value if self.cluster_role else "unknown",
                "roles": {
                    "juiz": self.cluster_state.juiz_id,
                    "bibliotecario": self.cluster_state.bibliotecario_id,
                    "guarda": self.cluster_state.guarda_id,
                    "workers": self.cluster_state.workers,
                    "artist_workers": self.cluster_state.artist_workers,
                },
                "secondary_roles": {
                    k: [r.value for r in v] for k, v in self.cluster_state.secondary_roles.items()
                },
                "juiz_failover_active": self.cluster_state.is_juiz_failover_active(),
                "juiz_failover_elapsed_hours": round(self.cluster_state.get_juiz_failover_elapsed_hours(), 2),
                "global_index_stats": {
                    "domains": len(self.cluster_state.global_index),
                    "entries": sum(len(v) for v in self.cluster_state.global_index.values()),
                },
                "internet_access": [p.value for p in self._internet_gate.get_allowed_purposes()] if self._internet_gate else [],
            })

        # Peer discovery endpoint
        async def peers(request: Request) -> Response:
            if not self._discovery:
                return web.json_response({"peers": []})
            peers = self._discovery.get_active_peers()
            return web.json_response({"peers": [
                {
                    "node_id": p.node_id,
                    "role": p.role,
                    "host": p.host,
                    "port": p.port,
                    "capabilities": p.capabilities,
                    "models": p.models,
                }
                for p in peers
            ]})

        app.router.add_get("/health", health)
        app.router.add_post("/api/v1/query", query)
        app.router.add_get("/api/v1/capabilities", capabilities)
        app.router.add_get("/api/v1/cluster", cluster_status)
        app.router.add_get("/api/v1/peers", peers)
        
        logger.info("Rotas da Abelha registradas na aplicação externa")

    def _calculate_load(self) -> float:
        """Calcula carga atual da Abelha (0.0 a 1.0)."""
        import psutil
        cpu = psutil.cpu_percent(interval=0.1) / 100.0
        mem = psutil.virtual_memory().percent / 100.0
        return (cpu + mem) / 2.0

    # =========================================================================
    # Handlers do Protocolo BEE
    # =========================================================================

    async def _handle_hello(self, envelope: BeeEnvelope) -> BeeEnvelope:
        """Handler para HELLO - handshake inicial."""
        from .protocol.messages import BeeHello, BeeHelloAck, BeeIdentity, BeeManifesto
        import secrets

        hello = BeeHello.from_dict(envelope.payload)
        logger.info(f"HELLO recebido de {hello.identity.node_id}")

        # Gerar nonce para resposta
        nonce = secrets.token_urlsafe(16)

        # Criar nosso manifesto
        manifesto = BeeManifesto(
            capabilities=self._get_capabilities_list(),
            models=self._get_models_list(),
            indexes=["documents"] if self._librarian else [],
            load=self._calculate_load(),
            uptime_seconds=int(asyncio.get_event_loop().time()),
            version="1.0.0",
        )

        hello_ack = BeeHelloAck(
            identity=BeeIdentity(node_id=self.node_id, protocol_version="1.0"),
            manifesto=manifesto,
            nonce=nonce,
            echo_nonce=hello.nonce,
        )

        return self._handler.create_hello_ack(
            target_node_id=envelope.source_node_id,
            manifesto=manifesto,
            nonce=nonce,
            echo_nonce=hello.nonce,
            correlation_id=envelope.correlation_id or envelope.msg_id,
        )

    async def _handle_hello_ack(self, envelope: BeeEnvelope) -> BeeEnvelope | None:
        """Handler para HELLO_ACK - resposta do handshake."""
        from .protocol.messages import BeeHelloAck
        hello_ack = BeeHelloAck.from_dict(envelope.payload)
        logger.info(f"HELLO_ACK recebido de {hello_ack.identity.node_id}")
        # Armazenar manifesto do peer
        if self._discovery:
            await self._discovery.update_peer_manifesto(envelope.source_node_id, hello_ack.manifesto)
        return None

    async def _handle_heartbeat(self, envelope: BeeEnvelope) -> BeeEnvelope:
        """Handler para HEARTBEAT."""
        from .protocol.messages import BeeHeartbeat
        heartbeat = BeeHeartbeat.from_dict(envelope.payload)

        if self._discovery:
            await self._discovery.update_peer_heartbeat(
                envelope.source_node_id,
                heartbeat.state,
                heartbeat.load,
                heartbeat.sequence,
            )

        return self._handler.create_heartbeat_ack(
            target_node_id=envelope.source_node_id,
            ack_sequence=heartbeat.sequence,
            load=self._calculate_load(),
        )

    async def _handle_heartbeat_ack(self, envelope: BeeEnvelope) -> BeeEnvelope | None:
        """Handler para HEARTBEAT_ACK."""
        from .protocol.messages import BeeHeartbeatAck
        ack = BeeHeartbeatAck.from_dict(envelope.payload)
        if self._discovery:
            await self._discovery.confirm_heartbeat(envelope.source_node_id, ack.ack_sequence)
        return None

    async def _handle_knowledge_query(self, envelope: BeeEnvelope) -> BeeEnvelope:
        """Handler para KNOWLEDGE_QUERY - consulta leve de conhecimento."""
        from .protocol.messages import BeeKnowledgeQuery
        query = BeeKnowledgeQuery.from_dict(envelope.payload)

        has_knowledge = False
        confidence = 0.0
        document_count = 0
        topics = []

        if self._librarian:
            # Verificação rápida sem RAG completo
            result = await self._librarian.quick_knowledge_check(query.subject, query.keywords)
            has_knowledge = result.get("has_knowledge", False)
            confidence = result.get("confidence", 0.0)
            document_count = result.get("document_count", 0)
            topics = result.get("topics", [])

        return self._handler.create_knowledge_response(
            target_node_id=envelope.source_node_id,
            query_id=query.query_id,
            has_knowledge=has_knowledge,
            confidence=confidence,
            document_count=document_count,
            topics=topics,
            correlation_id=envelope.correlation_id,
        )

    async def _handle_research_request(self, envelope: BeeEnvelope) -> BeeEnvelope:
        """Handler para RESEARCH_REQUEST - pesquisa completa com RAG."""
        from .protocol.messages import BeeResearchRequest, ResearchResultItem
        request = BeeResearchRequest.from_dict(envelope.payload)

        results = []
        if self._librarian:
            search_result = await self._librarian.search(request.query, request.max_results)
            for item in search_result.get("results", []):
                results.append(ResearchResultItem(
                    content=item.get("content", ""),
                    source=item.get("source"),
                    confidence=item.get("confidence", 0.0),
                    page=item.get("page"),
                    metadata=item.get("metadata", {}),
                ))

        return self._handler.create_research_result(
            target_node_id=envelope.source_node_id,
            request_id=request.request_id,
            results=results,
            total_results=len(results),
            processing_time_ms=search_result.get("latency_ms", 0) if "search_result" in locals() else 0,
            model_used=self.config.model,
            correlation_id=envelope.correlation_id,
        )

    async def _handle_model_request(self, envelope: BeeEnvelope) -> BeeEnvelope:
        """Handler para MODEL_REQUEST - inferência usando modelo local."""
        from .protocol.messages import BeeModelRequest
        request = BeeModelRequest.from_dict(envelope.payload)

        generation = ""
        if self._librarian:
            result = await self._librarian.generate(
                request.prompt,
                request.system_prompt,
                request.max_tokens,
                request.temperature,
            )
            generation = result.get("generation", "")

        return self._handler.create_model_response(
            target_node_id=envelope.source_node_id,
            request_id=request.request_id,
            generation=generation,
            model_used=self.config.model,
            correlation_id=envelope.correlation_id,
        )

    async def _handle_vision_request(self, envelope: BeeEnvelope) -> BeeEnvelope:
        """Handler para VISION_REQUEST - análise de imagem usando modelo de visão."""
        from .protocol.messages import BeeVisionRequest
        request = BeeVisionRequest.from_dict(envelope.payload)

        description = ""
        model_used = None
        error = None
        processing_time_ms = 0

        if self._librarian:
            import time
            start = time.perf_counter()
            try:
                image_bytes = base64.b64decode(request.image_base64)
                if request.structured_output:
                    result = await self._librarian.analyze_image_with_structured_output(image_bytes)
                else:
                    result = await self._librarian.analyze_image(
                        image_bytes,
                        request.prompt,
                        request.system_prompt,
                    )
                description = result.get("description", "")
                model_used = result.get("model")
                error = result.get("error")
            except Exception as e:
                error = str(e)
                logger.error(f"Erro na visão: {e}")
            processing_time_ms = int((time.perf_counter() - start) * 1000)

        return self._handler.create_vision_response(
            target_node_id=envelope.source_node_id,
            request_id=request.request_id,
            description=description,
            model_used=model_used,
            processing_time_ms=processing_time_ms,
            error=error,
            correlation_id=envelope.correlation_id,
        )

    async def _handle_capability_query(self, envelope: BeeEnvelope) -> BeeEnvelope:
        """Handler para CAPABILITY_QUERY."""
        from .protocol.messages import BeeCapabilityQuery
        query = BeeCapabilityQuery.from_dict(envelope.payload)

        has_cap = query.capability in self._get_capabilities_list()

        return self._handler.create_capability_response(
            target_node_id=envelope.source_node_id,
            has_capability=has_cap,
            confidence=1.0 if has_cap else 0.0,
            document_count=0,
            correlation_id=envelope.correlation_id,
        )

    async def _handle_state_change(self, envelope: BeeEnvelope) -> BeeEnvelope | None:
        """Handler para STATE_CHANGE - notificação de mudança de estado de peer."""
        from .protocol.messages import BeeStateChange, BeeState
        state_change = BeeStateChange.from_dict(envelope.payload)
        logger.info(f"Peer {state_change.node_id} mudou para estado: {state_change.new_state.value} - {state_change.reason}")
        
        # Atualizar peer no discovery
        if self._discovery and state_change.node_id in self._discovery._peers:
            peer = self._discovery._peers[state_change.node_id]
            peer.state = state_change.new_state
            if state_change.new_state == BeeState.STOPPING:
                # Peer vai parar, remover após timeout estimado
                pass
        
        # Cluster-specific handling (EIP-0009)
        if self.cluster_state and state_change.reason in ("juiz_failover", "juiz_restored", "new_election"):
            if state_change.reason == "juiz_failover":
                logger.warning(f"Failover de Juiz detectado: {state_change.node_id} assumiu")
                # Atualizar estado local se necessário
            elif state_change.reason == "juiz_restored":
                logger.info(f"Juiz original restaurado: {state_change.node_id}")
            elif state_change.reason == "new_election":
                logger.info(f"Nova eleição no cluster detectada")
                # Forçar re-eleição local na próxima verificação
                self.cluster_state.epoch = 0  # Marcar para re-eleição
        
        return None

    async def _handle_peer_lost(self, envelope: BeeEnvelope) -> BeeEnvelope | None:
        """Handler para PEER_LOST - notificação de peer perdido."""
        from .protocol.messages import BeePeerLost
        peer_lost = BeePeerLost.from_dict(envelope.payload)
        logger.warning(f"Peer perdido notificado: {peer_lost.node_id} - {peer_lost.reason}")
        
        # Remover peer do discovery se estiver lá
        if self._discovery:
            self._discovery._remove_peer(peer_lost.node_id)
        return None

    # =========================================================================
    # Loops de Background
    # =========================================================================

    async def _heartbeat_loop(self) -> None:
        """Envia heartbeats periódicos para peers ativos."""
        while self._running:
            try:
                if self._discovery:
                    peers = self._discovery.get_active_peers()
                    load = self._calculate_load()
                    for peer in peers:
                        envelope = self._handler.create_heartbeat()
                        # Atualizar load no heartbeat
                        envelope.payload["load"] = load
                        await self._send_to_peer(peer, envelope)
            except Exception as e:
                logger.error(f"Erro no heartbeat loop: {e}")
            await asyncio.sleep(self.config.heartbeat_interval)

    async def _peer_maintenance_loop(self) -> None:
        """Mantém lista de peers ativos, remove inativos."""
        while self._running:
            try:
                if self._discovery:
                    await self._discovery.cleanup_stale_peers()
            except Exception as e:
                logger.error(f"Erro no peer maintenance: {e}")
            await asyncio.sleep(30)

    async def _load_metrics_loop(self) -> None:
        """Atualiza métricas de carga e reanuncia via mDNS."""
        while self._running:
            try:
                load = self._calculate_load()
                # Atualizar anúncio mDNS com nova carga via BeeDiscoveryService
                if self._discovery:
                    self._discovery.update_announcement(load, self.state)
            except Exception as e:
                logger.error(f"Erro no load metrics: {e}")
            await asyncio.sleep(60)

    async def _send_to_peer(self, peer: "DiscoveredPeer", envelope: BeeEnvelope) -> None:
        """Envia envelope para peer via HTTP."""
        try:
            import aiohttp
            url = f"http://{peer.host}:{peer.port}/api/v1/bee/message"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=envelope.to_dict(), timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        response_envelope = BeeEnvelope.from_dict(data)
                        self._handler.complete_pending_request(envelope.correlation_id or envelope.msg_id, response_envelope)
        except Exception as e:
            logger.debug(f"Falha ao enviar para {peer.node_id}: {e}")

    # =========================================================================
    # Pipeline de Query: LOCAL -> ENXAME -> WEB
    # =========================================================================

    async def process_query(self, query: str) -> dict[str, Any]:
        """
        Processa query seguindo a política LOCAL -> ENXAME -> WEB (com cluster).
        
        Returns:
            dict com answer, source, confidence, metadata
        """
        logger.info(f"Processando query: {query[:100]}...")

        # 1. LOCAL - Memória semântica + RAG local
        local_result = await self._query_local(query)
        if local_result["confidence"] >= self.config.confidence_threshold_enxame:
            return {"answer": local_result["answer"], "source": "local", **local_result}

        # 2. ENXAME - Consultar peers se disponíveis
        if self._discovery and self._discovery.get_active_peers():
            enxame_result = await self._query_enxame(query)
            if enxame_result["confidence"] >= self.config.confidence_threshold_web:
                return {"answer": enxame_result["answer"], "source": "enxame", **enxame_result}

        # 3. WEB - Fallback se habilitado E papel permite (EIP-0009)
        if self.config.allow_web and self._librarian and self._internet_gate:
            if self._internet_gate.can_access(InternetPurpose.BIBLIOTECARIO_FALLBACK):
                web_result = await self._librarian.search_web(query)
                return {"answer": web_result.get("answer", ""), "source": "web", **web_result}
            else:
                logger.debug(f"Node {self.node_id} sem permissão de acesso à internet para fallback")

        # Fallback: melhor resultado disponível
        return {
            "answer": local_result.get("answer", "Não encontrei informação relevante."),
            "source": "local",
            "confidence": local_result.get("confidence", 0.0),
            "fallback": True,
        }

    async def _query_local(self, query: str) -> dict[str, Any]:
        """Consulta fontes locais: memória + RAG."""
        # 1. Memória semântica
        if self._memory:
            mem_result = await self._memory.search_semantic(query)
            if mem_result and mem_result.get("confidence", 0) > 0.8:
                return {"answer": mem_result["response"], "confidence": mem_result["confidence"], "source_type": "memory"}

        # 2. RAG local via Bibliotecário
        if self._librarian:
            result = await self._librarian.search(query)
            return {
                "answer": result.get("answer", ""),
                "confidence": result.get("confidence", 0.0),
                "source_type": "rag",
                "metadata": result.get("metadata", {}),
            }

        return {"answer": "", "confidence": 0.0, "source_type": "none"}

    async def _query_enxame(self, query: str) -> dict[str, Any]:
        """Consulta peers via protocolo BEE usando índice global do Bibliotecário."""
        if not self._discovery:
            return {"answer": "", "confidence": 0.0}

        peers = self._discovery.get_active_peers()
        if not peers:
            return {"answer": "", "confidence": 0.0}

        # 1. Se temos índice global (sou Bibliotecário ou recebi do Bibliotecário), usar para rotear
        target_peers = []
        if self._global_index:
            target_peers = self._global_index.get_peers_for_subject(query, min_confidence=0.5)
            target_peer_ids = [pk.peer_id for pk in target_peers]
            # Filtrar peers ativos
            target_peers = [p for p in peers if p.node_id in target_peer_ids]
            logger.debug(f"Roteando via índice global: {len(target_peers)} peers alvo para '{query}'")
        elif self.cluster_state and self.cluster_state.bibliotecario_id:
            # Consultar Bibliotecário para saber onde buscar
            bib_peer = next((p for p in peers if p.node_id == self.cluster_state.bibliotecario_id), None)
            if bib_peer:
                from .cluster.global_index import query_bibliotecario_where
                target_ids = await query_bibliotecario_where(bib_peer, query, self._global_index)
                target_peers = [p for p in peers if p.node_id in target_ids]
                logger.debug(f"Roteando via Bibliotecário: {len(target_peers)} peers alvo para '{query}'")
        
        # Se não temos roteamento, consultar todos
        if not target_peers:
            target_peers = peers

        # 2. KNOWLEDGE_QUERY para filtrar peers relevantes
        best_peer = None
        best_confidence = 0.0

        for peer in target_peers:
            envelope = self._handler.create_knowledge_query(
                target_node_id=peer.node_id,
                subject=query,
                timeout_ms=2000,
            )
            try:
                response = await self._send_with_response(envelope, peer, timeout_ms=3000)
                if response and response.msg_type == BeeMessageType.KNOWLEDGE_RESPONSE:
                    from .protocol.messages import BeeKnowledgeResponse
                    kq_resp = BeeKnowledgeResponse.from_dict(response.payload)
                    if kq_resp.has_knowledge and kq_resp.confidence > best_confidence:
                        best_confidence = kq_resp.confidence
                        best_peer = peer
            except Exception as e:
                logger.debug(f"Erro consultando peer {peer.node_id}: {e}")
                continue

        # 3. Se encontrou peer relevante, fazer RESEARCH_REQUEST
        if best_peer:
            envelope = self._handler.create_research_request(
                target_node_id=best_peer.node_id,
                query=query,
            )
            try:
                response = await self._send_with_response(envelope, best_peer, timeout_ms=35000)
                if response and response.msg_type == BeeMessageType.RESEARCH_RESULT:
                    from .protocol.messages import BeeResearchResult
                    rr = BeeResearchResult.from_dict(response.payload)
                    if rr.results:
                        answer_parts = [r.content for r in rr.results[:3]]
                        return {
                            "answer": "\n\n".join(answer_parts),
                            "confidence": 0.85,
                            "source": "enxame",
                            "peer": best_peer.node_id,
                            "metadata": {
                                "total_results": rr.total_results,
                                "processing_time_ms": rr.processing_time_ms,
                                "model_used": rr.model_used,
                            },
                        }
            except Exception as e:
                logger.debug(f"Erro em research request para {best_peer.node_id}: {e}")

        return {"answer": "", "confidence": best_confidence}

    async def _send_with_response(self, envelope: BeeEnvelope, peer: "DiscoveredPeer", timeout_ms: int = 5000) -> BeeEnvelope | None:
        """Envia envelope para peer e aguarda resposta via HTTP/WebSocket."""
        try:
            import aiohttp
            url = f"http://{peer.host}:{peer.port}/api/v1/bee/message"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    json=envelope.to_dict(), 
                    timeout=aiohttp.ClientTimeout(total=timeout_ms / 1000)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return BeeEnvelope.from_dict(data)
        except Exception as e:
            logger.debug(f"Falha ao enviar para {peer.node_id}: {e}")
        return None


async def main() -> int:
    parser = argparse.ArgumentParser(description="ENXAME Bee - Abelha Standalone")
    parser.add_argument("--config", type=Path, help="Arquivo de configuração")
    parser.add_argument("--data-dir", type=Path, help="Diretório de dados")
    parser.add_argument("--host", default="0.0.0.0", help="Host de escuta")
    parser.add_argument("--port", type=int, default=8765, help="Porta HTTP")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="URL do Ollama")
    parser.add_argument("--model", help="Modelo Ollama a usar")
    parser.add_argument("--allow-web", action="store_true", help="Permitir fallback web")
    parser.add_argument("--shared-secret", help="Segredo compartilhado para HMAC")
    parser.add_argument("--log-level", default="INFO", help="Nível de log")
    args = parser.parse_args()

    logging.getLogger().setLevel(args.log_level)

    # Carregar configuração
    config = load_config(args)

    # Criar e iniciar serviço
    bee = BeeService(config)

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(bee.stop()))

    try:
        await bee.start()
        # Manter rodando
        while bee._running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await bee.stop()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))