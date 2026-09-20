import os
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from security.rbac import require_role, require_permission, require_auth
from database.db import fetch_all, fetch_one, execute_query
from database.models import add_audit_log
from security.passwords import hash_password

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))

def get_client_ip(request: Request) -> str:
    return (request.headers.get("CF-Connecting-IP") or 
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or 
            request.client.host)

@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, user: dict = Depends(require_role("admin", "super_admin"))):
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, "user": user})

@router.get("/admin/api/users")
async def get_users(user: dict = Depends(require_permission("manage_users"))):
    users = await fetch_all("SELECT id, username, role, is_active, created_at FROM users")
    return [dict(u) for u in users]

@router.post("/admin/api/users")
async def create_user(request: Request, data: dict, user: dict = Depends(require_permission("manage_users"))):
    username = data.get("username")
    password = data.get("password")
    role = data.get("role", "user")
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
        
    hashed_pw = hash_password(password)
    
    try:
        user_id = await execute_query(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, hashed_pw, role)
        )
        ip = get_client_ip(request)
        await add_audit_log(user["id"], "create_user", f"Created user {username} with role {role}", ip)
        return {"id": user_id, "username": username, "role": role}
    except Exception as e:
        raise HTTPException(status_code=400, detail="Could not create user. Username might already exist.")

@router.delete("/admin/api/users/{user_id}")
async def deactivate_user(request: Request, user_id: int, user: dict = Depends(require_permission("manage_users"))):
    await execute_query("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    ip = get_client_ip(request)
    await add_audit_log(user["id"], "deactivate_user", f"Deactivated user {user_id}", ip)
    return {"status": "success"}

@router.patch("/admin/api/users/{user_id}/role")
async def change_user_role(request: Request, user_id: int, data: dict, user: dict = Depends(require_role("super_admin"))):
    new_role = data.get("role")
    if not new_role:
        raise HTTPException(status_code=400, detail="Role required")
        
    await execute_query("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    ip = get_client_ip(request)
    await add_audit_log(user["id"], "change_role", f"Changed role of user {user_id} to {new_role}", ip)
    return {"status": "success"}

@router.get("/admin/api/audit-log")
async def get_audit_log(user: dict = Depends(require_role("admin", "super_admin"))):
    logs = await fetch_all('''
        SELECT a.id, a.user_id, u.username, a.action, a.details, a.ip_address, a.timestamp 
        FROM audit_log a 
        LEFT JOIN users u ON a.user_id = u.id 
        ORDER BY a.timestamp DESC 
        LIMIT 200
    ''')
    return [dict(row) for row in logs]
