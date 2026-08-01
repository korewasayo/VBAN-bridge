from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from security.rate_limiter import rate_limiter
from web.routes_vban import router as vban_router
from web.routes_auth import router as auth_router
from web.routes_admin import router as admin_router
from vban_engine import load_config

app = FastAPI(title="VBAN Router Hub - Secure Edition")

@app.on_event("startup")
def startup_event():
    load_config()

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Simple IP extraction (in production behind Cloudflare, use X-Forwarded-For)
    client_ip = request.headers.get("X-Forwarded-For", request.client.host)
    if not rate_limiter.is_allowed(client_ip):
        return HTMLResponse("Rate limit exceeded. Please wait.", status_code=429)
    response = await call_next(request)
    return response

# Include all modular routes
app.include_router(vban_router)
app.include_router(auth_router)
app.include_router(admin_router)

# Mount templates/static if needed (for now we return HTML directly from files in routes)
import os
from security.tokens import is_token_valid

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    token = request.cookies.get("session_token")
    if not token or not is_token_valid(token, request.client.host):
        return RedirectResponse(url="/")
        
    template_path = os.path.join("templates", "dashboard.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Dashboard Template Missing</h1>")
