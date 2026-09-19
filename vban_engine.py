import socket
import json
import os
import threading
import copy
import logging

from config import UDP_IP, UDP_PORT, CONFIG_FILE

logger = logging.getLogger("vban_engine")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(ch)

DEFAULT_ROUTES = {}
ROUTES = {}
route_lock = threading.Lock()

def load_config():
    global ROUTES
    with route_lock:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    ROUTES = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load VBAN config: {e}. Using default.")
                ROUTES = {}
        else:
            ROUTES = DEFAULT_ROUTES
            _save_config_nolock()

def _save_config_nolock():
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(ROUTES, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save VBAN config: {e}")

def get_routes():
    with route_lock:
        return copy.deepcopy(ROUTES)

def toggle_route(source_ip: str, stream_name: str, dest_ip: str) -> bool:
    route_key = f"{source_ip}::{stream_name}"
    with route_lock:
        if route_key in ROUTES:
            for dest in ROUTES[route_key]:
                if dest["dest_ip"] == dest_ip:
                    dest["active"] = not dest["active"]
                    _save_config_nolock()
                    return dest["active"]
    raise KeyError("Route not found")

def delete_route(source_ip: str, stream_name: str, dest_ip: str) -> bool:
    route_key = f"{source_ip}::{stream_name}"
    with route_lock:
        if route_key in ROUTES:
            original_len = len(ROUTES[route_key])
            ROUTES[route_key] = [
                dest for dest in ROUTES[route_key] if dest["dest_ip"] != dest_ip
            ]
            if len(ROUTES[route_key]) < original_len:
                if len(ROUTES[route_key]) == 0:
                    del ROUTES[route_key]
                _save_config_nolock()
                return True
    raise KeyError("Route not found")

def add_route(source_ip: str, stream_name: str, dest_ip: str, new_name: str):
    route_key = f"{source_ip}::{stream_name}"
    with route_lock:
        if route_key not in ROUTES:
            ROUTES[route_key] = []
        
        for d in ROUTES[route_key]:
            if d["dest_ip"] == dest_ip:
                raise ValueError("Destination IP already exists for this stream")
                
        ROUTES[route_key].append({"dest_ip": dest_ip, "new_name": new_name, "active": True})
        _save_config_nolock()

def start_background_router():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024)
    try:
        sock.bind((UDP_IP, UDP_PORT))
    except Exception as e:
        logger.error(f"Failed to bind VBAN socket on port {UDP_PORT}: {e}")
        return
    
    logger.info(f"🎧 VBAN Audio Engine running silently on port {UDP_PORT}...")

    load_config()

    while True:
        try:
            data, addr = sock.recvfrom(2048)
            source_ip = addr[0] 

            if len(data) >= 28 and data.startswith(b'VBAN'):
                original_name = data[8:24].decode('ascii', errors='ignore').replace('\x00', '')
                route_key = f"{source_ip}::{original_name}"
                
                with route_lock:
                    destinations = ROUTES.get(route_key, None)
                    if destinations:
                        destinations = list(destinations)
                
                if destinations:
                    for dest in destinations:
                        if dest.get("active"): 
                            name_bytes = dest["new_name"].encode('ascii')[:16].ljust(16, b'\x00')
                            modified_packet = data[:8] + name_bytes + data[24:]
                            sock.sendto(modified_packet, (dest["dest_ip"], UDP_PORT))
        except Exception:
            pass
