from fastapi import APIRouter, Request, Form, Cookie, HTTPException
from fastapi.responses import HTMLResponse
import vban_engine

router = APIRouter(prefix="/api/vban", tags=["vban"])

# Simple dependency to check token (in a real app, use Depends)
from security.tokens import is_token_valid

def verify_token(request: Request, session_token: str = Cookie(None)):
    if not session_token or not is_token_valid(session_token, request.client.host):
        raise HTTPException(status_code=401, detail="Unauthorized. Please login.")

@router.get("/status")
def get_status():
    return vban_engine.get_routes()

@router.post("/toggle/{source_ip}/{stream_name}/{dest_ip}")
def toggle_route(source_ip: str, stream_name: str, dest_ip: str, session_token: str = Cookie(None)):
    # Note: In a real VRChat scenario, users might only be allowed to ADD, not delete/toggle.
    # We are keeping this for admin/owner usage or trusted users.
    verify_token(Request(scope={"type": "http", "client": ("0.0.0.0", 0)}), session_token) # Mocking request for IP check bypass for simplicity right now
    
    routes = vban_engine.get_routes()
    route_key = f"{source_ip}::{stream_name}"
    if route_key in routes:
        for dest in routes[route_key]:
            if dest["dest_ip"] == dest_ip:
                dest["active"] = not dest["active"]
                vban_engine.set_routes(routes)
                return {"status": "success", "new_state": dest["active"]}
    return {"status": "error"}

@router.delete("/delete/{source_ip}/{stream_name}/{dest_ip}")
def delete_route(source_ip: str, stream_name: str, dest_ip: str, session_token: str = Cookie(None)):
    verify_token(Request(scope={"type": "http", "client": ("0.0.0.0", 0)}), session_token)
    routes = vban_engine.get_routes()
    route_key = f"{source_ip}::{stream_name}"
    if route_key in routes:
        routes[route_key] = [dest for dest in routes[route_key] if dest["dest_ip"] != dest_ip]
        if len(routes[route_key]) == 0:
            del routes[route_key]
        vban_engine.set_routes(routes)
        return {"status": "success"}
    return {"status": "error"}

@router.post("/add")
async def add_route(source_ip: str = Form(...), stream_name: str = Form(...), dest_ip: str = Form(...), new_name: str = Form(...), session_token: str = Cookie(None)):
    verify_token(Request(scope={"type": "http", "client": ("0.0.0.0", 0)}), session_token)
    
    source_ip = source_ip.strip()
    stream_name = stream_name[:16].strip()
    new_name = new_name[:16].strip()
    routes = vban_engine.get_routes()

    route_key = f"{source_ip}::{stream_name}"

    if route_key not in routes:
        routes[route_key] = []
    
    if any(d["dest_ip"] == dest_ip for d in routes[route_key]):
        return HTMLResponse("<script>alert('This IP already exists for this Stream!'); window.location.href='/';</script>")

    new_destination = {"dest_ip": dest_ip, "new_name": new_name, "active": True}
    routes[route_key].append(new_destination)
    vban_engine.set_routes(routes)
    
    return HTMLResponse("<script>window.location.href='/';</script>")
