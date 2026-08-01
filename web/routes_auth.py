from fastapi import APIRouter, Request, Form, Response, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from security.auth import validate_and_consume_otp
from security.tokens import generate_session_token
import os

router = APIRouter(tags=["auth"])

@router.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    # Check if already has a valid token
    from security.tokens import is_token_valid
    token = request.cookies.get("session_token")
    if token and is_token_valid(token, request.client.host):
        return RedirectResponse(url="/dashboard")

    # Otherwise show login page
    template_path = os.path.join("templates", "login.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Login Template Missing</h1>")

@router.post("/login")
def login(request: Request, response: Response, otp: str = Form(...)):
    if validate_and_consume_otp(otp):
        # Issue a new session token
        token = generate_session_token(request.client.host)
        
        # We set it as a cookie for browser usage
        redirect = RedirectResponse(url="/dashboard", status_code=303)
        redirect.set_cookie(key="session_token", value=token, httponly=True, max_age=1800) # 30 mins
        return redirect
    
    return HTMLResponse("<script>alert('Invalid or expired OTP!'); window.location.href='/';</script>")

@router.get("/logout")
def logout(request: Request):
    from security.tokens import invalidate_token
    token = request.cookies.get("session_token")
    if token:
        invalidate_token(token)
    
    redirect = RedirectResponse(url="/", status_code=303)
    redirect.delete_cookie("session_token")
    return redirect
