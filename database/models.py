from typing import Optional
from .db import execute_query, fetch_one

TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('super_admin', 'admin', 'moderator', 'user', 'guest')),
        is_active INTEGER NOT NULL DEFAULT 1,
        source_link_id INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (source_link_id) REFERENCES access_links(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT UNIQUE NOT NULL,
        ip_address TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        expires_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS access_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE NOT NULL,
        created_by INTEGER NOT NULL,
        used_by INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        used_at TEXT,
        expires_at TEXT NOT NULL,
        is_used INTEGER NOT NULL DEFAULT 0,
        purpose TEXT NOT NULL DEFAULT 'login',
        allowed_role TEXT NOT NULL DEFAULT 'guest',
        max_uses INTEGER NOT NULL DEFAULT 1,
        used_count INTEGER NOT NULL DEFAULT 0,
        per_ip_limit INTEGER NOT NULL DEFAULT 1,
        per_user_agent_limit INTEGER NOT NULL DEFAULT 1,
        per_user_limit INTEGER NOT NULL DEFAULT 1,
        quota_window_minutes INTEGER NOT NULL DEFAULT 60,
        cooldown_minutes INTEGER NOT NULL DEFAULT 0,
        max_uploads_per_window INTEGER NOT NULL DEFAULT 1,
        upload_window_minutes INTEGER NOT NULL DEFAULT 60,
        is_public INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (created_by) REFERENCES users(id),
        FOREIGN KEY (used_by) REFERENCES users(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS access_link_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        link_id INTEGER NOT NULL,
        ip_address TEXT,
        user_agent_hash TEXT,
        used_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (link_id) REFERENCES access_links(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS music_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT NOT NULL,
        artist TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected', 'playing', 'played')),
        mp3_path TEXT,
        duration_seconds REAL NOT NULL DEFAULT 0,
        source_type TEXT NOT NULL DEFAULT 'text_request' CHECK(source_type IN ('upload', 'text_request')),
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        reviewed_by INTEGER,
        reviewed_at TEXT,
        reject_reason TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (reviewed_by) REFERENCES users(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS audio_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        source_ip TEXT NOT NULL,
        stream_name TEXT NOT NULL,
        dest_ip TEXT NOT NULL,
        dest_port INTEGER NOT NULL DEFAULT 6980,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_by INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (created_by) REFERENCES users(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        details TEXT,
        ip_address TEXT,
        timestamp TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """
]

async def init_db() -> None:
    """Initialize the database by creating all tables if they do not exist."""
    for sql in TABLES_SQL:
        await execute_query(sql)

    # Migration for older databases that predate the stricter guest-link model.
    for stmt in [
        "ALTER TABLE access_links ADD COLUMN purpose TEXT NOT NULL DEFAULT 'login'",
        "ALTER TABLE access_links ADD COLUMN allowed_role TEXT NOT NULL DEFAULT 'guest'",
        "ALTER TABLE access_links ADD COLUMN max_uses INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE access_links ADD COLUMN used_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE access_links ADD COLUMN per_ip_limit INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE access_links ADD COLUMN per_user_agent_limit INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE access_links ADD COLUMN per_user_limit INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE access_links ADD COLUMN quota_window_minutes INTEGER NOT NULL DEFAULT 60",
        "ALTER TABLE access_links ADD COLUMN cooldown_minutes INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE access_links ADD COLUMN max_uploads_per_window INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE access_links ADD COLUMN upload_window_minutes INTEGER NOT NULL DEFAULT 60",
        "ALTER TABLE access_links ADD COLUMN is_public INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN source_link_id INTEGER",
        "ALTER TABLE music_requests ADD COLUMN duration_seconds REAL NOT NULL DEFAULT 0",
    ]:
        try:
            await execute_query(stmt)
        except Exception:
            pass

    try:
        await execute_query(
            "CREATE TABLE IF NOT EXISTS access_link_usage (id INTEGER PRIMARY KEY AUTOINCREMENT, link_id INTEGER NOT NULL, ip_address TEXT, user_agent_hash TEXT, used_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY (link_id) REFERENCES access_links(id))"
        )
    except Exception:
        pass

async def seed_super_admin(username: str, password_hash: str) -> None:
    """Seed the super admin user if not already present."""
    existing_user = await fetch_one("SELECT id FROM users WHERE username = ?", (username,))
    if not existing_user:
        await execute_query(
            "INSERT INTO users (username, password_hash, role, is_active) VALUES (?, ?, 'super_admin', 1)",
            (username, password_hash)
        )

async def add_audit_log(user_id: Optional[int], action: str, details: Optional[str], ip_address: Optional[str]) -> None:
    """Add a new audit log entry."""
    await execute_query(
        "INSERT INTO audit_log (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)",
        (user_id, action, details, ip_address)
    )
