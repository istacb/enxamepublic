"""HTTP BEE message transport and authenticated envelope regression tests."""
from pathlib import Path
import sys

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bees.config import BeeConfig
from bees.service import BeeService
from bees.protocol.envelope import BeeEnvelope
from bees.protocol.handler import BeeProtocolHandler
from bees.protocol.messages import BeeMessageType


@pytest.mark.asyncio
async def test_unified_app_routes_signed_knowledge_request(tmp_path):
    receiver = BeeService(BeeConfig(data_dir=tmp_path, node_id="bee-b", shared_secret="shared"))
    app = web.Application()
    await receiver._add_routes_to_app(app)
    sender = BeeProtocolHandler("bee-a", shared_secret="shared")
    request = sender.create_knowledge_query("bee-b", "python")
    sender.sign_envelope(request)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/api/v1/bee/message", json=request.to_dict())
        assert response.status == 200
        reply = BeeEnvelope.from_dict(await response.json())
        assert reply.msg_type is BeeMessageType.KNOWLEDGE_RESPONSE
        assert reply.source_node_id == "bee-b"
        assert sender.verify_envelope(reply)


@pytest.mark.asyncio
async def test_missing_signature_rejected_with_configured_secret(tmp_path):
    receiver = BeeService(BeeConfig(data_dir=tmp_path, node_id="bee-b", shared_secret="shared"))
    app = web.Application()
    await receiver._add_routes_to_app(app)
    sender = BeeProtocolHandler("bee-a")
    request = sender.create_knowledge_query("bee-b", "python")
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/api/v1/bee/message", json=request.to_dict())
        assert response.status == 401
    assert not receiver._handler.verify_envelope(request)


@pytest.mark.asyncio
async def test_malformed_message_and_wrong_target_rejected(tmp_path):
    receiver = BeeService(BeeConfig(data_dir=tmp_path, node_id="bee-b"))
    app = web.Application()
    await receiver._add_routes_to_app(app)
    request = BeeProtocolHandler("bee-a").create_knowledge_query("bee-c", "python")
    async with TestClient(TestServer(app)) as client:
        assert (await client.post("/api/v1/bee/message", json={"invalid": True})).status == 400
        assert (await client.post("/api/v1/bee/message", json=request.to_dict())).status == 400


def test_research_and_vision_request_ttl_are_valid():
    handler = BeeProtocolHandler("bee-a")
    research = handler.create_research_request("bee-b", "question", timeout_ms=30000)
    vision = handler.create_vision_request("bee-b", "aW1hZ2U=", timeout_ms=60000)
    assert research.ttl_ms == 35000
    assert vision.ttl_ms == 70000
