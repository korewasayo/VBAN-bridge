"""FastAPI application factory for VBAN-Bridge.

Sets up middleware, mounts routers, serves static files and templates.
"""
import os
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from config import BASE_DIR
from security.rate_limiter import rate_limiter


def get_client_ip(request: Request) -> str:
    """Extract real client IP, accounting for Cloudflare and reverse proxies."""
    return (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.client.host
    )


def create_application(lifespan: Callable) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="VBAN-Bridge — Music Request System",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # --- MIDDLEWARE ---

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        """Rate limit by client IP."""
        client_ip = get_client_ip(request)
        if not rate_limiter.is_allowed(client_ip):
            return HTMLResponse("Rate limit exceeded. Please wait.", status_code=429)
        response = await call_next(request)
        return response

    @app.middleware("http")
    async def csrf_and_origin_middleware(request: Request, call_next):
        """Reject cross-site state-changing requests and add hardening headers."""
        method = request.method.upper()
        if method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("Origin")
            referer = request.headers.get("Referer")
            host = request.url.netloc
            allowed_origin = True

            if origin:
                allowed_origin = origin.rstrip("/") in {f"http://{host}", f"https://{host}"}
            elif referer:
                try:
                    from urllib.parse import urlparse
                    referer_host = urlparse(referer).netloc
                    allowed_origin = referer_host == host
                except Exception:
                    allowed_origin = False

            if not allowed_origin:
                return HTMLResponse("Forbidden: invalid origin.", status_code=403)

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Vary"] = "Origin, Referer"
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        )
        response.headers["Content-Security-Policy"] = csp
        return response

    # --- STATIC FILES ---
    static_dir = os.path.join(BASE_DIR, "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # --- ROUTERS ---
    from web.routes_auth import router as auth_router
    from web.routes_admin import router as admin_router
    from web.routes_vban import router as vban_router
    from web.routes_links import router as links_router
    from web.routes_requests import router as requests_router

    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(vban_router)
    app.include_router(links_router)
    app.include_router(requests_router)

    return app
