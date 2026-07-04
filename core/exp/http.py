from __future__ import annotations

from datetime import datetime, timezone

from .security import EXPSecurity


EXP_SIGNATURE_HEADER = "x-exp-signature"
EXP_TIMESTAMP_HEADER = "x-exp-timestamp"


def build_auth_headers(security: EXPSecurity, body: bytes) -> dict[str, str]:
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    signature = security.sign_http_message(body, timestamp)
    return {
        EXP_TIMESTAMP_HEADER: timestamp,
        EXP_SIGNATURE_HEADER: signature,
    }
