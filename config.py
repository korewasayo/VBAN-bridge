import os

# --- SERVER CONFIGURATIONS ---
UDP_IP = "0.0.0.0"
UDP_PORT = 6980
WEB_PORT = 8000
CONFIG_FILE = "vban_config.json"

# --- SECURITY CONFIGURATIONS ---
SESSION_TIMEOUT_MINUTES = 30
MAX_REQUESTS_PER_MINUTE = 60

# Admin credentials (in a real app, use environment variables)
# For now, this is a hardcoded secret to generate OTPs
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "super-secret-admin-key-change-me")
