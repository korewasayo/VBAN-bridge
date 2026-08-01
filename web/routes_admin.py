from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from config import ADMIN_SECRET
from security.auth import generate_otp, get_active_otps
import os

router = APIRouter(prefix="/admin", tags=["admin"])

def verify_admin_secret(secret: str):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized Admin Access")

@router.get("/")
def admin_panel(secret: str):
    verify_admin_secret(secret)
    # Simple JSON response for now, could be a full HTML page
    return {
        "status": "ok",
        "active_otps": get_active_otps()
    }

@router.post("/generate-otp")
def create_otp(secret: str):
    verify_admin_secret(secret)
    new_otp = generate_otp()
    return {"new_otp": new_otp}
