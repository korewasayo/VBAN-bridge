import socket
import json
import os
from config import UDP_IP, UDP_PORT, CONFIG_FILE

DEFAULT_ROUTES = {}
ROUTES = {}

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

def get_routes():
    return ROUTES

def set_routes(new_routes):
    global ROUTES
    ROUTES = new_routes
    save_config()

def start_background_router():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024)
    sock.bind((UDP_IP, UDP_PORT))
    
    print(f"🎧 VBAN Audio Engine running silently on port {UDP_PORT}...")

    load_config()

    while True:
        try:
            data, addr = sock.recvfrom(2048)
            source_ip = addr[0] 

            if data.startswith(b'VBAN'):
                original_name = data[8:24].decode('ascii', errors='ignore').replace('\x00', '')
                route_key = f"{source_ip}::{original_name}"
                
                if route_key in ROUTES:
                    for dest in ROUTES[route_key]:
                        if dest["active"]: 
                            name_bytes = dest["new_name"].encode('ascii')[:16].ljust(16, b'\x00')
                            modified_packet = data[:8] + name_bytes + data[24:]
                            sock.sendto(modified_packet, (dest["dest_ip"], UDP_PORT))
        except Exception:
            pass
