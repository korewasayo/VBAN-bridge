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
    CREATE TABLE IF NOT EXISTS invite_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        created_by INTEGER NOT NULL,
        role TEXT NOT NULL DEFAULT 'guest',
        expires_at TEXT NOT NULL,
        max_uses INTEGER NOT NULL DEFAULT 1,
        used_count INTEGER NOT NULL DEFAULT 0,
        allow_uploads INTEGER NOT NULL DEFAULT 1,
        allow_urls INTEGER NOT NULL DEFAULT 1,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (created_by) REFERENCES users(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS access_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        ip_address TEXT,
        reason TEXT NOT NULL DEFAULT 'invalid_access',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS user_bans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        ip_address TEXT,
        reason TEXT NOT NULL DEFAULT 'security_violation',
        banned_until TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
        is_looping INTEGER NOT NULL DEFAULT 0,
        thumbnail_url TEXT,
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
        category TEXT NOT NULL DEFAULT 'system',
        request_method TEXT,
        request_path TEXT,
        user_agent TEXT,
        timestamp TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """
]

async def init_db() -> None:
    """Initialize the database by creating all tables if they do not exist."""
    for sql in TABLES_SQL:
        await execute_query(sql)
    
    # Migrations
    for stmt in [
        "ALTER TABLE audit_log ADD COLUMN category TEXT NOT NULL DEFAULT 'system'",
        "ALTER TABLE audit_log ADD COLUMN request_method TEXT",
        "ALTER TABLE audit_log ADD COLUMN request_path TEXT",
        "ALTER TABLE audit_log ADD COLUMN user_agent TEXT",
    ]:
        try:
            await execute_query(stmt)
        except Exception:
            pass

    await execute_query("CREATE INDEX IF NOT EXISTS idx_audit_log_category_timestamp ON audit_log(category, timestamp)")
    await execute_query(
        """UPDATE audit_log SET category = CASE
               WHEN action LIKE '%ban%' OR action LIKE '%rate_limit%' OR action LIKE '%security%' THEN 'security'
               WHEN action LIKE '%login%' OR action LIKE '%failed_access%' OR action LIKE '%invalid_code%' THEN 'authentication'
               WHEN action LIKE '%link%' OR action LIKE '%invite%' THEN 'access'
               WHEN action LIKE '%request%' OR action LIKE '%upload%' OR action LIKE '%download%' OR action LIKE '%play%' OR action LIKE '%stop%' THEN 'media'
               WHEN action LIKE '%user%' OR action LIKE '%role%' OR action LIKE '%password%' THEN 'administration'
               ELSE 'system'
           END WHERE category = 'system'"""
    )

    try:
        await execute_query("ALTER TABLE music_requests ADD COLUMN thumbnail_url TEXT;")
    except Exception:
        pass

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

    for stmt in [
        "CREATE TABLE IF NOT EXISTS invite_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, created_by INTEGER NOT NULL, role TEXT NOT NULL DEFAULT 'guest', expires_at TEXT NOT NULL, max_uses INTEGER NOT NULL DEFAULT 1, used_count INTEGER NOT NULL DEFAULT 0, allow_uploads INTEGER NOT NULL DEFAULT 1, allow_urls INTEGER NOT NULL DEFAULT 1, is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY (created_by) REFERENCES users(id))",
        "CREATE TABLE IF NOT EXISTS access_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, ip_address TEXT, reason TEXT NOT NULL DEFAULT 'invalid_access', created_at TEXT NOT NULL DEFAULT (datetime('now')))",
        "CREATE TABLE IF NOT EXISTS user_bans (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, ip_address TEXT, reason TEXT NOT NULL DEFAULT 'security_violation', banned_until TEXT, is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT (datetime('now')) )"
    ]:
        try:
            await execute_query(stmt)
        except Exception:
            pass
        pass

async def seed_super_admin(username: str, password_hash: str) -> None:
    """Seed the super admin user if not already present, or update password to match config."""
    clean_username = username.strip()
    existing_user = await fetch_one("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (clean_username,))
    if not existing_user:
        await execute_query(
            "INSERT INTO users (username, password_hash, role, is_active) VALUES (?, ?, 'super_admin', 1)",
            (clean_username, password_hash)
        )
    else:
        await execute_query(
            "UPDATE users SET username = ?, password_hash = ?, is_active = 1, role = 'super_admin' WHERE id = ?",
            (clean_username, password_hash, existing_user["id"])
        )

def get_audit_category(action: str) -> str:
    """Group audit actions into categories that are useful for filtering."""
    action_name = action.lower()
    if any(term in action_name for term in ("ban", "rate_limit", "security", "suspicious")):
        return "security"
    if any(term in action_name for term in ("login", "authentication", "failed_access", "invalid_code")):
        return "authentication"
    if any(term in action_name for term in ("link", "invite")):
        return "access"
    if any(term in action_name for term in ("request", "upload", "download", "play", "stop")):
        return "media"
    if any(term in action_name for term in ("user", "role", "password")):
        return "administration"
    return "system"


async def add_audit_log(
    user_id: Optional[int],
    action: str,
    details: Optional[str],
    ip_address: Optional[str],
    category: Optional[str] = None,
    request_method: Optional[str] = None,
    request_path: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Add a categorized audit entry with optional request context."""
    await execute_query(
        "INSERT INTO audit_log (user_id, action, details, ip_address, category, request_method, request_path, user_agent) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, action, details, ip_address, category or get_audit_category(action), request_method, request_path, user_agent),
    )
