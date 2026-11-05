"""Admin session and settings access must not be globally unauthenticated."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.exp.admin_access import admin_access_allowed


def test_loopback_admin_access_without_secret():
    assert admin_access_allowed("127.0.0.1", None, None)
    assert admin_access_allowed("::1", None, None)


def test_remote_admin_access_requires_configured_token():
    assert not admin_access_allowed("192.168.0.10", None, None)
    assert not admin_access_allowed("203.0.113.7", None, None)
    assert not admin_access_allowed("203.0.113.7", "wrong", "secret")
    assert admin_access_allowed("203.0.113.7", "secret", "secret")


def test_remote_address_cannot_be_spoofed_with_hostname_or_missing_ip():
    assert not admin_access_allowed(None, None, None)
    assert not admin_access_allowed("localhost", None, None)
    assert not admin_access_allowed("127.0.0.1.attacker.example", None, None)
