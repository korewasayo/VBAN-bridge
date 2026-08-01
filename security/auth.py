import secrets

# In-memory store for valid One-Time Passwords
# We use a set for O(1) lookups
VALID_OTPS = set()

def generate_otp() -> str:
    """Generates a random 8-character OTP and stores it."""
    # Generate a simple 8-character string for easier typing by VRChat users
    otp = secrets.token_hex(4) 
    VALID_OTPS.add(otp)
    return otp

def validate_and_consume_otp(otp: str) -> bool:
    """Checks if an OTP is valid, and if so, deletes it so it can't be reused."""
    if otp in VALID_OTPS:
        VALID_OTPS.remove(otp)
        return True
    return False

def get_active_otps() -> list:
    """Returns a list of currently active OTPs for the admin dashboard."""
    return list(VALID_OTPS)
