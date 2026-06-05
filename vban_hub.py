import socket
import threading
import uvicorn
import json
import os
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

# --- SERVER CONFIGURATIONS ---
UDP_IP = "0.0.0.0"
UDP_PORT = 6980
WEB_PORT = 8000
CONFIG_FILE = "vban_config.json"

DEFAULT_ROUTES = {}
ROUTES = {}

# --- DATA MANAGEMENT FUNCTIONS (JSON) ---
def load_config():
    global ROUTES
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            ROUTES = json.load(f)
    else:
        ROUTES = DEFAULT_ROUTES
        save_config()

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(ROUTES, f, indent=4)

# --- 1. VBAN AUDIO ENGINE (Running in background) ---
def start_background_router():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024)
    sock.bind((UDP_IP, UDP_PORT))
    
    print(f"🎧 VBAN Audio Engine running silently on port {UDP_PORT}...")

    while True:
        try:
            data, addr = sock.recvfrom(2048)
            if data.startswith(b'VBAN'):
                original_name = data[8:24].decode('ascii', errors='ignore').replace('\x00', '')
                
                if original_name in ROUTES:
                    for dest in ROUTES[original_name]:
                        if dest["active"]: 
                            name_bytes = dest["new_name"].encode('ascii')[:16].ljust(16, b'\x00')
                            modified_packet = data[:8] + name_bytes + data[24:]
                            sock.sendto(modified_packet, (dest["dest_ip"], UDP_PORT))
        except Exception:
            pass

# --- 2. WEB SERVER & API (FastAPI) ---
app = FastAPI(title="VBAN Router Hub")

@app.on_event("startup")
def startup_event():
    load_config()

@app.get("/api/status")
def get_status():
    return ROUTES

@app.post("/api/toggle/{stream_name}/{dest_ip}")
def toggle_route(stream_name: str, dest_ip: str):
    if stream_name in ROUTES:
        for dest in ROUTES[stream_name]:
            if dest["dest_ip"] == dest_ip:
                dest["active"] = not dest["active"]
                save_config() 
                return {"status": "success", "new_state": dest["active"]}
    return {"status": "error"}

# NEW: API Route to delete a destination
@app.delete("/api/delete/{stream_name}/{dest_ip}")
def delete_route(stream_name: str, dest_ip: str):
    if stream_name in ROUTES:
        # Filter out the deleted IP
        ROUTES[stream_name] = [dest for dest in ROUTES[stream_name] if dest["dest_ip"] != dest_ip]
        
        # If the stream has no destinations left, remove the stream completely
        if len(ROUTES[stream_name]) == 0:
            del ROUTES[stream_name]
            
        save_config()
        return {"status": "success"}
    return {"status": "error"}

@app.post("/api/add")
async def add_route(stream_name: str = Form(...), dest_ip: str = Form(...), new_name: str = Form(...)):
    stream_name = stream_name[:16].strip()
    new_name = new_name[:16].strip()

    if stream_name not in ROUTES:
        ROUTES[stream_name] = []
    
    if any(d["dest_ip"] == dest_ip for d in ROUTES[stream_name]):
        return HTMLResponse("<script>alert('This IP already exists for this Stream!'); window.location.href='/';</script>")

    new_destination = {"dest_ip": dest_ip, "new_name": new_name, "active": True}
    ROUTES[stream_name].append(new_destination)
    save_config()
    
    return HTMLResponse("<script>window.location.href='/';</script>")

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VBAN Hub Dashboard</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #121212; color: #fff; padding: 20px; }
            h1, h3 { text-align: center; color: #4CAF50; }
            .container { max-width: 800px; margin: 0 auto; }
            .card { background-color: #1e1e1e; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
            .route { display: flex; justify-content: space-between; align-items: center; background: #2c2c2c; padding: 10px 15px; margin-bottom: 10px; border-radius: 8px; }
            .ip { font-size: 0.9em; color: #bbb; }
            .controls { display: flex; gap: 10px; align-items: center; }
            button { padding: 10px 20px; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; transition: 0.2s; }
            .btn-on { background-color: #4CAF50; color: white; }
            .btn-off { background-color: #f44336; color: white; }
            .btn-add { background-color: #2196F3; color: white; }
            /* NEW: Delete button styling */
            .btn-del { background-color: #333; border: 1px solid #555; color: white; padding: 10px 15px; }
            .btn-del:hover { background-color: #555; color: #ff5252; }
            
            .form-box { background: #2a2a2a; padding: 15px; border-radius: 8px; display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; align-items: center;}
            input { padding: 10px; border-radius: 5px; border: 1px solid #444; background: #111; color: white; min-width: 150px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎛️ VBAN Hub Dashboard</h1>
            
            <div class="card">
                <h3 style="color: #2196F3; margin-top: 0;">➕ Add New Route</h3>
                <form action="/api/add" method="POST" class="form-box">
                    <input type="text" name="stream_name" placeholder="Incoming (e.g. CableC)" required maxlength="16">
                    <input type="text" name="dest_ip" placeholder="Target IP (e.g. 192.168.1.10)" required>
                    <input type="text" name="new_name" placeholder="New Name (e.g. CableCS1)" required maxlength="16">
                    <button type="submit" class="btn-add">Add Route</button>
                </form>
            </div>

            <div id="app">Loading routes...</div>
        </div>

        <script>
            async function fetchStatus() {
                const response = await fetch('/api/status');
                const data = await response.json();
                renderUI(data);
            }

            async function toggleRoute(streamName, destIp) {
                await fetch(`/api/toggle/${streamName}/${destIp}`, { method: 'POST' });
                fetchStatus(); 
            }

            // NEW: Delete Route function with confirmation
            async function deleteRoute(streamName, destIp) {
                if(confirm(`Are you sure you want to delete the route to ${destIp}?`)) {
                    await fetch(`/api/delete/${streamName}/${destIp}`, { method: 'DELETE' });
                    fetchStatus(); 
                }
            }

            function renderUI(routes) {
                const app = document.getElementById('app');
                
                if (Object.keys(routes).length === 0) {
                    app.innerHTML = '<div class="card"><p style="text-align:center; color:#bbb;">No routes configured yet. Add one above!</p></div>';
                    return;
                }

                app.innerHTML = '';

                for (const [streamName, destinations] of Object.entries(routes)) {
                    if (destinations.length === 0) continue; 
                    
                    let cardHtml = `<div class="card"><h2 style="color: #03dac6; border-bottom: 1px solid #333; padding-bottom: 10px;">Incoming: ${streamName}</h2>`;
                    
                    destinations.forEach(dest => {
                        const btnClass = dest.active ? 'btn-on' : 'btn-off';
                        const btnText = dest.active ? 'ON' : 'OFF';
                        cardHtml += `
                            <div class="route">
                                <div>
                                    <strong>Outgoing: ${dest.new_name}</strong><br>
                                    <span class="ip">Target IP: ${dest.dest_ip}</span>
                                </div>
                                <div class="controls">
                                    <button class="${btnClass}" onclick="toggleRoute('${streamName}', '${dest.dest_ip}')">${btnText}</button>
                                    <button class="btn-del" onclick="deleteRoute('${streamName}', '${dest.dest_ip}')" title="Delete">🗑️</button>
                                </div>
                            </div>
                        `;
                    });
                    
                    cardHtml += `</div>`;
                    app.innerHTML += cardHtml;
                }
            }

            fetchStatus();
            setInterval(fetchStatus, 3000); 
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    threading.Thread(target=start_background_router, daemon=True).start()
    print("🌐 Starting Web Dashboard...")
    uvicorn.run(app, host="0.0.0.0", port=WEB_PORT)