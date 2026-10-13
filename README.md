# 🎵 VBAN-Bridge — Music Request System

A web-based music request system built on top of VBAN audio routing. Users access via Cloudflare-tunneled domain, submit song requests or upload MP3 files, and admins manage the queue through an RBAC-secured dashboard.

## Features
- 🔊 VBAN audio routing between network devices
- 🎶 Music request queue (FIFO)
- 📤 MP3 file upload with multi-layer security validation
- 🎞️ Video-link audio extraction and direct live-stream audio playback over VBAN
- 🎤 DJ live microphone streaming to VR speakers via browser
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

To route outbound audio-provider requests through proxies, set `DOWNLOADER_PROXIES` in `.env` to a comma-separated list of HTTP(S) proxy URLs. The downloader tries them in order and switches to the next when a request fails. The old single `DOWNLOADER_PROXY` setting remains supported. Use providers you trust: each proxy can see the requests it forwards. Public free proxies are not bundled because their operators and handling of traffic cannot be trusted; this setting also does not proxy web visitors' connections or hide the server from other traffic.

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

## DJ Live Microphone

Navigate to `/dj` to stream your microphone directly to all connected VR speakers over VBAN. The page captures audio via the browser's `getUserMedia` API and sends raw PCM frames over a WebSocket. The server re-broadcasts each frame as a VBAN packet to every active route destination.

**Access control:** Only users with the `live_mic` permission (super_admin, admin, moderator) can access the DJ page. Only one DJ can stream at a time.

**Configuration (`.env`):**
| Variable | Default | Description |
|---|---|---|
| `DJ_STREAM_NAME` | `DJLive` | VBAN stream name for the live mic (max 16 chars) |
| `DJ_SAMPLE_RATE` | `48000` | Audio sample rate in Hz |

**Features:**
- Real-time waveform visualizer
- RMS level meter with dB readout
- Gain slider (0–200%)
- Live duration timer
- Works on desktop and mobile browsers

## Security Events and Bans
Failed admin logins and invalid access codes are recorded as categorized audit events with the client IP, request method, path, and user-agent. The admin Audit Log tab can filter by category or search event details. Five failed attempts from an IP within ten minutes trigger a 30-minute application ban. Repeated rate-limit rejections are also written as structured `SECURITY_EVENT` log entries.

Optional Fail2ban filter and jail templates are in `deploy/fail2ban/`. They are disabled by default. Enable them only on a Linux deployment where the application is directly reachable and the firewall can block the logged client IP. Do not use the default host-firewall action behind Cloudflare Tunnel: requests reach the host through Cloudflare, so banning the visitor's IP locally will not reliably block that visitor and can disrupt proxy traffic. The application-level ban remains active for Windows and Tunnel deployments.

The server binds to loopback by default. Set `WEB_HOST=0.0.0.0` only when direct network access is intentional and protected by an appropriate firewall or trusted reverse proxy.

## Architecture
- **Backend**: FastAPI + SQLite (async via aiosqlite)
- **Audio**: VBAN UDP protocol + ffplay for MP3 playback
- **DJ Mic**: WebSocket (browser PCM) → VBAN UDP packets
- **Security**: RBAC, one-time links, rate limiting, file validation
- **Tunnel**: Cloudflare Tunnel (cloudflared)

Video links are converted to MP3 audio for the queue. Active live links are resolved when requested and streamed through FFmpeg to VBAN; the admin dashboard can also monitor them in-browser. Live streams have no seek or fixed duration. A source reported as unavailable by its provider must be accessible to the server; updating yt-dlp may resolve extractor changes, but cannot make private, deleted, or region-blocked media available.