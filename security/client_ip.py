"""Client IP extraction for a local reverse-proxy deployment."""
import ipaddress
from fastapi import Request


def _parse_ip(value: str):
    try:
        return ipaddress.ip_address(value.strip())
    except (ValueError, AttributeError):
        return None


def get_client_ip(request: Request) -> str:
    """Trust forwarding headers only when the TCP peer is a loopback proxy."""
    peer_host = request.client.host if request.client else ""
    peer_ip = _parse_ip(peer_host)
    if not peer_ip:
        return peer_host or "unknown"

    if peer_ip.is_loopback:
        forwarded_ip = _parse_ip(request.headers.get("CF-Connecting-IP", ""))
        if not forwarded_ip:
            forwarded_ip = _parse_ip(request.headers.get("X-Forwarded-For", "").split(",", 1)[0])
        if forwarded_ip:
            return forwarded_ip.compressed

    return peer_ip.compressed
