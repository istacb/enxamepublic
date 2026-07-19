from __future__ import annotations

import pytest

from core.exp.envelope import EXPEnvelope, EXPNode
from core.exp.types import EXPMessageType


def test_envelope_defaults() -> None:
    env = EXPEnvelope(
        source=EXPNode(node_id="juiz-01", role="juiz"),
        type=EXPMessageType.HELLO,
        payload={"ok": True},
    )
    assert env.exp_version == "1.0"
    assert env.priority == 5


def test_envelope_priority_bounds() -> None:
    with pytest.raises(ValueError):
        EXPEnvelope(
            source=EXPNode(node_id="juiz-01", role="juiz"),
            type=EXPMessageType.HELLO,
            payload={},
            priority=11,
        )
