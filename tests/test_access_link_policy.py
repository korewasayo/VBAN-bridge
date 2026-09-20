import pytest

from database.db import execute_query
from security.auth import can_user_upload_for_link


@pytest.mark.asyncio
async def test_can_user_upload_for_link_enforces_cooldown_and_user_cap():
    await execute_query("DELETE FROM music_requests")
    await execute_query("DELETE FROM access_links")
    await execute_query("DELETE FROM users")

    link_id = await execute_query(
        "INSERT INTO access_links (token, created_by, expires_at, purpose, allowed_role, max_uses, used_count, per_ip_limit, per_user_agent_limit, quota_window_minutes, is_public, per_user_limit, cooldown_minutes, max_uploads_per_window, upload_window_minutes) VALUES (?, ?, datetime('now', '+1 day'), 'upload', 'guest', 10, 0, 1, 1, 60, 1, 2, 5, 1, 5)",
        ("test_link_policy_1", 1),
    )

    user_id = await execute_query(
        "INSERT INTO users (username, password_hash, role, source_link_id) VALUES (?, ?, 'guest', ?)",
        ("guest_policy_user", "", link_id),
    )

    await execute_query(
        "INSERT INTO music_requests (user_id, title, artist, status, source_type, created_at) VALUES (?, ?, ?, 'approved', 'upload', datetime('now'))",
        (user_id, "First Upload", "Tester"),
    )

    allowed, reason = await can_user_upload_for_link(user_id, link_id)
    assert not allowed
    assert "cooldown" in reason.lower() or "within" in reason.lower()

    other_user_id = await execute_query(
        "INSERT INTO users (username, password_hash, role, source_link_id) VALUES (?, ?, 'guest', ?)",
        ("guest_policy_user_2", "", link_id),
    )

    allowed, reason = await can_user_upload_for_link(other_user_id, link_id)
    assert allowed
    assert reason == ""
