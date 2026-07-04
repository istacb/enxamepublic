from __future__ import annotations

from datetime import datetime, timezone

from core.exp.http import build_auth_headers
from core.exp.security import EXPAuthError, EXPSecurity


def test_sign_and_verify_payload_ok() -> None:
    security = EXPSecurity("secret")
    payload = {"a": 1, "b": "x"}
    signature = security.sign_payload(payload)
    assert security.verify_payload(payload, signature)


def test_http_hmac_rejects_bad_signature() -> None:
    security = EXPSecurity("secret")
    body = b'{"hello":"world"}'
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    try:
        security.verify_http_message(body=body, timestamp=ts, signature="bad")
        assert False, "Era esperado EXPAuthError"
    except EXPAuthError:
        assert True


def test_build_auth_headers() -> None:
    security = EXPSecurity("secret")
    headers = build_auth_headers(security, b"{}")
    assert "x-exp-signature" in headers
    assert "x-exp-timestamp" in headers
