# 🎵 VBAN-Bridge — Music Request System

A web-based music request system built on top of VBAN audio routing. Users access via Cloudflare-tunneled domain, submit song requests or upload MP3 files, and admins manage the queue through an RBAC-secured dashboard.

## Features
- 🔊 VBAN audio routing between network devices
- 🎶 Music request queue (FIFO)
- 📤 MP3 file upload with multi-layer security validation
- 🔐 Role-Based Access Control (Super Admin, Admin, Moderator, User)
- 🔗 One-time access links (single-use, auto-expiring)
- 🌐 Cloudflare Tunnel integration (IP hidden, DDoS protected)
- 🎛️ Admin dashboard for managing requests, channels, users, and links

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your settings
```
Set `SUPER_ADMIN_PASSWORD` to a unique password of at least 12 characters. The server refuses to start with a missing or known default password. The web listener binds to `127.0.0.1` by default so a local Cloudflare Tunnel can reach it without exposing the port directly.

### 3. Run the Server
```bash
python server.py
```

### 4. Run with Cloudflare Tunnel
```bash
python server.py --tunnel
```

### 5. Open the Dashboard
Navigate to `http://localhost:8000` or your Cloudflare domain.

## Security Events and Bans
Failed admin logins and invalid access codes are recorded as categorized audit events with the client IP, request method, path, and user-agent. The admin Audit Log tab can filter by category or search event details. Five failed attempts from an IP within ten minutes trigger a 30-minute application ban. Repeated rate-limit rejections are also written as structured `SECURITY_EVENT` log entries.

Optional Fail2ban filter and jail templates are in `deploy/fail2ban/`. They are disabled by default. Enable them only on a Linux deployment where the application is directly reachable and the firewall can block the logged client IP. Do not use the default host-firewall action behind Cloudflare Tunnel: requests reach the host through Cloudflare, so banning the visitor's IP locally will not reliably block that visitor and can disrupt proxy traffic. The application-level ban remains active for Windows and Tunnel deployments.

The server binds to loopback by default. Set `WEB_HOST=0.0.0.0` only when direct network access is intentional and protected by an appropriate firewall or trusted reverse proxy.

## Architecture
- **Backend**: FastAPI + SQLite (async via aiosqlite)
- **Audio**: VBAN UDP protocol + ffplay for MP3 playback
- **Security**: RBAC, one-time links, rate limiting, file validation
- **Tunnel**: Cloudflare Tunnel (cloudflared)