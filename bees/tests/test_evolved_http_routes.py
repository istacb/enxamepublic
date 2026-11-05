"""The unified kernel must compose with BeeService without duplicate routes."""
from pathlib import Path
import sys

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bees.config import BeeConfig
from bees.service import BeeService
from enxame_evolved.kernel import EnxameKernel


@pytest.mark.asyncio
async def test_kernel_and_bee_routes_compose_without_conflict(tmp_path):
    config = BeeConfig(data_dir=tmp_path)
    kernel = EnxameKernel(config)
    app = web.Application()
    kernel._http_app = app
    kernel._setup_http_routes()
    await BeeService(config)._add_routes_to_app(app)
    assert any(r.resource.canonical == "/health" for r in app.router.routes())
    assert any(r.resource.canonical == "/api/v1/chat" for r in app.router.routes())
    assert any(r.resource.canonical == "/api/v1/peers" for r in app.router.routes())
    assert sum(r.method == "GET" and r.resource.canonical == "/health" for r in app.router.routes()) == 1


@pytest.mark.asyncio
async def test_status_is_available_before_first_health_loop(tmp_path):
    kernel = EnxameKernel(BeeConfig(data_dir=tmp_path))
    status = await kernel.get_system_status()
    assert status["kernel"]["load"] == 0.0


@pytest.mark.asyncio
async def test_dashboard_websocket_ping_works(tmp_path):
    kernel = EnxameKernel(BeeConfig(data_dir=tmp_path))
    app = web.Application()
    kernel._http_app = app
    kernel._setup_http_routes()
    async with TestClient(TestServer(app)) as client:
        ws = await client.ws_connect("/ws")
        status = await ws.receive_json()
        assert status["type"] == "status"
        await ws.send_json({"type": "ping"})
        assert (await ws.receive_json())["type"] == "pong"
        await ws.close()
