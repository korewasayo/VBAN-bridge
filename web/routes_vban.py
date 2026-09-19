"""VBAN route management API endpoints.

Handles VBAN audio routing configuration: add, toggle, delete routes.
"""
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse
from security.rbac import require_auth
import vban_engine

router = APIRouter(prefix="/api/vban", tags=["vban"])


@router.get("/status")
async def get_status(user: dict = Depends(require_auth)):
    """Get all VBAN routes and their status."""
    return vban_engine.get_routes()


@router.post("/toggle/{source_ip}/{stream_name}/{dest_ip}")
async def toggle_route(
    source_ip: str,
    stream_name: str,
    dest_ip: str,
    user: dict = Depends(require_auth),
):
    """Toggle a VBAN route on/off."""
    try:
        new_state = vban_engine.toggle_route(source_ip, stream_name, dest_ip)
        return {"status": "success", "new_state": new_state}
    except KeyError:
        raise HTTPException(status_code=404, detail="Route not found")


@router.delete("/delete/{source_ip}/{stream_name}/{dest_ip}")
async def delete_route(
    source_ip: str,
    stream_name: str,
    dest_ip: str,
    user: dict = Depends(require_auth),
):
    """Delete a VBAN route."""
    try:
        vban_engine.delete_route(source_ip, stream_name, dest_ip)
        return {"status": "success"}
    except KeyError:
        raise HTTPException(status_code=404, detail="Route not found")


@router.post("/add")
async def add_route(
    source_ip: str = Form(...),
    stream_name: str = Form(...),
    dest_ip: str = Form(...),
    new_name: str = Form(...),
    user: dict = Depends(require_auth),
):
    """Add a new VBAN route."""
    source_ip = source_ip.strip()
    stream_name = stream_name[:16].strip()
    new_name = new_name[:16].strip()

    try:
        vban_engine.add_route(source_ip, stream_name, dest_ip, new_name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return RedirectResponse(url="/admin/dashboard", status_code=303)
