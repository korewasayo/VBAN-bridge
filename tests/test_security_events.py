import secrets
from types import SimpleNamespace

import pytest

from database.db import execute_query, fetch_one
from database.models import get_audit_category, init_db
from security.auth import get_ban_status, register_failed_access
from security.client_ip import get_client_ip
from security.rate_limiter import RateLimiter
from web.routes_admin import get_audit_log


class Headers(dict):
    def get(self, key, default=None):
        return super().get(key, default)


def make_request(peer_ip, headers=None):
    return SimpleNamespace(
        client=SimpleNamespace(host=peer_ip),
        headers=Headers(headers or {}),
    )


def test_forwarded_ip_is_trusted_only_from_loopback_proxy():
    request = make_request("203.0.113.8", {"CF-Connecting-IP": "198.51.100.4"})
    assert get_client_ip(request) == "203.0.113.8"

    request = make_request("127.0.0.1", {"CF-Connecting-IP": "198.51.100.4"})
    assert get_client_ip(request) == "198.51.100.4"


def test_rate_limiter_bounds_state_and_throttles_rejection_logs():
    limiter = RateLimiter(max_requests=1, window_seconds=60, max_tracked_ips=2)
    assert limiter.is_allowed("198.51.100.1")
    assert not limiter.is_allowed("198.51.100.1")
    assert limiter.should_log_rejection("198.51.100.1")
    assert not limiter.should_log_rejection("198.51.100.1")

    assert limiter.is_allowed("198.51.100.2")
    assert limiter.is_allowed("198.51.100.3")
    assert len(limiter.requests) == 2
    assert "198.51.100.1" not in limiter.requests


def test_audit_actions_are_grouped_for_filtering():
    assert get_audit_category("admin_login_failed") == "authentication"
    assert get_audit_category("rate_limit") == "security"
    assert get_audit_category("submit_upload") == "media"


@pytest.mark.asyncio
async def test_five_failed_auth_attempts_are_audited_and_banned():
    await init_db()
    ip_address = f"198.51.100.{secrets.randbelow(254) + 1}"
    try:
        for _ in range(5):
            result = await register_failed_access(
                ip_address=ip_address,
                reason="admin_login_failed",
                request_method="POST",
                request_path="/admin/login",
                user_agent="Test Browser/1.0",
                details="Failed administrator login for username: test-user",
            )

        assert result == {"banned": True, "reason": "Too many failed attempts"}
        assert await get_ban_status(ip_address=ip_address)

        event = await fetch_one(
            "SELECT category, request_method, request_path, user_agent FROM audit_log WHERE ip_address = ? AND action = 'admin_login_failed' ORDER BY id DESC LIMIT 1",
            (ip_address,),
        )
        assert event["category"] == "authentication"
        assert event["request_method"] == "POST"
        assert event["request_path"] == "/admin/login"
        assert event["user_agent"] == "Test Browser/1.0"

        filtered_events = await get_audit_log(category="authentication", search=ip_address, limit=20)
        assert any(item["ip_address"] == ip_address for item in filtered_events)

        await register_failed_access(ip_address=ip_address, reason="admin_login_failed")
        bans = await fetch_one("SELECT COUNT(*) AS count FROM user_bans WHERE ip_address = ?", (ip_address,))
        assert bans["count"] == 1
    finally:
        await execute_query("DELETE FROM access_attempts WHERE ip_address = ?", (ip_address,))
        await execute_query("DELETE FROM user_bans WHERE ip_address = ?", (ip_address,))
        await execute_query("DELETE FROM audit_log WHERE ip_address = ?", (ip_address,))
