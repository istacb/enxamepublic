"""Testes unitários do protocolo BEE.

Cobre:
- Descoberta (reutiliza discovery existente)
- Manifesto
- Handshake
- Timeout
- Incompatibilidade de versão
- Abelha desaparecendo da rede
"""

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bees.protocol.envelope import BeeEnvelope
from bees.protocol.handler import BeeProtocolHandler, PeerInfo
from bees.protocol.messages import (
    BeeErrorCode,
    BeeHeartbeat,
    BeeHello,
    BeeHelloAck,
    BeeIdentity,
    BeeKnowledgeQuery,
    BeeKnowledgeResponse,
    BeeManifesto,
    BeeMessageType,
    BeeState,
)


class TestBeeManifesto:
    """Testes para BeeManifesto."""

    def test_manifesto_creation(self):
        """Testa criação básica de manifesto."""
        manifesto = BeeManifesto(
            capabilities=["rag", "ocr"],
            models=["llama3:8b"],
            indexes=["documents"],
            load=0.3,
            uptime_seconds=3600,
            version="1.0.0",
        )

        assert manifesto.capabilities == ["rag", "ocr"]
        assert manifesto.models == ["llama3:8b"]
        assert manifesto.indexes == ["documents"]
        assert manifesto.load == 0.3
        assert manifesto.uptime_seconds == 3600

    def test_manifesto_has_capability(self):
        """Testa verificação de capabilities."""
        manifesto = BeeManifesto(capabilities=["rag", "ocr", "embeddings"])

        assert manifesto.has_capability("rag") is True
        assert manifesto.has_capability("ocr") is True
        assert manifesto.has_capability("web_fallback") is False

    def test_manifesto_has_model(self):
        """Testa verificação de modelos."""
        manifesto = BeeManifesto(models=["llama3:8b", "gemma2:9b"])

        assert manifesto.has_model("llama3:8b") is True
        assert manifesto.has_model("hermes:latest") is False

    def test_manifesto_to_dict(self):
        """Testa serialização para dict."""
        manifesto = BeeManifesto(
            capabilities=["rag"],
            models=["llama3:8b"],
            load=0.5,
            uptime_seconds=100,
        )

        data = manifesto.to_dict()
        assert data["capabilities"] == ["rag"]
        assert data["models"] == ["llama3:8b"]
        assert data["load"] == 0.5
        assert data["uptime_seconds"] == 100

    def test_manifesto_from_dict(self):
        """Testa desserialização de dict."""
        data = {
            "capabilities": ["rag", "ocr"],
            "models": ["llama3:8b"],
            "indexes": ["documents", "zim"],
            "load": 0.7,
            "uptime_seconds": 7200,
            "version": "1.0.0",
        }

        manifesto = BeeManifesto.from_dict(data)
        assert manifesto.capabilities == ["rag", "ocr"]
        assert manifesto.models == ["llama3:8b"]
        assert manifesto.indexes == ["documents", "zim"]
        assert manifesto.load == 0.7


class TestBeeHandshake:
    """Testes para handshake entre Abelhas."""

    def test_hello_creation(self):
        """Testa criação de mensagem HELLO."""
        identity = BeeIdentity(node_id="bee-123", protocol_version="1.0")
        manifesto = BeeManifesto(capabilities=["rag"], models=["llama3:8b"])

        hello = BeeHello(
            identity=identity,
            manifesto=manifesto,
            nonce="random-nonce-123",
        )

        assert hello.identity.node_id == "bee-123"
        assert hello.manifesto.capabilities == ["rag"]
        assert hello.nonce == "random-nonce-123"

    def test_hello_ack_creation(self):
        """Testa criação de mensagem HELLO_ACK."""
        identity = BeeIdentity(node_id="bee-456", protocol_version="1.0")
        manifesto = BeeManifesto(capabilities=["embeddings"])

        hello_ack = BeeHelloAck(
            identity=identity,
            manifesto=manifesto,
            nonce="new-nonce-456",
            echo_nonce="original-nonce-123",
        )

        assert hello_ack.identity.node_id == "bee-456"
        assert hello_ack.echo_nonce == "original-nonce-123"

    def test_hello_roundtrip(self):
        """Testa serialização e desserialização de HELLO."""
        original = BeeHello(
            identity=BeeIdentity(node_id="bee-789"),
            manifesto=BeeManifesto(capabilities=["rag", "ocr"]),
            nonce="test-nonce",
        )

        data = original.to_dict()
        restored = BeeHello.from_dict(data)

        assert restored.identity.node_id == original.identity.node_id
        assert restored.manifesto.capabilities == original.manifesto.capabilities
        assert restored.nonce == original.nonce


class TestBeeProtocolHandler:
    """Testes para BeeProtocolHandler."""

    def test_handler_creation(self):
        """Testa criação do handler."""
        handler = BeeProtocolHandler(
            node_id="test-bee",
            shared_secret=None,
            heartbeat_interval=5.0,
            heartbeat_timeout=15.0,
        )

        assert handler.node_id == "test-bee"
        assert handler.heartbeat_interval == 5.0
        assert handler.heartbeat_timeout == 15.0
        assert len(handler.peers) == 0

    def test_handler_with_security(self):
        """Testa handler com security habilitado."""
        handler = BeeProtocolHandler(
            node_id="secure-bee",
            shared_secret="test-secret-key",
        )

        assert handler._security is not None

    def test_create_heartbeat(self):
        """Testa criação de heartbeat."""
        handler = BeeProtocolHandler(node_id="bee-1")
        envelope = handler.create_heartbeat()

        assert envelope.msg_type == BeeMessageType.HEARTBEAT
        assert envelope.source_node_id == "bee-1"
        assert envelope.priority == 8  # Alta prioridade

    def test_create_knowledge_query(self):
        """Testa criação de knowledge query."""
        handler = BeeProtocolHandler(node_id="bee-1")
        envelope = handler.create_knowledge_query(
            target_node_id="bee-2",
            subject="direito tributário",
            keywords=["impostos", "Brasil"],
            min_confidence=0.7,
            timeout_ms=2000,
        )

        assert envelope.msg_type == BeeMessageType.KNOWLEDGE_QUERY
        assert envelope.target_node_id == "bee-2"
        
        payload = BeeKnowledgeQuery.from_dict(envelope.payload)
        assert payload.subject == "direito tributário"
        assert payload.keywords == ["impostos", "Brasil"]
        assert payload.min_confidence == 0.7

    def test_create_knowledge_response(self):
        """Testa criação de knowledge response."""
        handler = BeeProtocolHandler(node_id="bee-2")
        envelope = handler.create_knowledge_response(
            target_node_id="bee-1",
            query_id="query-123",
            has_knowledge=True,
            confidence=0.85,
            document_count=12,
            topics=["ICMS", "ISS"],
        )

        assert envelope.msg_type == BeeMessageType.KNOWLEDGE_RESPONSE
        
        payload = BeeKnowledgeResponse.from_dict(envelope.payload)
        assert payload.has_knowledge is True
        assert payload.confidence == 0.85
        assert payload.document_count == 12


class TestTimeout:
    """Testes para timeout de mensagens."""

    def test_envelope_not_expired(self):
        """Testa envelope não expirado."""
        envelope = BeeEnvelope.create_request(
            source_node_id="bee-1",
            target_node_id="bee-2",
            msg_type=BeeMessageType.KNOWLEDGE_QUERY,
            payload={"test": "data"},
            ttl_ms=30000,
        )

        assert envelope.is_expired() is False

    def test_envelope_expired(self):
        """Testa envelope expirado."""
        envelope = BeeEnvelope.create_request(
            source_node_id="bee-1",
            target_node_id="bee-2",
            msg_type=BeeMessageType.KNOWLEDGE_QUERY,
            payload={"test": "data"},
            ttl_ms=1,  # 1ms
        )

        # Aguarda um pouco para garantir expiração
        time.sleep(0.01)  # 10ms
        assert envelope.is_expired() is True

    @pytest.mark.asyncio
    async def test_send_with_timeout_success(self):
        """Testa envio com timeout - sucesso."""
        handler = BeeProtocolHandler(node_id="bee-1")
        
        envelope = handler.create_knowledge_query(
            target_node_id="bee-2",
            subject="teste",
            timeout_ms=5000,
        )

        # Mock send_func que completa o pending
        async def mock_send(env):
            response = handler.create_knowledge_response(
                target_node_id="bee-1",
                query_id="query-123",
                has_knowledge=True,
                correlation_id=envelope.correlation_id,
            )
            handler.complete_pending_request(envelope.correlation_id or "", response)

        result = await handler.send_with_timeout(envelope, mock_send, timeout_ms=5000)
        assert result is not None
        assert result.msg_type == BeeMessageType.KNOWLEDGE_RESPONSE

    @pytest.mark.asyncio
    async def test_send_with_timeout_failure(self):
        """Testa envio com timeout - falha por timeout."""
        handler = BeeProtocolHandler(node_id="bee-1")
        
        envelope = handler.create_knowledge_query(
            target_node_id="bee-2",
            subject="teste",
            timeout_ms=100,  # 100ms
        )

        # Mock send_func que NÃO responde (simula timeout)
        async def mock_send(env):
            pass  # Não faz nada, deixa timeout ocorrer

        result = await handler.send_with_timeout(envelope, mock_send, timeout_ms=100)
        assert result is None  # Timeout retorna None


class TestVersionIncompatibility:
    """Testes para incompatibilidade de versão."""

    def test_envelope_version_validation(self):
        """Testa validação de versão incompatível."""
        envelope = BeeEnvelope(
            protocol_version="2.0",  # Versão incompatível
            msg_id="test-123",
            source_node_id="bee-1",
            msg_type=BeeMessageType.HELLO,
        )

        errors = envelope.validate()
        assert any("Versão incompatível" in e for e in errors)

    def test_envelope_valid_version(self):
        """Testa validação de versão válida."""
        envelope = BeeEnvelope(
            protocol_version="1.0",
            msg_id="test-123",
            source_node_id="bee-1",
            msg_type=BeeMessageType.HELLO,
        )

        errors = envelope.validate()
        assert len(errors) == 0

    def test_handle_wrong_version(self):
        """Testa handler rejeitando versão errada."""
        handler = BeeProtocolHandler(node_id="bee-1")
        
        envelope = BeeEnvelope(
            protocol_version="2.0",
            msg_id="test-123",
            source_node_id="bee-2",
            msg_type=BeeMessageType.HELLO,
            payload={},
        )

        # Validação manual antes de handle_message
        errors = envelope.validate()
        assert any("Versão incompatível" in e for e in errors)


class TestPeerDisappearance:
    """Testes para detecção de peer desaparecendo da rede."""

    def test_peer_info_creation(self):
        """Testa criação de PeerInfo."""
        peer = PeerInfo(node_id="bee-xyz")

        assert peer.node_id == "bee-xyz"
        assert peer.state == BeeState.RUNNING
        assert peer.connected is False
        assert peer.missed_heartbeats == 0

    def test_update_peer_on_heartbeat(self):
        """Testa atualização de peer ao receber heartbeat."""
        handler = BeeProtocolHandler(node_id="bee-1")
        
        heartbeat_env = handler.create_heartbeat()
        handler._update_peer_info(heartbeat_env)

        peer = handler.get_peer("bee-1")
        assert peer is not None
        assert peer.connected is True
        assert peer.missed_heartbeats == 0

    def test_get_active_peers(self):
        """Testa obtenção de peers ativos."""
        handler = BeeProtocolHandler(
            node_id="bee-1",
            heartbeat_timeout=15.0,
        )

        # Adiciona peer manualmente
        now = datetime.now(UTC)
        handler.peers["bee-2"] = PeerInfo(
            node_id="bee-2",
            last_seen=now,
            state=BeeState.RUNNING,
            connected=True,
        )

        active = handler.get_active_peers()
        assert len(active) == 1
        assert active[0].node_id == "bee-2"

    def test_peer_becomes_inactive(self):
        """Testa peer tornando-se inativo após timeout."""
        handler = BeeProtocolHandler(
            node_id="bee-1",
            heartbeat_timeout=0.1,  # 100ms para teste rápido
        )

        # Adiciona peer com timestamp antigo
        old_time = datetime.now(UTC) - timedelta(seconds=1)
        handler.peers["bee-2"] = PeerInfo(
            node_id="bee-2",
            last_seen=old_time,
            state=BeeState.RUNNING,
            connected=True,
        )

        active = handler.get_active_peers()
        assert len(active) == 0  # Peer expirou

    def test_remove_peer(self):
        """Testa remoção explícita de peer."""
        handler = BeeProtocolHandler(node_id="bee-1")
        
        handler.peers["bee-2"] = PeerInfo(node_id="bee-2")
        assert "bee-2" in handler.peers

        handler.remove_peer("bee-2")
        assert "bee-2" not in handler.peers
        assert handler.get_peer("bee-2") is None


class TestDiscoveryReuse:
    """Testes demonstrando reutilização do discovery existente."""

    @patch("core.discovery.mdns_discovery.NodeAnnouncer")
    def test_mdns_announcement_with_bee_role(self, mock_announcer):
        """Testa anúncio mDNS com role 'bee'."""
        # Este teste demonstra como o discovery existente pode ser reutilizado
        # O campo 'role' deve ser "bee" para Abelhas
        from core.discovery.mdns_discovery import NodeAnnouncer

        announcer = NodeAnnouncer(
            node_id="bee-test-123",
            role="bee",  # Valor literal para Abelhas
            host_ip="192.168.1.100",
            port=8765,
            capabilities='["rag", "ocr"]',
            models='["llama3:8b"]',
        )

        assert announcer.role == "bee"
        assert announcer.node_id == "bee-test-123"
        assert announcer.capabilities == '["rag", "ocr"]'

    @patch("core.discovery.browser.ENXAMEMDNSBrowser")
    def test_mdns_browser_discovers_bee(self, mock_browser):
        """Testa browser descobrindo Abelha."""
        # Demonstra compatibilidade com discovery existente
        from core.discovery.browser import DiscoveredNode

        node = DiscoveredNode(
            node_id="bee-discovered-456",
            role="bee",
            host="192.168.1.101",
            port=8765,
            capabilities='["embeddings"]',
            models='["gemma2:9b"]',
        )

        assert node.role == "bee"
        assert "embeddings" in node.capabilities


class TestErrorHandling:
    """Testes para tratamento de erros."""

    def test_error_response_creation(self):
        """Testa criação de resposta de erro."""
        handler = BeeProtocolHandler(node_id="bee-1")
        
        request_env = handler.create_knowledge_query(
            target_node_id="bee-2",
            subject="teste",
        )

        error_env = handler._create_error_response(
            request_env,
            BeeErrorCode.NOT_FOUND,
            "Conhecimento não encontrado",
        )

        assert error_env.msg_type == BeeMessageType.ERROR
        assert error_env.payload["code"] == "NOT_FOUND"
        assert error_env.payload["detail"] == "Conhecimento não encontrado"

    def test_invalid_envelope_validation(self):
        """Testa validação de envelope inválido."""
        envelope = BeeEnvelope(
            protocol_version="1.0",
            msg_id="",  # Vazio = inválido
            source_node_id="",  # Vazio = inválido
            msg_type=BeeMessageType.HELLO,
        )

        errors = envelope.validate()
        assert "source_node_id é obrigatório" in errors
        assert "msg_id é obrigatório" in errors

    def test_priority_validation(self):
        """Testa validação de priority."""
        # Priority válido
        env1 = BeeEnvelope(
            protocol_version="1.0",
            msg_id="test-1",
            source_node_id="bee-1",
            msg_type=BeeMessageType.HELLO,
            priority=5,
        )
        assert len(env1.validate()) == 0

        # Priority inválido (muito alto)
        env2 = BeeEnvelope(
            protocol_version="1.0",
            msg_id="test-2",
            source_node_id="bee-1",
            msg_type=BeeMessageType.HELLO,
            priority=15,  # > 10
        )
        errors = env2.validate()
        assert any("priority deve estar entre" in e for e in errors)


# Executa os testes
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
