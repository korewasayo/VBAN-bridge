import time
from collections import OrderedDict
from config import MAX_REQUESTS_PER_MINUTE

class RateLimiter:
    def __init__(self, max_requests=MAX_REQUESTS_PER_MINUTE, window_seconds=60, max_tracked_ips=10000):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_tracked_ips = max_tracked_ips
        self.requests = OrderedDict()
        self.last_rejection_log = OrderedDict()

    def is_allowed(self, ip: str) -> bool:
        now = time.monotonic()
        if ip not in self.requests:
            if len(self.requests) >= self.max_tracked_ips:
                evicted_ip, _ = self.requests.popitem(last=False)
                self.last_rejection_log.pop(evicted_ip, None)
            self.requests[ip] = []

        self.requests.move_to_end(ip)
        recent_requests = [timestamp for timestamp in self.requests[ip] if now - timestamp < self.window_seconds]
        self.requests[ip] = recent_requests

        if len(recent_requests) >= self.max_requests:
            return False

        recent_requests.append(now)
        return True

    def should_log_rejection(self, ip: str, interval_seconds: int = 10) -> bool:
        """Avoid flooding logs when one client keeps exceeding its request limit."""
        now = time.monotonic()
        last_logged = self.last_rejection_log.get(ip)
        if last_logged is not None and now - last_logged < interval_seconds:
            return False

        if ip not in self.last_rejection_log and len(self.last_rejection_log) >= self.max_tracked_ips:
            self.last_rejection_log.popitem(last=False)
        self.last_rejection_log[ip] = now
        self.last_rejection_log.move_to_end(ip)
        return True

# Global instance
rate_limiter = RateLimiter()
