import os
import secrets
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from security.auth import validate_and_consume_link, get_ban_status, register_failed_access
from security.client_ip import get_client_ip
from security.tokens import generate_session_token, invalidate_token
from security.passwords import verify_password
from database.db import fetch_one, execute_query
from database.models import add_audit_log

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))

def get_user_agent(request: Request) -> str:
    return request.headers.get("User-Agent", "")


def set_session_cookie(response: RedirectResponse, request: Request, session_token: str) -> None:
    is_secure = request.headers.get("X-Forwarded-Proto", request.url.scheme) == "https"
    response.set_cookie(key="session_token", value=session_token, httponly=True, secure=is_secure, samesite="lax")

@router.get("/")
async def root_redirect():
    return RedirectResponse(url="/request", status_code=303)

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, token: str = None, code: str = None):
    ip = get_client_ip(request)
    ban = await get_ban_status(ip_address=ip)
    if ban:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Your access is temporarily blocked."})

    access_value = token or code
    if access_value:
        valid_link = await validate_and_consume_link(
            access_value,
            purpose="login",
            required_role="guest",
            client_ip=ip,
            user_agent=get_user_agent(request),
        )
        if not valid_link:
            from security.auth import validate_invite_code
            invite = await validate_invite_code(access_value, required_role="guest", client_ip=ip, user_agent=get_user_agent(request))
            if invite:
                guest_username = f"guest_{secrets.token_hex(4)}"
                user_id = await execute_query(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    (guest_username, "", invite["role"] or "guest")
                )

                session_token = await generate_session_token(user_id, ip)
                response = RedirectResponse(url="/request", status_code=303)
                set_session_cookie(response, request, session_token)
                await add_audit_log(user_id, "guest_login", "Logged in via invite code", ip)
                return response

            await register_failed_access(
                ip_address=ip,
                reason="invalid_login_code",
                request_method=request.method,
                request_path=request.url.path,
                user_agent=get_user_agent(request),
            )
        else:
            guest_username = f"guest_{secrets.token_hex(4)}"
            user_id = await execute_query(
                "INSERT INTO users (username, password_hash, role, source_link_id) VALUES (?, ?, 'guest', ?)",
                (guest_username, "", valid_link)
            )

            session_token = await generate_session_token(user_id, ip)
            response = RedirectResponse(url="/request", status_code=303)
            set_session_cookie(response, request, session_token)
            await add_audit_log(user_id, "guest_login", "Logged in via access link", ip)
            return response

    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})

@router.post("/admin/login")
async def admin_login(request: Request, username: str = Form(...), password: str = Form(...)):
    ip = get_client_ip(request)
    if await get_ban_status(ip_address=ip):
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "error": "Your access is temporarily blocked."},
            status_code=403,
        )

    clean_username = username.strip()
    user = await fetch_one(
        "SELECT id, username, password_hash, role, is_active FROM users WHERE LOWER(username) = LOWER(?)",
        (clean_username,)
    )
    
    is_valid = False
    if user and user["is_active"]:
        is_valid = verify_password(password, user["password_hash"])

    if is_valid:
        session_token = await generate_session_token(user["id"], ip)
        response = RedirectResponse(url="/admin/dashboard", status_code=303)
        set_session_cookie(response, request, session_token)
        await add_audit_log(user["id"], "admin_login", "Admin login successful", ip)
        return response
    
    safe_username = "".join(char for char in clean_username if char.isprintable())[:120]
    await register_failed_access(
        user_id=user["id"] if user else None,
        ip_address=ip,
        reason="admin_login_failed",
        request_method=request.method,
        request_path=request.url.path,
        user_agent=get_user_agent(request),
        details=f"Failed administrator login for username: {safe_username}",
    )
    return templates.TemplateResponse("admin_login.html", {"request": request, "error": "Invalid username or password"})

@router.post("/login")
async def legacy_login(request: Request, token: str = Form(None), code: str = Form(None)):
    ip = get_client_ip(request)
    ban = await get_ban_status(ip_address=ip)
    if ban:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Your access is temporarily blocked."})

    access_value = token or code
    if not access_value:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Enter a valid access token or code"})

    valid_link = await validate_and_consume_link(
        access_value,
        purpose="login",
        required_role="guest",
        client_ip=ip,
        user_agent=get_user_agent(request),
    )
    if valid_link:
        guest_username = f"guest_{secrets.token_hex(4)}"
        user_id = await execute_query(
            "INSERT INTO users (username, password_hash, role, source_link_id) VALUES (?, ?, 'guest', ?)",
            (guest_username, "", valid_link)
        )

        session_token = await generate_session_token(user_id, ip)
        response = RedirectResponse(url="/request", status_code=303)
        set_session_cookie(response, request, session_token)
        await add_audit_log(user_id, "guest_login", "Logged in via OTP form", ip)
        return response

    from security.auth import validate_invite_code
    invite = await validate_invite_code(access_value, required_role="guest", client_ip=ip, user_agent=get_user_agent(request))
    if invite:
        guest_username = f"guest_{secrets.token_hex(4)}"
        user_id = await execute_query(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (guest_username, "", invite["role"] or "guest")
        )

        session_token = await generate_session_token(user_id, ip)
        response = RedirectResponse(url="/request", status_code=303)
        set_session_cookie(response, request, session_token)
        await add_audit_log(user_id, "guest_login", "Logged in via invite code form", ip)
        return response

    await register_failed_access(
        ip_address=ip,
        reason="invalid_login_code",
        request_method=request.method,
        request_path=request.url.path,
        user_agent=get_user_agent(request),
    )
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid or expired token or code"})

@router.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("session_token")
    if token:
        await invalidate_token(token)
    
    response = RedirectResponse(url="/request", status_code=303)
    response.delete_cookie("session_token", secure=True, httponly=True)
    return response
