"""VBAN route management API endpoints.

Handles VBAN audio routing configuration: add, toggle, delete routes.
"""
from fastapi import APIRouter, Request, Depends, HTTPException, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
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
    routes = vban_engine.get_routes()
    route_key = f"{source_ip}::{stream_name}"

    if route_key in routes:
        for dest in routes[route_key]:
            if dest["dest_ip"] == dest_ip:
                dest["active"] = not dest["active"]
                vban_engine.set_routes(routes)
                return {"status": "success", "new_state": dest["active"]}

    raise HTTPException(status_code=404, detail="Route not found")


@router.delete("/delete/{source_ip}/{stream_name}/{dest_ip}")
async def delete_route(
    source_ip: str,
    stream_name: str,
    dest_ip: str,
    user: dict = Depends(require_auth),
):
    """Delete a VBAN route."""
    routes = vban_engine.get_routes()
    route_key = f"{source_ip}::{stream_name}"

    if route_key in routes:
        routes[route_key] = [
            dest for dest in routes[route_key] if dest["dest_ip"] != dest_ip
        ]
        if len(routes[route_key]) == 0:
            del routes[route_key]
        vban_engine.set_routes(routes)
        return {"status": "success"}

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
    routes = vban_engine.get_routes()

    route_key = f"{source_ip}::{stream_name}"

    if route_key not in routes:
        routes[route_key] = []

    if any(d["dest_ip"] == dest_ip for d in routes[route_key]):
        raise HTTPException(
            status_code=409,
            detail="This destination IP already exists for this stream."
        )

    new_destination = {"dest_ip": dest_ip, "new_name": new_name, "active": True}
    routes[route_key].append(new_destination)
    vban_engine.set_routes(routes)

    return RedirectResponse(url="/admin/dashboard", status_code=303)
