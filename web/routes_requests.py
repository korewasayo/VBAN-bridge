import os
from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from audio.downloader import download_audio_task

from security.rbac import require_permission, get_current_user
from security.file_validator import validate_mp3, save_mp3, quarantine_file, extract_mp3_metadata, sanitize_metadata_value
from security.auth import can_user_upload_for_link, get_ban_status
from database.db import fetch_all, fetch_one, execute_query
from database.models import add_audit_log
from config import MAX_UPLOAD_SIZE_BYTES

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))

def get_client_ip(request: Request) -> str:
    return (request.headers.get("CF-Connecting-IP") or 
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or 
            request.client.host)

@router.get("/request", response_class=HTMLResponse)
async def request_page(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("request_page.html", {"request": request, "user": user})

@router.post("/api/requests/submit")
async def submit_request(request: Request, background_tasks: BackgroundTasks, title: str = Form(...), artist: str = Form(""), user: dict = Depends(require_permission("submit_request"))):
    safe_title = sanitize_metadata_value(title) or "Untitled Song"
    safe_artist = sanitize_metadata_value(artist) or "Unknown Artist"
    user_id = user["id"]
    request_id = await execute_query(
        "INSERT INTO music_requests (user_id, title, artist, duration_seconds, status, source_type) VALUES (?, ?, ?, 0, 'pending', 'text_request')",
        (user_id, safe_title, safe_artist)
    )
    ip = get_client_ip(request)
    await add_audit_log(user_id, "submit_request", f"Submitted text request: {safe_title} by {safe_artist}", ip)
    
    # Spawn background task to download the audio
    background_tasks.add_task(download_audio_task, title, request_id, user_id, ip)
    
    return {"status": "success", "request_id": request_id}

@router.post("/api/requests/upload")
async def upload_request(request: Request, title: str = Form(...), artist: str = Form(""), file: UploadFile = File(...), user: dict = Depends(require_permission("upload_media"))):
    file_data = await file.read()
    ip = get_client_ip(request)
    ban = await get_ban_status(user_id=user["id"], ip_address=ip)
    if ban:
        raise HTTPException(status_code=403, detail=f"Access blocked: {ban['reason']}")

    if len(file_data) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large")

    source_link_id = user.get("source_link_id")
    if source_link_id:
        can_upload, deny_reason = await can_user_upload_for_link(user["id"], int(source_link_id))
        if not can_upload:
            raise HTTPException(status_code=429, detail=deny_reason)

    is_valid, error_msg = validate_mp3(file.filename, file_data)
    if is_valid:
        safe_title = sanitize_metadata_value(title) or "Untitled Song"
        safe_artist = sanitize_metadata_value(artist) or "Unknown Artist"

        saved_path, save_error = save_mp3(file_data, file.filename)
        if not saved_path:
            raise HTTPException(status_code=500, detail=save_error)

        metadata = extract_mp3_metadata(saved_path)
        if not safe_title or safe_title == "Untitled Song":
            safe_title = sanitize_metadata_value(metadata.get("title")) or "Untitled Song"
        if not safe_artist or safe_artist == "Unknown Artist":
            safe_artist = sanitize_metadata_value(metadata.get("artist")) or "Unknown Artist"
        duration_seconds = float(metadata.get("duration", 0.0) or 0.0)

        user_id = user["id"]
        request_id = await execute_query(
            "INSERT INTO music_requests (user_id, title, artist, status, source_type, mp3_path, duration_seconds) VALUES (?, ?, ?, 'pending', 'upload', ?, ?)",
            (user_id, safe_title, safe_artist, saved_path, duration_seconds)
        )
        ip = get_client_ip(request)
        await add_audit_log(user_id, "submit_upload", f"Uploaded mp3 request: {safe_title} by {safe_artist}", ip)
        return {"status": "success", "request_id": request_id}
    else:
        quarantine_file(file_data, file.filename, error_msg)
        raise HTTPException(status_code=400, detail=error_msg)

@router.get("/api/requests/queue")
async def get_queue(user: dict = Depends(require_permission("view_queue"))):
    requests = await fetch_all(
        "SELECT id, title, artist, duration_seconds, status, source_type, created_at FROM music_requests WHERE status IN ('pending', 'approved', 'playing') ORDER BY created_at ASC"
    )
    return [dict(r) for r in requests]

@router.get("/admin/api/requests")
async def admin_get_requests(status: str = None, user: dict = Depends(require_permission("manage_requests"))):
    query = """
        SELECT r.id, r.title, r.artist, r.status, r.source_type, r.created_at, r.mp3_path, r.duration_seconds,
               u.username as requested_by
        FROM music_requests r
        LEFT JOIN users u ON r.user_id = u.id
    """
    params = ()
    if status:
        query += " WHERE r.status = ?"
        params = (status,)
    query += " ORDER BY r.created_at ASC"
    
    requests = await fetch_all(query, params)
    return [dict(r) for r in requests]

@router.post("/admin/api/requests/{request_id}/approve")
async def approve_request(request: Request, request_id: int, user: dict = Depends(require_permission("manage_requests"))):
    await execute_query(
        "UPDATE music_requests SET status = 'approved', reviewed_by = ?, reviewed_at = datetime('now') WHERE id = ?",
        (user["id"], request_id)
    )
    ip = get_client_ip(request)
    await add_audit_log(user["id"], "approve_request", f"Approved request {request_id}", ip)
    return {"status": "success"}

@router.post("/admin/api/requests/{request_id}/reject")
async def reject_request(request: Request, request_id: int, data: dict, user: dict = Depends(require_permission("manage_requests"))):
    reason = data.get("reason", "")
    await execute_query(
        "UPDATE music_requests SET status = 'rejected', reviewed_by = ?, reviewed_at = datetime('now'), reject_reason = ? WHERE id = ?",
        (user["id"], reason, request_id)
    )
    ip = get_client_ip(request)
    await add_audit_log(user["id"], "reject_request", f"Rejected request {request_id}", ip)
    return {"status": "success"}

@router.post("/admin/api/requests/{request_id}/play")
async def play_request(request: Request, request_id: int, user: dict = Depends(require_permission("manage_requests"))):
    await execute_query("UPDATE music_requests SET status = 'played' WHERE status = 'playing'")
    await execute_query("UPDATE music_requests SET status = 'playing' WHERE id = ?", (request_id,))
    
    req = await fetch_one("SELECT mp3_path FROM music_requests WHERE id = ?", (request_id,))
    if req and req["mp3_path"]:
        try:
            from audio.player import player
            player.play(req["mp3_path"])
        except Exception:
            pass
            
    ip = get_client_ip(request)
    await add_audit_log(user["id"], "play_request", f"Playing request {request_id}", ip)
    return {"status": "success"}

@router.post("/admin/api/requests/{request_id}/stop")
async def stop_request(request: Request, request_id: int, user: dict = Depends(require_permission("manage_requests"))):
    await execute_query("UPDATE music_requests SET status = 'played' WHERE id = ?", (request_id,))
    
    try:
        from audio.player import player
        player.stop()
    except Exception:
        pass
        
    ip = get_client_ip(request)
    await add_audit_log(user["id"], "stop_request", f"Stopped request {request_id}", ip)
    return {"status": "success"}

@router.post("/admin/api/player/pause")
async def pause_player(request: Request, user: dict = Depends(require_permission("manage_requests"))):
    try:
        from audio.player import player
        is_paused = player.toggle_pause()
        return {"status": "success", "is_paused": is_paused}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/api/player/status")
async def player_status(request: Request, user: dict = Depends(require_permission("manage_requests"))):
    try:
        from audio.player import player
        return player.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/api/player/volume")
async def set_player_volume(request: Request, data: dict, user: dict = Depends(require_permission("manage_requests"))):
    volume = data.get("volume", 0.8)
    try:
        from audio.player import player
        player.set_volume(float(volume))
        return {"status": "success", "volume": player.volume}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/api/player/seek")
async def seek_player(request: Request, data: dict, user: dict = Depends(require_permission("manage_requests"))):
    time = data.get("time", 0.0)
    try:
        from audio.player import player
        success = player.seek(float(time))
        if not success:
            raise HTTPException(status_code=400, detail="Could not seek to that time")
        return {"status": "success", "time": time}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.delete("/admin/api/requests/{request_id}")
async def delete_request(request: Request, request_id: int, user: dict = Depends(require_permission("manage_requests"))):
    req = await fetch_one("SELECT mp3_path FROM music_requests WHERE id = ?", (request_id,))
    if req and req["mp3_path"] and os.path.exists(req["mp3_path"]):
        try:
            os.remove(req["mp3_path"])
        except OSError:
            pass
            
    await execute_query("DELETE FROM music_requests WHERE id = ?", (request_id,))
    ip = get_client_ip(request)
    await add_audit_log(user["id"], "delete_request", f"Deleted request {request_id}", ip)
    return {"status": "success"}
