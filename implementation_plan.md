# VBAN-Bridge Implementation Plan

## Goal Description
Build a secure music request system allowing users to stream or upload audio (MP3) to a local speaker system safely. The system uses a reverse proxy to hide the host IP, secures access through one-time links/passwords, provides deep malware scanning for uploads, and includes an RBAC administrator interface to manage requests and audio channels by IP.

## Architecture Components

1. **Network Security & Proxy (Cloudflare Tunnels)**
   - Implement a tunnel manager to spawn a `cloudflared` subprocess.
   - Expose the local FastAPI server to the internet without opening ports, utilizing Cloudflare's DDoS protection.

2. **Audio Engine (VBAN)**
   - Implement a UDP router to listen for incoming VBAN streams.
   - Route streams dynamically based on IP and configuration.

3. **Web Server (FastAPI)**
   - Create a central entry point managing the database, background threads (VBAN/Cloudflare), and the web application.

4. **Security & Authentication**
   - **RBAC (Role-Based Access Control)**: Hierarchical roles (`super_admin`, `admin`, `moderator`, `user`) to restrict access to endpoints.
   - **Dynamic Authentication**: Token generation for one-time or time-limited access to prevent link sharing and reuse.

5. **Malware & File Validation**
   - Enforce `.mp3` extension and size limits.
   - Verify magic bytes (MPEG Audio/ID3 headers).
   - Check MIME types using `python-magic`.
   - Scan file body for embedded executable signatures (MZ, ELF, Scripts) to prevent disguised malware.

## Step-by-Step Execution Plan

### Step 1: Core Setup & VBAN Engine
- Initialize the project structure and dependencies.
- Build the UDP VBAN packet router to receive and forward audio packets based on source IP.

### Step 2: Cloudflare Tunnel Integration
- Create the integration script (`tunnel.py`) to automatically start a Cloudflare tunnel alongside the server.
- Ensure the local web server binds to local interfaces, entirely hidden behind the tunnel.

### Step 3: Security Foundations (RBAC & Auth)
- Setup the SQLite database with models for Users, Tokens, and Audio Channels.
- Implement the Role-Based Access Control (RBAC) middleware for FastAPI.
- Create the system for generating expiring, one-time-use login links.

### Step 4: Secure File Uploads
- Implement multi-layer MP3 validation (Extension, Size, Magic Bytes, MIME type).
- Add deep body scanning to detect malicious payloads hidden inside audio files (quarantining suspicious files).

### Step 5: Web API & Admin Interface
- Build the user-facing request endpoints for submitting music/audio streams.
- Build the admin API for reviewing requests, managing RBAC users, and configuring IP-based audio channels.
