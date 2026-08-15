"""Handler do protocolo BEE para processamento de mensagens.

Reutiliza EXPSecurity do core/exp para autenticação.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .envelope import BeeEnvelope
from .messages import (
    BeeCapabilityQuery,
    BeeCapabilityResponse,
    BeeError,
    BeeErrorCode,
    BeeHeartbeat,
    BeeHeartbeatAck,
    BeeHello,
    BeeHelloAck,
    BeeKnowledgeQuery,
    BeeKnowledgeResponse,
    BeeManifesto,
    BeeMessageType,
    BeeModelRequest,
    BeeModelResponse,
    BeeResearchRequest,
    BeeResearchResult,
    BeeState,
)


# Tipo de handler para mensagens específicas
MessageHandler = Callable[[BeeEnvelope], Awaitable[BeeEnvelope | None]]


@dataclass(slots=True)
class PeerInfo:
    """Informações sobre um peer conhecido."""

    node_id: str
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    state: BeeState = BeeState.RUNNING
    load: float = 0.0
    manifesto: BeeManifesto | None = None
    missed_heartbeats: int = 0
    connected: bool = False


class BeeProtocolHandler:
    """Handler para processamento de mensagens do protocolo BEE.

    Este handler gerencia:
    - Handshake inicial (HELLO/HELLO_ACK)
    - Heartbeat e detecção de falhas
    - Consultas (KNOWLEDGE_QUERY, RESEARCH_REQUEST, MODEL_REQUEST)
    - Estado de peers
    - Timeouts e retries
    """

    def __init__(
        self,
        node_id: str,
        shared_secret: str | None = None,
        heartbeat_interval: float = 5.0,
        heartbeat_timeout: float = 15.0,
    ) -> None:
        self.node_id = node_id
        self.shared_secret = shared_secret
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout

        # Peers conhecidos
        self.peers: dict[str, PeerInfo] = {}

        # Handlers registrados por tipo de mensagem
        self._handlers: dict[BeeMessageType, MessageHandler] = {}

        # Pending requests com timeout
        self._pending_requests: dict[str, asyncio.Future[BeeEnvelope]] = {}

        # Sequence counter para heartbeats
        self._heartbeat_sequence = 0

        # Security (reutiliza do core/exp se disponível)
        self._security = None
        if shared_secret:
            try:
                from core.exp.security import EXPSecurity

                self._security = EXPSecurity(shared_secret=shared_secret)
            except ImportError:
                pass

        # Setup handlers padrão
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Registra handlers padrão para tipos de mensagem."""
        # Handlers são registrados conforme necessário
        pass

    def register_handler(
        self, msg_type: BeeMessageType, handler: MessageHandler
    ) -> None:
        """Registra handler para tipo específico de mensagem."""
        self._handlers[msg_type] = handler

    async def handle_message(
        self, envelope: BeeEnvelope
    ) -> BeeEnvelope | None:
        """Processa mensagem recebida e retorna resposta se aplicável.

        Args:
            envelope: Mensagem recebida

        Returns:
            Envelope de resposta ou None se não houver resposta
        """
        # Validação básica
        errors = envelope.validate()
        if errors:
            return self._create_error_response(
                envelope, BeeErrorCode.BAD_PAYLOAD, "; ".join(errors)
            )

        # Verifica expiração
        if envelope.is_expired():
            return self._create_error_response(
                envelope, BeeErrorCode.TIMEOUT, "Mensagem expirada"
            )

        # Verifica assinatura se security habilitado
        if self._security and envelope.signature:
            try:
                signable = envelope.as_signable_dict()
                if not self._security.verify_payload(signable, envelope.signature):
                    return self._create_error_response(
                        envelope, BeeErrorCode.AUTH_FAILED, "Assinatura inválida"
                    )
            except Exception as e:
                return self._create_error_response(
                    envelope, BeeErrorCode.AUTH_FAILED, f"Erro validação: {e}"
                )

        # Atualiza info do peer
        self._update_peer_info(envelope)

        # Dispatch para handler específico
        handler = self._handlers.get(envelope.msg_type)
        if handler:
            try:
                response = await handler(envelope)
                return response
            except Exception as e:
                return self._create_error_response(
                    envelope, BeeErrorCode.INTERNAL_ERROR, str(e)
                )

        # Handler não registrado - retorna erro
        return self._create_error_response(
            envelope,
            BeeErrorCode.UNSUPPORTED,
            f"Tipo de mensagem não suportado: {envelope.msg_type}",
        )

    def _update_peer_info(self, envelope: BeeEnvelope) -> None:
        """Atualiza informações do peer baseado na mensagem recebida."""
        source_id = envelope.source_node_id
        if source_id not in self.peers:
            self.peers[source_id] = PeerInfo(node_id=source_id)

        peer = self.peers[source_id]
        peer.last_seen = datetime.now(UTC)
        peer.connected = True
        peer.missed_heartbeats = 0

        # Extrai estado do payload se disponível
        if envelope.msg_type == BeeMessageType.HEARTBEAT:
            heartbeat = BeeHeartbeat.from_dict(envelope.payload)
            peer.state = heartbeat.state
            peer.load = heartbeat.load

    def _create_error_response(
        self,
        request_envelope: BeeEnvelope,
        code: BeeErrorCode,
        detail: str | None = None,
    ) -> BeeEnvelope:
        """Cria envelope de erro em resposta a request."""
        error = BeeError(code=code, detail=detail, request_id=request_envelope.correlation_id)
        return BeeEnvelope.create_response(
            source_node_id=self.node_id,
            target_node_id=request_envelope.source_node_id,
            msg_type=BeeMessageType.ERROR,
            payload=error.to_dict(),
            correlation_id=request_envelope.correlation_id or request_envelope.msg_id,
        )

    # ========================================================================
    # Métodos utilitários para envio de mensagens
    # ========================================================================

    def create_hello(
        self,
        target_node_id: str | None,
        manifesto: BeeManifesto,
        nonce: str,
    ) -> BeeEnvelope:
        """Cria mensagem HELLO para handshake."""
        from .messages import BeeIdentity

        identity = BeeIdentity(
            node_id=self.node_id,
            protocol_version="1.0",
        )

        hello = BeeHello(
            identity=identity,
            manifesto=manifesto,
            nonce=nonce,
        )

        return BeeEnvelope.create_request(
            source_node_id=self.node_id,
            target_node_id=target_node_id,
            msg_type=BeeMessageType.HELLO,
            payload=hello.to_dict(),
        )

    def create_hello_ack(
        self,
        target_node_id: str,
        manifesto: BeeManifesto,
        nonce: str,
        echo_nonce: str,
        correlation_id: str,
    ) -> BeeEnvelope:
        """Cria mensagem HELLO_ACK para resposta de handshake."""
        from .messages import BeeIdentity

        identity = BeeIdentity(
            node_id=self.node_id,
            protocol_version="1.0",
        )

        hello_ack = BeeHelloAck(
            identity=identity,
            manifesto=manifesto,
            nonce=nonce,
            echo_nonce=echo_nonce,
        )

        return BeeEnvelope.create_response(
            source_node_id=self.node_id,
            target_node_id=target_node_id,
            msg_type=BeeMessageType.HELLO_ACK,
            payload=hello_ack.to_dict(),
            correlation_id=correlation_id,
        )

    def create_heartbeat(self) -> BeeEnvelope:
        """Cria mensagem HEARTBEAT."""
        self._heartbeat_sequence += 1

        heartbeat = BeeHeartbeat(
            node_id=self.node_id,
            state=BeeState.RUNNING,
            load=0.0,  # Deve ser atualizado pelo caller
            timestamp=datetime.now(UTC),
            sequence=self._heartbeat_sequence,
        )

        return BeeEnvelope.create_request(
            source_node_id=self.node_id,
            target_node_id=None,  # Broadcast
            msg_type=BeeMessageType.HEARTBEAT,
            payload=heartbeat.to_dict(),
            priority=8,  # Alta prioridade
            ttl_ms=15000,
        )

    def create_heartbeat_ack(
        self, target_node_id: str, ack_sequence: int, load: float = 0.0
    ) -> BeeEnvelope:
        """Cria mensagem HEARTBEAT_ACK."""
        self._heartbeat_sequence += 1

        heartbeat_ack = BeeHeartbeatAck(
            node_id=self.node_id,
            state=BeeState.RUNNING,
            load=load,
            timestamp=datetime.now(UTC),
            sequence=self._heartbeat_sequence,
            ack_sequence=ack_sequence,
        )

        return BeeEnvelope.create_response(
            source_node_id=self.node_id,
            target_node_id=target_node_id,
            msg_type=BeeMessageType.HEARTBEAT_ACK,
            payload=heartbeat_ack.to_dict(),
            correlation_id=str(ack_sequence),
            priority=8,
            ttl_ms=15000,
        )

    def create_knowledge_query(
        self,
        target_node_id: str,
        subject: str,
        keywords: list[str] | None = None,
        min_confidence: float = 0.6,
        timeout_ms: int = 2000,
    ) -> BeeEnvelope:
        """Cria mensagem KNOWLEDGE_QUERY."""
        query = BeeKnowledgeQuery(
            query_id=f"query_{time.time()}_{self.node_id[:8]}",
            subject=subject,
            keywords=keywords or [],
            min_confidence=min_confidence,
            timeout_ms=timeout_ms,
        )

        return BeeEnvelope.create_request(
            source_node_id=self.node_id,
            target_node_id=target_node_id,
            msg_type=BeeMessageType.KNOWLEDGE_QUERY,
            payload=query.to_dict(),
            ttl_ms=timeout_ms + 1000,  # Margem para processamento
        )

    def create_knowledge_response(
        self,
        target_node_id: str,
        query_id: str,
        has_knowledge: bool,
        confidence: float = 0.0,
        document_count: int = 0,
        topics: list[str] | None = None,
        correlation_id: str | None = None,
    ) -> BeeEnvelope:
        """Cria mensagem KNOWLEDGE_RESPONSE."""
        response = BeeKnowledgeResponse(
            query_id=query_id,
            has_knowledge=has_knowledge,
            confidence=confidence,
            document_count=document_count,
            topics=topics or [],
        )

        return BeeEnvelope.create_response(
            source_node_id=self.node_id,
            target_node_id=target_node_id,
            msg_type=BeeMessageType.KNOWLEDGE_RESPONSE,
            payload=response.to_dict(),
            correlation_id=correlation_id or query_id,
        )

    def create_research_request(
        self,
        target_node_id: str,
        query: str,
        context: str | None = None,
        max_results: int = 10,
        include_sources: bool = True,
        timeout_ms: int = 30000,
    ) -> BeeEnvelope:
        """Cria mensagem RESEARCH_REQUEST."""
        request = BeeResearchRequest(
            request_id=f"research_{time.time()}_{self.node_id[:8]}",
            query=query,
            context=context,
            max_results=max_results,
            include_sources=include_sources,
            timeout_ms=timeout_ms,
        )

        return BeeEnvelope.create_request(
            source_node_id=self.node_id,
            target_node_id=target_node_id,
            msg_type=BeeMessageType.RESEARCH_REQUEST,
            payload=request.to_dict(),
            timeout_ms=timeout_ms + 5000,
        )

    def create_research_result(
        self,
        target_node_id: str,
        request_id: str,
        results: list[Any],
        total_results: int = 0,
        processing_time_ms: int = 0,
        model_used: str | None = None,
        correlation_id: str | None = None,
    ) -> BeeEnvelope:
        """Cria mensagem RESEARCH_RESULT."""
        from .messages import ResearchResultItem

        result_items = []
        for r in results:
            if isinstance(r, dict):
                result_items.append(ResearchResultItem.from_dict(r))
            elif isinstance(r, ResearchResultItem):
                result_items.append(r)

        result = BeeResearchResult(
            request_id=request_id,
            results=result_items,
            total_results=total_results or len(result_items),
            processing_time_ms=processing_time_ms,
            model_used=model_used,
            sources_included=True,
        )

        return BeeEnvelope.create_response(
            source_node_id=self.node_id,
            target_node_id=target_node_id,
            msg_type=BeeMessageType.RESEARCH_RESULT,
            payload=result.to_dict(),
            correlation_id=correlation_id or request_id,
        )

    def create_model_request(
        self,
        target_node_id: str,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
        timeout_ms: int = 60000,
    ) -> BeeEnvelope:
        """Cria mensagem MODEL_REQUEST."""
        request = BeeModelRequest(
            request_id=f"model_{time.time()}_{self.node_id[:8]}",
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_ms=timeout_ms,
        )

        return BeeEnvelope.create_request(
            source_node_id=self.node_id,
            target_node_id=target_node_id,
            msg_type=BeeMessageType.MODEL_REQUEST,
            payload=request.to_dict(),
            timeout_ms=timeout_ms + 10000,
        )

    def create_model_response(
        self,
        target_node_id: str,
        request_id: str,
        generation: str,
        model_used: str | None = None,
        tokens_used: int = 0,
        processing_time_ms: int = 0,
        correlation_id: str | None = None,
    ) -> BeeEnvelope:
        """Cria mensagem MODEL_RESPONSE."""
        response = BeeModelResponse(
            request_id=request_id,
            generation=generation,
            model_used=model_used,
            tokens_used=tokens_used,
            processing_time_ms=processing_time_ms,
        )

        return BeeEnvelope.create_response(
            source_node_id=self.node_id,
            target_node_id=target_node_id,
            msg_type=BeeMessageType.MODEL_RESPONSE,
            payload=response.to_dict(),
            correlation_id=correlation_id or request_id,
        )

    def create_capability_query(
        self, target_node_id: str, capability: str, subject: str | None = None
    ) -> BeeEnvelope:
        """Cria mensagem CAPABILITY_QUERY."""
        query = BeeCapabilityQuery(capability=capability, subject=subject)

        return BeeEnvelope.create_request(
            source_node_id=self.node_id,
            target_node_id=target_node_id,
            msg_type=BeeMessageType.CAPABILITY_QUERY,
            payload=query.to_dict(),
        )

    def create_capability_response(
        self,
        target_node_id: str,
        has_capability: bool,
        confidence: float = 0.0,
        document_count: int = 0,
        correlation_id: str | None = None,
    ) -> BeeEnvelope:
        """Cria mensagem CAPABILITY_RESPONSE."""
        response = BeeCapabilityResponse(
            has_capability=has_capability,
            confidence=confidence,
            document_count=document_count,
        )

        return BeeEnvelope.create_response(
            source_node_id=self.node_id,
            target_node_id=target_node_id,
            msg_type=BeeMessageType.CAPABILITY_RESPONSE,
            payload=response.to_dict(),
            correlation_id=correlation_id,
        )

    def create_state_change(
        self,
        new_state: BeeState,
        reason: str,
        estimated_return_seconds: int | None = None,
    ) -> BeeEnvelope:
        """Cria mensagem STATE_CHANGE (broadcast)."""
        from .messages import BeeStateChange

        state_change = BeeStateChange(
            node_id=self.node_id,
            new_state=new_state,
            reason=reason,
            estimated_return_seconds=estimated_return_seconds,
        )

        return BeeEnvelope.create_request(
            source_node_id=self.node_id,
            target_node_id=None,  # Broadcast
            msg_type=BeeMessageType.STATE_CHANGE,
            payload=state_change.to_dict(),
            priority=9,
        )

    def create_peer_lost(
        self,
        node_id: str,
        last_seen: datetime,
        reason: str,
        missed_heartbeats: int = 0,
    ) -> BeeEnvelope:
        """Cria mensagem PEER_LOST (notificação local)."""
        from .messages import BeePeerLost

        peer_lost = BeePeerLost(
            node_id=node_id,
            last_seen=last_seen,
            reason=reason,
            missed_heartbeats=missed_heartbeats,
        )

        return BeeEnvelope.create_request(
            source_node_id=self.node_id,
            target_node_id=None,
            msg_type=BeeMessageType.PEER_LOST,
            payload=peer_lost.to_dict(),
            priority=7,
        )

    # ========================================================================
    # Gerenciamento de pending requests
    # ========================================================================

    async def send_with_timeout(
        self,
        envelope: BeeEnvelope,
        send_func: Callable[[BeeEnvelope], Awaitable[None]],
        timeout_ms: int | None = None,
    ) -> BeeEnvelope | None:
        """Envia mensagem e aguarda resposta com timeout.

        Args:
            envelope: Mensagem a enviar
            send_func: Função assíncrona para enviar mensagem
            timeout_ms: Timeout em ms (usa do envelope se None)

        Returns:
            Resposta ou None se timeout
        """
        if timeout_ms is None:
            timeout_ms = envelope.ttl_ms

        future: asyncio.Future[BeeEnvelope] = asyncio.Future()
        self._pending_requests[envelope.correlation_id or envelope.msg_id] = future

        try:
            await send_func(envelope)
            response = await asyncio.wait_for(future, timeout=timeout_ms / 1000.0)
            return response
        except asyncio.TimeoutError:
            # Timeout - limpa pending
            self._pending_requests.pop(
                envelope.correlation_id or envelope.msg_id, None
            )
            return None
        except Exception:
            self._pending_requests.pop(
                envelope.correlation_id or envelope.msg_id, None
            )
            raise

    def complete_pending_request(
        self, correlation_id: str, response: BeeEnvelope
    ) -> bool:
        """Completa request pendente com resposta.

        Returns:
            True se encontrou e completou o pending, False caso contrário
        """
        future = self._pending_requests.pop(correlation_id, None)
        if future and not future.done():
            future.set_result(response)
            return True
        return False

    def fail_pending_request(self, correlation_id: str, exception: Exception) -> bool:
        """Falha request pendente com exceção.

        Returns:
            True se encontrou e falhou o pending, False caso contrário
        """
        future = self._pending_requests.pop(correlation_id, None)
        if future and not future.done():
            future.set_exception(exception)
            return True
        return False

    # ========================================================================
    # Utilitários
    # ========================================================================

    def get_peer(self, node_id: str) -> PeerInfo | None:
        """Retorna informações de um peer específico."""
        return self.peers.get(node_id)

    def get_active_peers(self) -> list[PeerInfo]:
        """Retorna lista de peers ativos (conectados recentemente)."""
        now = datetime.now(UTC)
        active = []
        for peer in self.peers.values():
            elapsed = (now - peer.last_seen).total_seconds()
            if elapsed < self.heartbeat_timeout and peer.connected:
                active.append(peer)
        return active

    def remove_peer(self, node_id: str) -> None:
        """Remove peer da lista de conhecidos."""
        self.peers.pop(node_id, None)

    def sign_envelope(self, envelope: BeeEnvelope) -> None:
        """Assina envelope com HMAC se security habilitado."""
        if self._security:
            signable = envelope.as_signable_dict()
            envelope.signature = self._security.sign_payload(signable)

    def verify_envelope(self, envelope: BeeEnvelope) -> bool:
        """Verifica assinatura de envelope.

        Returns:
            True se válida ou se security não habilitado, False se inválida
        """
        if not self._security or not envelope.signature:
            return True  # Sem security ou sem signature = aceita

        try:
            signable = envelope.as_signable_dict()
            return self._security.verify_payload(signable, envelope.signature)
        except Exception:
            return False
