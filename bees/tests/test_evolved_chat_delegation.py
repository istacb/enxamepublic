"""Regression tests for evolved chat routing and peer delegation."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bees.config import BeeConfig
from bees.protocol.handler import BeeProtocolHandler
from bees.protocol.messages import BeeResearchResult, ResearchResultItem
from enxame_evolved.kernel import EnxameKernel
from enxame_evolved.orchestrator import TaskOrchestrator, Task, ExecutionPlan


@pytest.mark.asyncio
async def test_chat_uses_original_message_when_classifier_does_not_return_task(tmp_path):
    kernel = EnxameKernel(BeeConfig(data_dir=tmp_path))
    kernel._analyze_intent = AsyncMock(return_value={"task_type": "query", "suggested_profile": "generalist"})
    kernel._profiles = SimpleNamespace(select_or_create_profile=AsyncMock(return_value=SimpleNamespace(profile_id="generalist")))
    kernel._orchestrator = SimpleNamespace(execute_task=AsyncMock(return_value={"answer": "ok", "confidence": 1.0}))
    result = await kernel.process_chat("Who are my peers?")
    assert result["response"] == "ok"
    assert kernel._orchestrator.execute_task.await_args.kwargs["task"] == "Who are my peers?"


@pytest.mark.asyncio
async def test_peer_delegation_uses_actual_response_instead_of_fabrication():
    peer = SimpleNamespace(node_id="bee-b", host="127.0.0.1", port=8765)
    handler = BeeProtocolHandler("bee-a")
    reply = BeeProtocolHandler("bee-b").create_research_result(
        target_node_id="bee-a", request_id="research-1",
        results=[ResearchResultItem(content="Actual result", source="doc", confidence=0.9)],
    )
    bee = SimpleNamespace(_handler=handler, _send_with_response=AsyncMock(return_value=reply))
    discovery = SimpleNamespace(get_peer=lambda node_id: peer)
    orch = TaskOrchestrator(kernel=SimpleNamespace(node_id="bee-a"), profiles=None,
                            multimodal=None, discovery=discovery, bee=bee)
    out = await orch._delegate_to_peers(Task(message="question"), None, {}, ["bee-b"])
    assert out["answer"] == "Actual result"
    assert out["confidence"] == 0.9
    assert out["metadata"]["sources"] == ["doc"]


@pytest.mark.asyncio
async def test_peer_delegation_does_not_invent_answers_without_reply():
    peer = SimpleNamespace(node_id="bee-b")
    bee = SimpleNamespace(_handler=BeeProtocolHandler("bee-a"),
                          _send_with_response=AsyncMock(return_value=None))
    orch = TaskOrchestrator(kernel=SimpleNamespace(node_id="bee-a"), profiles=None,
                            multimodal=None, discovery=SimpleNamespace(get_peer=lambda _: peer), bee=bee)
    result = await orch._delegate_to_peers(Task(message="question"), None, {}, ["bee-b"])
    assert result["answer"] == ""
    assert result["source"] == "peer_failed"


@pytest.mark.asyncio
async def test_completed_tasks_leave_live_registry_but_remain_in_history():
    kernel = SimpleNamespace(config=SimpleNamespace(confidence_threshold_enxame=0.7))
    orch = TaskOrchestrator(kernel=kernel, profiles=None, multimodal=None, discovery=None, bee=None)
    orch._create_execution_plan = AsyncMock(return_value=ExecutionPlan(task_id="test"))
    orch._execute_local = AsyncMock(return_value={"answer": "ok", "confidence": 1})
    orch._record_success = AsyncMock()
    profile = SimpleNamespace(profile_id="generalist", complexity_handling="medium")
    result = await orch.execute_task("task", profile, {}, "question")
    assert result["answer"] == "ok"
    assert orch._tasks == {}
    assert len(orch._execution_history) == 1
    assert orch._execution_history[0].completed_at is not None
