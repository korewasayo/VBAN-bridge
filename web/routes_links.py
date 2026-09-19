from fastapi import APIRouter, Request, Depends, HTTPException

from security.auth import generate_access_link, get_all_links, revoke_link
from security.rbac import require_permission
from config import DOMAIN
from database.models import add_audit_log

router = APIRouter()

def get_client_ip(request: Request) -> str:
    return (request.headers.get("CF-Connecting-IP") or 
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or 
            request.client.host)

@router.post("/admin/api/links/generate")
async def generate_links(request: Request, data: dict, user: dict = Depends(require_permission("generate_links"))):
    count = data.get("count", 1)
    expiry_minutes = data.get("expiry_minutes")
    
    urls = []
    base_url = f"https://{DOMAIN}/" if DOMAIN != "localhost" else "http://localhost:8000/"
    
    for _ in range(count):
        token = await generate_access_link(created_by=user["id"], expiry_minutes=expiry_minutes)
        urls.append(f"{base_url}?token={token}")
        
    ip = get_client_ip(request)
    await add_audit_log(user["id"], "generate_links", f"Generated {count} access link(s)", ip)
    
    return {"urls": urls}

@router.get("/admin/api/links")
async def list_links(user: dict = Depends(require_permission("generate_links"))):
    links = await get_all_links()
    return links

@router.delete("/admin/api/links/{link_id}")
async def delete_link(request: Request, link_id: int, user: dict = Depends(require_permission("generate_links"))):
    success = await revoke_link(link_id)
    if not success:
        raise HTTPException(status_code=404, detail="Link not found or already revoked")
        
    ip = get_client_ip(request)
    await add_audit_log(user["id"], "revoke_link", f"Revoked link {link_id}", ip)
    return {"status": "success"}
