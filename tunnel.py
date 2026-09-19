"""Cloudflare Tunnel integration for VBAN-Bridge.

Manages a cloudflared tunnel subprocess to expose the local server
to the internet without opening ports or exposing the machine's IP.

Supports two modes:
1. Quick tunnel: `cloudflared tunnel --url http://localhost:PORT`
   (generates a random *.trycloudflare.com URL — good for testing)
2. Named tunnel: `cloudflared tunnel run TUNNEL_NAME`
   (uses a pre-configured tunnel with your custom domain)
"""
import subprocess
import shutil
import logging
import signal
import sys
import threading
from typing import Optional

from config import CLOUDFLARE_TUNNEL_TOKEN

logger = logging.getLogger(__name__)

_tunnel_process: Optional[subprocess.Popen] = None
_shutdown_event = threading.Event()


def find_cloudflared() -> Optional[str]:
    """Find the cloudflared binary in PATH."""
    path = shutil.which("cloudflared")
    if path:
        return path
    
    # Check common Windows install locations
    import os
    common_paths = [
        os.path.expanduser("~\\cloudflared\\cloudflared.exe"),
        "C:\\Program Files\\cloudflared\\cloudflared.exe",
        "C:\\Program Files (x86)\\cloudflared\\cloudflared.exe",
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p
    
    return None


def start_tunnel(port: int = 8000) -> None:
    """Start a Cloudflare Tunnel pointing to the local server.
    
    This function blocks and should be run in a daemon thread.
    If CLOUDFLARE_TUNNEL_TOKEN is set, uses it for a named tunnel.
    Otherwise, starts a quick tunnel with a random URL.
    """
    global _tunnel_process

    cloudflared = find_cloudflared()
    if not cloudflared:
        logger.error(
            "❌ cloudflared not found. Install it:\n"
            "   winget install Cloudflare.cloudflared\n"
            "   or download from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
        )
        return

    try:
        if CLOUDFLARE_TUNNEL_TOKEN:
            # Named tunnel mode (pre-configured with domain)
            cmd = [cloudflared, "tunnel", "run", "--token", CLOUDFLARE_TUNNEL_TOKEN]
            logger.info("🌐 Starting named Cloudflare Tunnel...")
        else:
            # Quick tunnel mode (random URL)
            cmd = [cloudflared, "tunnel", "--url", f"http://localhost:{port}", "--no-autoupdate"]
            logger.info(f"🌐 Starting quick Cloudflare Tunnel → http://localhost:{port}")

        _tunnel_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
        )

        # Read and log tunnel output (captures the assigned URL)
        for line in _tunnel_process.stdout:
            line = line.strip()
            if line:
                # Look for the tunnel URL in quick mode
                if "trycloudflare.com" in line or "https://" in line:
                    logger.info(f"🌐 Tunnel URL: {line}")
                elif "error" in line.lower():
                    logger.error(f"🌐 Tunnel: {line}")
                else:
                    logger.debug(f"🌐 Tunnel: {line}")

            if _shutdown_event.is_set():
                break

        _tunnel_process.wait()
        logger.info("🌐 Cloudflare Tunnel stopped.")

    except FileNotFoundError:
        logger.error("❌ cloudflared binary not found or not executable.")
    except Exception as e:
        logger.error(f"❌ Tunnel error: {e}")


def stop_tunnel() -> None:
    """Stop the running Cloudflare Tunnel."""
    global _tunnel_process
    _shutdown_event.set()

    if _tunnel_process is not None:
        try:
            _tunnel_process.terminate()
            _tunnel_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _tunnel_process.kill()
            _tunnel_process.wait()
        except Exception as e:
            logger.error(f"Error stopping tunnel: {e}")
        finally:
            _tunnel_process = None
            logger.info("🌐 Tunnel process terminated.")


def is_tunnel_running() -> bool:
    """Check if the tunnel process is still running."""
    if _tunnel_process is None:
        return False
    return _tunnel_process.poll() is None
