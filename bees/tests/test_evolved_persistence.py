"""Persisted profile and sprint state must survive process restart."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from enxame_evolved.profiles import AgentProfileManager
from enxame_evolved.sprint import SprintPlanner, SprintStatus, SprintTask


@pytest.mark.asyncio
async def test_custom_profile_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bee = SimpleNamespace(_librarian=None)
    manager = AgentProfileManager("node-a", discovery=None, bee_service=bee)
    created = await manager.create_profile({
        "profile_id": "custom_test",
        "name": "Tester",
        "domain": "technical",
        "capabilities": ["code"],
    })
    assert created["status"] == "created"
    restored = AgentProfileManager("node-a", discovery=None, bee_service=bee)
    await restored._load_custom_profiles()
    profile = restored._profiles["custom_test"]
    assert profile.name == "Tester"
    assert isinstance(profile.created_at, datetime)


@pytest.mark.asyncio
async def test_sprint_round_trip_with_nested_tasks(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    planner = SprintPlanner(orchestrator=None, profiles=None)
    sprint = await planner.create_sprint("Hardening", "Verify persistence", ["EIP-0001"])
    assert sprint.tasks and all(isinstance(t, SprintTask) for t in sprint.tasks)
    sprint.tasks[0].status = "done"
    sprint.status = SprintStatus.ACTIVE
    await planner._save_sprints()

    restored = SprintPlanner(orchestrator=None, profiles=None)
    await restored.initialize()
    loaded = restored._sprints[sprint.sprint_id]
    assert loaded.status is SprintStatus.ACTIVE
    assert isinstance(loaded.tasks[0], SprintTask)
    assert loaded.tasks[0].status == "done"
    assert isinstance(loaded.tasks[0].created_at, datetime)
    assert isinstance(loaded.start_date, datetime)
