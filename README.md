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

## Default Admin Login
- Username: `admin` (or value of SUPER_ADMIN_USERNAME env var)
- Password: `changeme123` (or value of SUPER_ADMIN_PASSWORD env var)

⚠️ **Change the default password immediately after first login!**

## Architecture
- **Backend**: FastAPI + SQLite (async via aiosqlite)
- **Audio**: VBAN UDP protocol + ffplay for MP3 playback
- **Security**: RBAC, one-time links, rate limiting, file validation
- **Tunnel**: Cloudflare Tunnel (cloudflared)