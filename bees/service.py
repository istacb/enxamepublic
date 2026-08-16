#!/usr/bin/env python3
"""
BEE-0001 — Standalone Bee Service
=================================
Uma Abelha autônoma que opera offline-first, descobre peers via mDNS,
e segue a política LOCAL -> ENXAME -> WEB.

Este é o ponto de entrada principal para executar uma Abelha standalone.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

from core.discovery.mdns_discovery import NodeAnnouncer, NodeListener, DiscoveredNode
from core.exp.security import EXPSecurity

from .protocol.envelope import BeeEnvelope
from .protocol.handler import BeeProtocolHandler
from .protocol.messages import BeeMessageType, BeeState
from .librarian import LocalBeeLibrarian
from .memory import BeeMemory
from .discovery import BeeDiscoveryService
from .config import BeeConfig, load_config

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
        self._announcer: NodeAnnouncer | None = None
        self._listener: NodeListener | None = None

        self._running = False
        self._tasks: list[asyncio.Task] = []

        self._register_protocol_handlers()

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
        )

        self._handler.register_handler(BeeMessageType.HELLO, self._handle_hello)
        self._handler.register_handler(BeeMessageType.HELLO_ACK, self._handle_hello_ack)
        self._handler.register_handler(BeeMessageType.HEARTBEAT, self._handle_heartbeat)
        self._handler.register_handler(BeeMessageType.HEARTBEAT_ACK, self._handle_heartbeat_ack)
        self._handler.register_handler(BeeMessageType.KNOWLEDGE_QUERY, self._handle_knowledge_query)
        self._handler.register_handler(BeeMessageType.RESEARCH_REQUEST, self._handle_research_request)
        self._handler.register_handler(BeeMessageType.MODEL_REQUEST, self._handle_model_request)
        self._handler.register_handler(BeeMessageType.CAPABILITY_QUERY, self._handle_capability_query)

    async def start(self) -> None:
        """Inicializa todos os componentes da Abelha."""
        logger.info(f"Iniciando Abelha {self.node_id}...")

        # 1. Carregar identidade persistente
        await self._load_identity()

        # 2. Inicializar memória local (SQLite)
        self._memory = BeeMemory(self.config.data_dir / "memory.db")
        await self._memory.initialize()
        logger.info("Memória local inicializada")

        # 3. Inicializar Bibliotecário Local (RAG offline)
        self._librarian = LocalBeeLibrarian(
            data_dir=self.config.data_dir,
            ollama_url=self.config.ollama_base_url,
            model=self.config.model,
            memory=self._memory,
        )
        await self._librarian.initialize()
        logger.info("Bibliotecário local inicializado")

        # 4. Inicializar descoberta de peers (mDNS)
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

        # 5. Anunciar presença via mDNS
        self._announcer = NodeAnnouncer(
            node_id=self.node_id,
            role="bee",
            host_ip=self.config.host_ip,
            port=self.config.port,
            capabilities=",".join(self._get_capabilities_list()),
            models=",".join(self._get_models_list()),
        )
        self._announcer.start()
        logger.info(f"Anunciando via mDNS em {self.config.host_ip}:{self.config.port}")

        # 6. Iniciar servidor HTTP para API e WebSocket
        await self._start_http_server()

        # 7. Iniciar loops de background
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

        # Cancelar tasks de background
        for task in self._tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        # Parar anunciações
        if self._announcer:
            self._announcer.stop()

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

    def _get_capabilities_list(self) -> list[str]:
        """Retorna lista de capabilities da Abelha."""
        caps = ["rag", "vector_search", "embeddings", "query", "index"]
        if self._librarian and self._librarian.has_ocr():
            caps.append("ocr")
        if self._librarian and self._librarian.has_zim():
            caps.append("zim")
        if self.config.allow_web:
            caps.append("web_fallback")
        return caps

    def _get_models_list(self) -> list[str]:
        """Retorna lista de modelos disponíveis."""
        if self._librarian:
            return self._librarian.get_available_models()
        return []

    def _on_peer_discovered(self, peer: DiscoveredNode) -> None:
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

    # =========================================================================
    # Loops de Background
    # =========================================================================

    async def _heartbeat_loop(self) -> None:
        """Envia heartbeats periódicos para peers ativos."""
        while self._running:
            try:
                if self._discovery:
                    peers = self._discovery.get_active_peers()
                    for peer in peers:
                        envelope = self._handler.create_heartbeat()
                        # Enviar via WebSocket ou HTTP
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
                # Atualizar anúncio mDNS com nova carga
                if self._announcer:
                    # Reanunciar com nova carga
                    pass
            except Exception as e:
                logger.error(f"Erro no load metrics: {e}")
            await asyncio.sleep(60)

    async def _send_to_peer(self, peer: DiscoveredNode, envelope: BeeEnvelope) -> None:
        """Envia envelope para peer via HTTP/WebSocket."""
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
        Processa query seguindo a política LOCAL -> ENXAME -> WEB.
        
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

        # 3. WEB - Fallback se habilitado
        if self.config.allow_web and self._librarian:
            web_result = await self._librarian.search_web(query)
            return {"answer": web_result.get("answer", ""), "source": "web", **web_result}

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
        """Consulta peers via protocolo BEE."""
        if not self._discovery:
            return {"answer": "", "confidence": 0.0}

        peers = self._discovery.get_active_peers()
        if not peers:
            return {"answer": "", "confidence": 0.0}

        # KNOWLEDGE_QUERY para filtrar peers relevantes
        best_peer = None
        best_confidence = 0.0

        for peer in peers:
            envelope = self._handler.create_knowledge_query(
                target_node_id=peer.node_id,
                subject=query,
                timeout_ms=2000,
            )
            try:
                # TODO: Enviar e aguardar resposta via WebSocket
                pass
            except Exception:
                continue

        # Se encontrou peer relevante, fazer RESEARCH_REQUEST
        if best_peer:
            envelope = self._handler.create_research_request(
                target_node_id=best_peer.node_id,
                query=query,
            )
            try:
                # TODO: Enviar e aguardar
                pass
            except Exception:
                pass

        return {"answer": "", "confidence": best_confidence}


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