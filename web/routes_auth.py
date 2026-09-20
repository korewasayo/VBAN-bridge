import os
import secrets
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from security.auth import validate_and_consume_link
from security.tokens import generate_session_token, invalidate_token
from security.passwords import verify_password
from database.db import fetch_one, execute_query
from database.models import add_audit_log

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))

def get_client_ip(request: Request) -> str:
    return (request.headers.get("CF-Connecting-IP") or 
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or 
            request.client.host)

@router.get("/")
async def root_redirect():
    return RedirectResponse(url="/request", status_code=303)

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, token: str = None):
    if token:
        valid_link = await validate_and_consume_link(token)
        if valid_link:
            guest_username = f"guest_{secrets.token_hex(4)}"
            user_id = await execute_query(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'user')", 
                (guest_username, "")
            )
            
            ip = get_client_ip(request)
            session_token = await generate_session_token(user_id, ip)
            
            response = RedirectResponse(url="/request", status_code=303)
            response.set_cookie(key="session_token", value=session_token, httponly=True, secure=True, samesite="strict")
            await add_audit_log(user_id, "user_login", "Logged in via access link", ip)
            return response
            
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})

@router.post("/admin/login")
async def admin_login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = await fetch_one("SELECT id, password_hash, role, is_active FROM users WHERE username = ?", (username,))
    ip = get_client_ip(request)
    
    if user and user["is_active"] and verify_password(password, user["password_hash"]):
        session_token = await generate_session_token(user["id"], ip)
        response = RedirectResponse(url="/admin/dashboard", status_code=303)
        response.set_cookie(key="session_token", value=session_token, httponly=True, secure=True, samesite="strict")
        await add_audit_log(user["id"], "admin_login", "Admin login successful", ip)
        return response
    
    await add_audit_log(None, "admin_login_failed", f"Failed login attempt for {username}", ip)
    return templates.TemplateResponse("admin_login.html", {"request": request, "error": "Invalid username or password"})

@router.post("/login")
async def legacy_login(request: Request, token: str = Form(...)):
    valid_link = await validate_and_consume_link(token)
    if valid_link:
        guest_username = f"guest_{secrets.token_hex(4)}"
        user_id = await execute_query(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'user')", 
            (guest_username, "")
        )
        
        ip = get_client_ip(request)
        session_token = await generate_session_token(user_id, ip)
        
        response = RedirectResponse(url="/request", status_code=303)
        response.set_cookie(key="session_token", value=session_token, httponly=True, secure=True, samesite="strict")
        await add_audit_log(user_id, "user_login", "Logged in via OTP form", ip)
        return response
        
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid or expired token"})

@router.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("session_token")
    if token:
        await invalidate_token(token)
    
    response = RedirectResponse(url="/request", status_code=303)
    response.delete_cookie("session_token", secure=True, httponly=True)
    return response
