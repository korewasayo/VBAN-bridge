"""DJ live microphone streaming routes.

Serves the DJ page and handles the WebSocket that receives browser
microphone audio (raw PCM s16le, 48 kHz, stereo) and re-broadcasts it
as VBAN packets to all active route destinations.
"""
import logging
import os
import socket
import struct

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import UDP_PORT, DJ_STREAM_NAME, DJ_SAMPLE_RATE
from security.rbac import require_permission, get_current_user, has_permission
from security.tokens import get_session_user
from security.client_ip import get_client_ip

logger = logging.getLogger("dj_live")

router = APIRouter()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)

# ---- Shared state: only one DJ can stream at a time ----
_active_dj: dict | None = None


async def _ws_authenticate(websocket: WebSocket) -> dict | None:
    """Validate the session cookie attached to the WebSocket handshake.

    WebSocket endpoints cannot use regular FastAPI ``Depends`` for cookie-based
    auth, so we extract and validate the token manually.
    """
    token = websocket.cookies.get("session_token")
    if not token:
        return None
    ip = get_client_ip(websocket)
    user = await get_session_user(token, ip)
    if user and has_permission(user["role"], "live_mic"):
        return user
    return None


# ---- HTTP: serve DJ page ----

@router.get("/dj", response_class=HTMLResponse)
async def dj_page(request: Request, user: dict = Depends(require_permission("live_mic"))):
    """Render the DJ live streaming page."""
    return templates.TemplateResponse("dj_live.html", {
        "request": request,
        "user": user,
        "stream_name": DJ_STREAM_NAME,
        "sample_rate": DJ_SAMPLE_RATE,
    })


@router.get("/api/dj/status")
async def dj_status(user: dict = Depends(require_permission("live_mic"))):
    """Return the current live-stream status."""
    global _active_dj
    if _active_dj:
        return {
            "is_live": True,
            "dj_username": _active_dj["username"],
            "stream_name": DJ_STREAM_NAME,
        }
    return {"is_live": False}


# ---- WebSocket: receive mic audio, emit VBAN ----

@router.websocket("/ws/dj")
async def dj_websocket(websocket: WebSocket):
    """Receive raw PCM audio from the DJ's browser and broadcast via VBAN.

    Protocol (binary frames):
    - Each frame is raw PCM bytes (s16le, 48 kHz, stereo).
    - The server wraps each frame in a VBAN header and sends it to every
      active route destination, using the configured DJ stream name.
    """
    global _active_dj

    user = await _ws_authenticate(websocket)
    if not user:
        await websocket.close(code=4401, reason="Authentication required")
        return

    if _active_dj is not None:
        await websocket.close(
            code=4409,
            reason=f"Another DJ ({_active_dj['username']}) is already live",
        )
        return

    await websocket.accept()
    _active_dj = user
    logger.info("🎤 DJ '%s' started live mic stream.", user["username"])

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    frame_counter = 0
    stream_name_bytes = DJ_STREAM_NAME.encode("ascii")[:16].ljust(16, b"\x00")

    # VBAN sub-protocol byte for PCM:
    #   SR index 3 = 48000 Hz (see VBAN spec SR list)
    #   Bit 5..7 = sub-protocol 0 (audio)
    sr_byte = 3  # 48000 Hz index in VBAN sample-rate table

    try:
        import vban_engine

        while True:
            data = await websocket.receive_bytes()
            if not data:
                continue

            # Pad short frames to 1024 bytes (256 stereo samples × 2 bytes × 2 ch)
            if len(data) < 1024:
                data = data.ljust(1024, b"\x00")

            # Determine how many samples per frame
            # Each sample = 2 bytes (s16le), 2 channels → 4 bytes per sample-pair
            num_samples = (len(data) // 4) - 1  # 0-indexed per VBAN spec

            # Build VBAN header (28 bytes)
            header = struct.pack(
                "<4sBBBB16sI",
                b"VBAN",       # magic
                sr_byte,       # sample rate index | sub-protocol
                num_samples & 0xFF,  # samples per frame (low 8 bits)
                1,             # channels - 1 (stereo = 2 - 1 = 1)
                1,             # data format: 1 = 16-bit int (s16le)
                stream_name_bytes,
                frame_counter & 0xFFFFFFFF,
            )
            packet = header + data

            # Send to all active VBAN destinations
            routes = vban_engine.get_routes()
            destinations = set()
            for route_key, route_list in routes.items():
                for dest in route_list:
                    if dest.get("active"):
                        destinations.add(dest["dest_ip"])

            if not destinations:
                destinations.add("127.0.0.1")

            for dest_ip in destinations:
                try:
                    sock.sendto(packet, (dest_ip, UDP_PORT))
                except Exception:
                    pass

            frame_counter += 1

    except WebSocketDisconnect:
        logger.info("🎤 DJ '%s' disconnected.", user["username"])
    except Exception as e:
        logger.error("DJ WebSocket error: %s", e)
    finally:
        _active_dj = None
        sock.close()
        logger.info("🎤 DJ live mic stream ended.")
