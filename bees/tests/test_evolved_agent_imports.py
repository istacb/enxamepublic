"""Regression tests for separately-importable evolved agent components."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_shared_models_do_not_import_agent_service():
    from enxame_evolved.agent_models import AgentCapability, AgentProfile
    assert AgentCapability.CODE_GENERATION.value == "code_generation"
    from typing import get_type_hints
    assert AgentProfile(agent_id="node-a", name="Coder").name == "Coder"
    assert "metadata" in get_type_hints(AgentProfile)


def test_profile_manager_can_import_without_agent_cycle():
    from enxame_evolved.agent_profile_manager import ProfileManager, AgentProfileSpec
    from enxame_evolved.agent_models import AgentCapability
    assert ProfileManager is not None
    assert AgentProfileSpec(agent_id="a", name="B", capabilities=[AgentCapability.OCR]).name == "B"


def test_orchestrator_and_discovery_have_independent_imports():
    from enxame_evolved.agent_task_orchestrator import TaskOrchestrator
    from enxame_evolved.agent_swarm_discovery import SwarmDiscovery
    from enxame_evolved.agent_multimodal import MultiModalProcessor
    assert TaskOrchestrator and SwarmDiscovery and MultiModalProcessor
