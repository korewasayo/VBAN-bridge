import secrets
import time
from config import SESSION_TIMEOUT_MINUTES

# In-memory store for active sessions: { token_string: { "created_at": timestamp, "ip": ip_address } }
ACTIVE_SESSIONS = {}

def generate_session_token(ip: str) -> str:
    token = secrets.token_urlsafe(32)
    ACTIVE_SESSIONS[token] = {
        "created_at": time.time(),
        "ip": ip
    }
    return token

def is_token_valid(token: str, ip: str = None) -> bool:
    if token not in ACTIVE_SESSIONS:
        return False
        
    session = ACTIVE_SESSIONS[token]
    
    # Optional IP binding check (adds extra security)
    if ip and session["ip"] != ip:
        return False
        
    # Check expiration
    age_seconds = time.time() - session["created_at"]
    if age_seconds > (SESSION_TIMEOUT_MINUTES * 60):
        del ACTIVE_SESSIONS[token]
        return False
        
    # Refresh the token (sliding session)
    session["created_at"] = time.time()
    return True

def invalidate_token(token: str):
    if token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[token]
