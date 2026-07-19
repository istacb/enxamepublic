from __future__ import annotations

from fastapi.testclient import TestClient

from core.exp.http import build_auth_headers
from core.exp.security import EXPSecurity
from juiz.app import app


def test_health_ok() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_cluster_requires_valid_hmac() -> None:
    client = TestClient(app)
    security = EXPSecurity("enxame-dev-secret")
    headers = build_auth_headers(security, b"")
    resp = client.get("/api/v1/cluster", headers=headers)
    assert resp.status_code == 200
    assert "agents_connected" in resp.json()
