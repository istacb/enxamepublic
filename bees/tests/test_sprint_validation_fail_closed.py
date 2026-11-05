"""An unavailable LLM must never approve unverified sprint work."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from enxame_evolved.sprint import SprintPlanner, SprintTask


def make_planner(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kernel = SimpleNamespace(config=SimpleNamespace(ollama_base_url="http://localhost:11434",
                                                     model="llama3.2:3b"))
    return SprintPlanner(orchestrator=SimpleNamespace(kernel=kernel), profiles=None)


@pytest.mark.asyncio
async def test_model_failure_does_not_mark_acceptance_as_passed(tmp_path, monkeypatch):
    from core.ollama import client as ollama_mod
    monkeypatch.setattr(ollama_mod, "OllamaClient", lambda *_: SimpleNamespace(
        generate=AsyncMock(side_effect=RuntimeError("ollama unavailable"))))
    planner = make_planner(monkeypatch, tmp_path)
    verdict = await planner._validate_acceptance(
        SprintTask(title="Write code", acceptance_criteria=["unit tests pass"]),
        {"answer": "done"})
    assert verdict["passed"] is False
    assert verdict["error"]


@pytest.mark.asyncio
async def test_invalid_model_json_fails_closed(tmp_path, monkeypatch):
    from core.ollama import client as ollama_mod
    monkeypatch.setattr(ollama_mod, "OllamaClient", lambda *_: SimpleNamespace(
        generate=AsyncMock(return_value='{"passed": "true"}')))
    planner = make_planner(monkeypatch, tmp_path)
    verdict = await planner._validate_acceptance(
        SprintTask(title="Tests", acceptance_criteria=["green"]),
        {"answer": "done"})
    assert verdict["passed"] is False


@pytest.mark.asyncio
async def test_no_acceptance_criteria_is_explicitly_allowed(tmp_path, monkeypatch):
    planner = make_planner(monkeypatch, tmp_path)
    assert (await planner._validate_acceptance(SprintTask(), {})) == {
        "passed": True, "details": []
    }
