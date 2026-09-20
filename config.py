import os
from dotenv import load_dotenv

load_dotenv()

# --- SERVER CONFIGURATIONS ---
UDP_IP = "0.0.0.0"
UDP_PORT = int(os.environ.get("UDP_PORT", 6980))
WEB_PORT = int(os.environ.get("WEB_PORT", 8000))
CONFIG_FILE = "vban_config.json"

# --- DATABASE ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATABASE_PATH = os.path.join(DATA_DIR, "vban_bridge.db")

# --- FILE UPLOADS ---
# Step 3: Storing files outside the server root to prevent direct web server access
UPLOAD_BASE = os.environ.get("UPLOAD_BASE", os.path.abspath(os.path.join(BASE_DIR, "..", "vban_data_uploads")))
UPLOAD_DIR = os.path.join(UPLOAD_BASE, "mp3")
QUARANTINE_DIR = os.path.join(UPLOAD_BASE, "quarantine")
MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", 50))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".mp3"}

# --- AUDIO PLAYBACK ---
FFPLAY_PATH = os.environ.get("FFPLAY_PATH", "ffplay")  # assumes ffplay is in PATH

# --- SECURITY CONFIGURATIONS ---
SESSION_TIMEOUT_MINUTES = int(os.environ.get("SESSION_TIMEOUT_MINUTES", 30))
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("MAX_REQUESTS_PER_MINUTE", 60))
LINK_EXPIRY_MINUTES = int(os.environ.get("LINK_EXPIRY_MINUTES", 10))

# --- ADMIN CREDENTIALS ---
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "super-secret-admin-key-change-me")
SUPER_ADMIN_USERNAME = os.environ.get("SUPER_ADMIN_USERNAME", "admin")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "changeme123")

# --- CLOUDFLARE ---
CLOUDFLARE_TUNNEL_TOKEN = os.environ.get("CLOUDFLARE_TUNNEL_TOKEN", "")
DOMAIN = os.environ.get("DOMAIN", "localhost")
