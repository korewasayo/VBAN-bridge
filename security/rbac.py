"""Role-Based Access Control (RBAC) system for VBAN-Bridge."""
from functools import wraps
from fastapi import Request, HTTPException, Cookie
from typing import Optional

# Role hierarchy: higher roles inherit lower role permissions
ROLE_HIERARCHY = {
    "super_admin": 4,
    "admin": 3,
    "moderator": 2,
    "user": 1,
}

PERMISSIONS = {
    "super_admin": [
        "manage_requests", "manage_channels", "manage_users", 
        "manage_roles", "generate_links", "view_dashboard",
        "submit_request", "view_queue", "manage_system"
    ],
    "admin": [
        "manage_requests", "manage_channels", "manage_users",
        "generate_links", "view_dashboard",
        "submit_request", "view_queue"
    ],
    "moderator": [
        "manage_requests", "view_dashboard",
        "submit_request", "view_queue"
    ],
    "user": [
        "submit_request", "view_queue"
    ],
}


def has_permission(role: str, permission: str) -> bool:
    """Check if a role has a specific permission."""
    if role not in PERMISSIONS:
        return False
    return permission in PERMISSIONS[role]


def has_minimum_role(user_role: str, required_role: str) -> bool:
    """Check if user's role meets or exceeds the required role level."""
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    required_level = ROLE_HIERARCHY.get(required_role, 999)
    return user_level >= required_level


async def get_current_user(request: Request) -> Optional[dict]:
    """Extract and validate the current user from session cookie.
    Returns user dict with id, username, role or None."""
    from security.tokens import get_session_user
    
    token = request.cookies.get("session_token")
    if not token:
        return None
    
    # Get real client IP (Cloudflare sends CF-Connecting-IP)
    client_ip = (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.client.host
    )
    
    user = await get_session_user(token, client_ip)
    return user


async def require_auth(request: Request) -> dict:
    """FastAPI dependency: requires any authenticated user."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_role(*roles: str):
    """FastAPI dependency factory: requires user to have one of the specified roles.
    Usage: Depends(require_role('admin', 'super_admin'))
    """
    async def dependency(request: Request) -> dict:
        user = await get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if user["role"] not in roles and not has_minimum_role(user["role"], min(roles, key=lambda r: ROLE_HIERARCHY.get(r, 999))):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency


def require_permission(permission: str):
    """FastAPI dependency factory: requires user to have a specific permission.
    Usage: Depends(require_permission('manage_requests'))
    """
    async def dependency(request: Request) -> dict:
        user = await get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not has_permission(user["role"], permission):
            raise HTTPException(status_code=403, detail=f"Permission '{permission}' required")
        return user
    return dependency
