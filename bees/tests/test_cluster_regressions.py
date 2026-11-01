"""Regression coverage for role election and failover transitions."""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bees.cluster.election import elect_juiz_failover, elect_roles
from bees.cluster.monitor import ClusterMonitor
from bees.cluster.types import ClusterState


def _peer(node_id: str, load: float = 0.2) -> SimpleNamespace:
    return SimpleNamespace(node_id=node_id, capabilities=[], load=load)


def test_primary_role_fallback_without_declared_capabilities():
    peers = [_peer("bee-1", 0.1), _peer("bee-2", 0.2), _peer("bee-3", 0.3)]
    state = elect_roles(peers)
    assert (state.juiz_id, state.bibliotecario_id, state.guarda_id) == (
        "bee-1", "bee-2", "bee-3"
    )

    assert not set(state.workers) & {state.juiz_id, state.bibliotecario_id, state.guarda_id}


def test_fallback_roles_do_not_remain_workers_in_four_node_cluster():
    peers = [_peer("bee-1", 0.1), _peer("bee-2", 0.2), _peer("bee-3", 0.3), _peer("bee-4", 0.4)]
    state = elect_roles(peers)
    assert state.workers == ["bee-4"]
    assert set(state.secondary_roles) == {"bee-1", "bee-2", "bee-3"}


def test_juiz_failover_fallback_without_declared_capabilities():
    state = ClusterState(epoch=1, juiz_id="bee-1")
    result = elect_juiz_failover([_peer("bee-2", 0.1), _peer("bee-3", 0.2)], "bee-1", state)
    assert result.juiz_id == "bee-2"
    assert result.juiz_failover_started is not None


def test_72_hour_re_election_threshold():
    state = ClusterState(juiz_failover_started=time.time() - 73 * 3600)
    assert state.should_trigger_new_election() is True
    state.juiz_failover_started = time.time() - 71 * 3600
    assert state.should_trigger_new_election() is False
    state.juiz_failover_started = None
    assert state.should_trigger_new_election() is False


@pytest.mark.asyncio
async def test_monitor_re_elects_instead_of_restarting_expired_failover():
    state = ClusterState(juiz_id="bee-original", juiz_failover_started=time.time() - 73 * 3600)
    service = SimpleNamespace(_discovery=SimpleNamespace(get_active_peers=lambda: []))
    monitor = ClusterMonitor(service, state, lambda _state: None)
    monitor._trigger_new_election = AsyncMock()
    monitor._handle_juiz_failure = AsyncMock()
    monitor._check_re_election_needed = AsyncMock()

    await monitor._check_cluster_health()

    monitor._trigger_new_election.assert_awaited_once()
    monitor._handle_juiz_failure.assert_not_awaited()
