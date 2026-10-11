import os
import shutil
import sys
from dotenv import load_dotenv

# Ensure system error messages (e.g. WinError / Winsock) are formatted in English
if sys.platform == "win32":
    try:
        import ctypes
        MUI_LANGUAGE_NAME = 0x8
        kernel32 = ctypes.windll.kernel32
        kernel32.SetProcessPreferredUILanguages(MUI_LANGUAGE_NAME, ctypes.create_unicode_buffer("en-US\0"), None)
        kernel32.SetThreadUILanguage(0x0409)
    except Exception:
        pass

for env_var in ("LANG", "LANGUAGE", "LC_ALL"):
    os.environ.setdefault(env_var, "en_US.UTF-8")

load_dotenv()


# --- SERVER CONFIGURATIONS ---
UDP_IP = "0.0.0.0"
UDP_PORT = int(os.environ.get("UDP_PORT", 6980))
WEB_PORT = int(os.environ.get("WEB_PORT", 8000))
WEB_HOST = os.environ.get("WEB_HOST", "127.0.0.1")
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

# --- AUDIO / FFMPEG CONFIGURATION ---
_downloader_proxy_values = os.environ.get("DOWNLOADER_PROXIES", "").strip()
if not _downloader_proxy_values:
    _downloader_proxy_values = os.environ.get("DOWNLOADER_PROXY", "").strip()
DOWNLOADER_PROXIES = tuple(proxy.strip() for proxy in _downloader_proxy_values.split(",") if proxy.strip())

def _resolve_ffmpeg_binaries():
    ffmpeg_env = os.environ.get("FFMPEG_PATH", "").strip()
    ffmpeg_bin = None
    ffmpeg_dir = None

    if ffmpeg_env:
        if os.path.isdir(ffmpeg_env):
            ffmpeg_dir = ffmpeg_env
            cand = os.path.join(ffmpeg_dir, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
            ffmpeg_bin = cand if os.path.exists(cand) else ffmpeg_env
        elif os.path.exists(ffmpeg_env):
            ffmpeg_bin = ffmpeg_env
            ffmpeg_dir = os.path.dirname(ffmpeg_env)

    if not ffmpeg_bin:
        cand_which = shutil.which("ffmpeg")
        if cand_which:
            ffmpeg_bin = cand_which
            ffmpeg_dir = os.path.dirname(cand_which)

    if not ffmpeg_bin:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        user_profile = os.environ.get("USERPROFILE", "")
        candidates = [
            os.path.join(BASE_DIR, "bin", "ffmpeg.exe" if os.name == "nt" else "ffmpeg"),
            os.path.join(local_app_data, "Microsoft", "WinGet", "Links", "ffmpeg.exe"),
            os.path.join(user_profile, "scoop", "shims", "ffmpeg.exe"),
            r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
            r"C:\ffmpeg\bin\ffmpeg.exe",
        ]
        for c in candidates:
            if c and os.path.exists(c):
                ffmpeg_bin = c
                ffmpeg_dir = os.path.dirname(c)
                break

    if not ffmpeg_bin and os.environ.get("LOCALAPPDATA"):
        winget_pkgs = os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "WinGet", "Packages")
        if os.path.isdir(winget_pkgs):
            for root, _, files in os.walk(winget_pkgs):
                if "ffmpeg.exe" in files:
                    ffmpeg_bin = os.path.join(root, "ffmpeg.exe")
                    ffmpeg_dir = root
                    break

    if not ffmpeg_bin:
        ffmpeg_bin = "ffmpeg"

    # Ensure the directory containing ffmpeg is on PATH so child processes & yt-dlp find ffmpeg/ffprobe
    if ffmpeg_dir and os.path.isdir(ffmpeg_dir):
        current_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in current_path:
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path

    # FFprobe resolution
    ffprobe_env = os.environ.get("FFPROBE_PATH", "").strip()
    ffprobe_bin = None
    if ffprobe_env and os.path.exists(ffprobe_env):
        ffprobe_bin = ffprobe_env
    elif ffmpeg_dir:
        cand_ffprobe = os.path.join(ffmpeg_dir, "ffprobe.exe" if os.name == "nt" else "ffprobe")
        if os.path.exists(cand_ffprobe):
            ffprobe_bin = cand_ffprobe
    if not ffprobe_bin:
        ffprobe_bin = shutil.which("ffprobe") or "ffprobe"

    # FFplay resolution
    ffplay_env = os.environ.get("FFPLAY_PATH", "").strip()
    ffplay_bin = None
    if ffplay_env and os.path.exists(ffplay_env):
        ffplay_bin = ffplay_env
    elif ffmpeg_dir:
        cand_ffplay = os.path.join(ffmpeg_dir, "ffplay.exe" if os.name == "nt" else "ffplay")
        if os.path.exists(cand_ffplay):
            ffplay_bin = cand_ffplay
    if not ffplay_bin:
        ffplay_bin = shutil.which("ffplay") or "ffplay"

    location = ffmpeg_dir if (ffmpeg_dir and os.path.isdir(ffmpeg_dir)) else ffmpeg_bin
    return ffmpeg_bin, ffprobe_bin, ffplay_bin, location

FFMPEG_PATH, FFPROBE_PATH, FFPLAY_PATH, FFMPEG_LOCATION = _resolve_ffmpeg_binaries()

# --- SECURITY CONFIGURATIONS ---
SESSION_TIMEOUT_MINUTES = int(os.environ.get("SESSION_TIMEOUT_MINUTES", 30))
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("MAX_REQUESTS_PER_MINUTE", 60))
LINK_EXPIRY_MINUTES = int(os.environ.get("LINK_EXPIRY_MINUTES", 10))

# --- ADMIN CREDENTIALS ---
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")
SUPER_ADMIN_USERNAME = os.environ.get("SUPER_ADMIN_USERNAME", "admin")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "")

# --- CLOUDFLARE ---
CLOUDFLARE_TUNNEL_TOKEN = os.environ.get("CLOUDFLARE_TUNNEL_TOKEN", "")
DOMAIN = os.environ.get("DOMAIN", "localhost")
