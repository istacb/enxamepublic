"""Regression coverage for parsing BEE knowledge responses in the global index."""

from types import SimpleNamespace

import aiohttp
import pytest

from bees.cluster.global_index import query_peer_knowledge
from bees.protocol.envelope import BeeEnvelope
from bees.protocol.messages import BeeKnowledgeResponse, BeeMessageType


@pytest.mark.asyncio
@pytest.mark.parametrize("has_knowledge", [True, False])
async def test_query_peer_knowledge_parses_the_response_schema(monkeypatch, has_knowledge):
    reply = BeeKnowledgeResponse(
        query_id="query-1", has_knowledge=has_knowledge, confidence=0.92,
        document_count=7, topics=["python"]
    )
    envelope = BeeEnvelope.create_response(
        source_node_id="peer-b", target_node_id="global_index_query",
        msg_type=BeeMessageType.KNOWLEDGE_RESPONSE,
        payload=reply.to_dict(), correlation_id="request-1"
    )

    class Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        async def json(self):
            return envelope.to_dict()

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        def post(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(aiohttp, "ClientSession", lambda: Session())
    peer = SimpleNamespace(node_id="peer-b", host="127.0.0.1", port=8765)
    peer_id, knowledge = await query_peer_knowledge(peer, "python")

    assert peer_id == "peer-b"
    if has_knowledge:
        assert knowledge is not None
        assert knowledge.confidence == 0.92
        assert knowledge.document_count == 7
        assert knowledge.topics == ["python"]
    else:
        assert knowledge is None
