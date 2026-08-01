import time
from collections import defaultdict
from config import MAX_REQUESTS_PER_MINUTE

class RateLimiter:
    def __init__(self, max_requests=MAX_REQUESTS_PER_MINUTE, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Stores IP -> list of timestamps
        self.requests = defaultdict(list)

    def is_allowed(self, ip: str) -> bool:
        now = time.time()
        # Clean up old timestamps
        self.requests[ip] = [t for t in self.requests[ip] if now - t < self.window_seconds]
        
        if len(self.requests[ip]) >= self.max_requests:
            return False
            
        self.requests[ip].append(now)
        return True

# Global instance
rate_limiter = RateLimiter()
