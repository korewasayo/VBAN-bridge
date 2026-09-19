"""Session token management for VBAN-Bridge.

DB-backed sessions with IP binding and sliding expiration.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict
from config import SESSION_TIMEOUT_MINUTES
from database.db import execute_query, fetch_one


async def generate_session_token(user_id: int, ip: str) -> str:
    """Create a new session for a user, stored in DB."""
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(minutes=SESSION_TIMEOUT_MINUTES)).isoformat()
    
    await execute_query(
        "INSERT INTO sessions (user_id, token, ip_address, expires_at) VALUES (?, ?, ?, ?)",
        (user_id, token, ip, expires_at)
    )
    return token


async def is_token_valid(token: str, ip: str = None) -> bool:
    """Check if a session token is valid."""
    session = await fetch_one(
        "SELECT id, user_id, ip_address, expires_at FROM sessions WHERE token = ?",
        (token,)
    )
    
    if not session:
        return False
    
    # IP binding check
    if ip and session["ip_address"] and session["ip_address"] != ip:
        return False
    
    # Check expiration
    expires_at = datetime.fromisoformat(session["expires_at"])
    if datetime.utcnow() > expires_at:
        # Clean up expired session
        await execute_query("DELETE FROM sessions WHERE id = ?", (session["id"],))
        return False
    
    # Sliding session - refresh expiry
    new_expires = (datetime.utcnow() + timedelta(minutes=SESSION_TIMEOUT_MINUTES)).isoformat()
    await execute_query(
        "UPDATE sessions SET expires_at = ? WHERE id = ?",
        (new_expires, session["id"])
    )
    return True


async def get_session_user(token: str, ip: str = None) -> Optional[Dict]:
    """Get the user associated with a session token.
    Returns dict with id, username, role or None."""
    row = await fetch_one(
        """SELECT s.id as session_id, s.ip_address, s.expires_at,
                  u.id as user_id, u.username, u.role, u.is_active
           FROM sessions s
           JOIN users u ON s.user_id = u.id
           WHERE s.token = ?""",
        (token,)
    )
    
    if not row:
        return None
    
    # Check user is active
    if not row["is_active"]:
        return None
    
    # IP binding check
    if ip and row["ip_address"] and row["ip_address"] != ip:
        return None
    
    # Check expiration
    expires_at = datetime.fromisoformat(row["expires_at"])
    if datetime.utcnow() > expires_at:
        await execute_query("DELETE FROM sessions WHERE id = ?", (row["session_id"],))
        return None
    
    # Sliding session - refresh expiry
    new_expires = (datetime.utcnow() + timedelta(minutes=SESSION_TIMEOUT_MINUTES)).isoformat()
    await execute_query(
        "UPDATE sessions SET expires_at = ? WHERE id = ?",
        (new_expires, row["session_id"])
    )
    
    return {
        "id": row["user_id"],
        "username": row["username"],
        "role": row["role"]
    }


async def invalidate_token(token: str) -> None:
    """Delete a session token."""
    await execute_query("DELETE FROM sessions WHERE token = ?", (token,))


async def invalidate_all_user_sessions(user_id: int) -> None:
    """Delete all sessions for a user (e.g., after password change)."""
    await execute_query("DELETE FROM sessions WHERE user_id = ?", (user_id,))


async def cleanup_expired_sessions() -> int:
    """Remove all expired sessions from DB. Returns count removed."""
    await execute_query(
        "DELETE FROM sessions WHERE expires_at < datetime('now')"
    )
    return 0  # count not easily tracked
