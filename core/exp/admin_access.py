"""Restrict administrative operations to local clients or a configured admin token."""
from __future__ import annotations

import hmac
import ipaddress


def admin_access_allowed(remote_addr: str | None, supplied_token: str | None,
                         required_token: str | None) -> bool:
    """Trust loopback; require a separately configured secret for remote clients.

    Never trust Host or X-Forwarded-For as proof that the client is local.
    Reverse proxies should enforce their own auth and set ENXAME_ADMIN_TOKEN.
    """
    try:
        if remote_addr and ipaddress.ip_address(remote_addr).is_loopback:
            return True
    except ValueError:
        pass

    return bool(required_token and supplied_token) and hmac.compare_digest(
        supplied_token, required_token
    )
