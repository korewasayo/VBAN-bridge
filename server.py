"""VBAN-Bridge Server Entry Point.

Starts the VBAN audio engine, initializes the database,
seeds the super admin, and runs the FastAPI web server.
Optionally starts a Cloudflare Tunnel.
"""
import argparse
import asyncio
import logging
import os
import sys
import threading
from contextlib import asynccontextmanager

import uvicorn

from config import (
    WEB_PORT, SUPER_ADMIN_USERNAME, SUPER_ADMIN_PASSWORD,
    UPLOAD_DIR, QUARANTINE_DIR, DATA_DIR
)
from database.models import init_db, seed_super_admin
from security.passwords import hash_password
from vban_engine import start_background_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    """Application lifespan: startup and shutdown hooks."""
    # --- STARTUP ---
    logger.info("🗄️  Initializing database...")
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(QUARANTINE_DIR, exist_ok=True)

    await init_db()

    # Seed super admin
    pw_hash = hash_password(SUPER_ADMIN_PASSWORD)
    await seed_super_admin(SUPER_ADMIN_USERNAME, pw_hash)
    logger.info(f"👑 Super admin '{SUPER_ADMIN_USERNAME}' ready.")

    # Start VBAN engine in background thread
    vban_thread = threading.Thread(target=start_background_router, daemon=True)
    vban_thread.start()
    logger.info("🎧 VBAN Audio Engine started.")

    yield  # App is running

    # --- SHUTDOWN ---
    from database.db import Database
    await Database.close()
    logger.info("🛑 Server shutting down.")


def create_app():
    """Create the FastAPI app with lifespan."""
    from web.app import create_application
    return create_application(lifespan)


def main():
    parser = argparse.ArgumentParser(description="VBAN-Bridge Music Request System")
    parser.add_argument("--tunnel", action="store_true", help="Start Cloudflare Tunnel alongside the server")
    parser.add_argument("--port", type=int, default=WEB_PORT, help=f"Web server port (default: {WEB_PORT})")
    args = parser.parse_args()

    app = create_app()

    if args.tunnel:
        try:
            from tunnel import start_tunnel
            tunnel_thread = threading.Thread(
                target=start_tunnel,
                args=(args.port,),
                daemon=True
            )
            tunnel_thread.start()
            logger.info("🌐 Cloudflare Tunnel starting...")
        except ImportError:
            logger.warning("⚠️  Tunnel module not configured. Running without tunnel.")

    logger.info(f"🌐 Starting Web Dashboard on port {args.port}...")
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
