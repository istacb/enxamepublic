"""Regression tests for Ollama image requests, pulls and model sizing."""
from pathlib import Path
import sys
from unittest.mock import AsyncMock

import pytest

# CI installs bees/ as an editable package from the bees/ working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.ollama.client import OllamaClient, OllamaGenerateRequest, OllamaModel


class FakeResponse:
    status_code = 200
    text = ""
    def json(self):
        return {"response": "image described", "status": "success"}


class FakeClient:
    def __init__(self, calls):
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def post(self, url, *, json):
        self.calls.append((url, json))
        return FakeResponse()


@pytest.mark.asyncio
async def test_generate_passes_images_to_ollama(monkeypatch):
    import httpx
    calls = []
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeClient(calls))
    result = await OllamaClient("http://localhost:11434").generate(
        OllamaGenerateRequest(model="llava:7b", prompt="describe", images=["aW1hZ2U="])
    )
    assert result == "image described"
    assert calls[0][1]["images"] == ["aW1hZ2U="]


@pytest.mark.asyncio
async def test_pull_requests_non_streaming_response(monkeypatch):
    import httpx
    calls = []
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeClient(calls))
    result = await OllamaClient("http://localhost:11434").pull("llava:7b")
    assert result["status"] == "success"
    assert calls[0][1] == {"model": "llava:7b", "stream": False}


@pytest.mark.asyncio
async def test_small_model_does_not_satisfy_large_recommendation():
    client = OllamaClient("http://localhost:11434")
    client.list_models = AsyncMock(return_value=[
        OllamaModel(name="qwen2.5:0.5b", size_mb=500),
    ])
    client.pull = AsyncMock(return_value={"status": "success"})
    result = await client.ensure_model(ram_gb=16, vram_gb=0)
    assert result == "qwen2.5:7b"
    client.pull.assert_awaited_once_with("qwen2.5:7b")


@pytest.mark.asyncio
async def test_same_or_larger_known_model_is_reused():
    client = OllamaClient("http://localhost:11434")
    client.list_models = AsyncMock(return_value=[
        OllamaModel(name="qwen2.5:7b", size_mb=4000),
    ])
    client.pull = AsyncMock()
    assert await client.ensure_model(ram_gb=16, vram_gb=0) == "qwen2.5:7b"
    client.pull.assert_not_awaited()
