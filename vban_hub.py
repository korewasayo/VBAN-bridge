import socket

# --- CONFIGURATIONS ---
UDP_IP = "0.0.0.0"
UDP_PORT = 6980

# --- ROUTING TABLE ---
# IMPORTANT: Replace these dummy IPs (10.0.0.x) with the actual 
# local IP addresses of the destination computers on your network.
ROUTES = {
    "CableA": [
        {"dest_ip": "10.0.0.10", "new_name": "CableAS1"},
    ],
    "CableB": [
        {"dest_ip": "10.0.0.10", "new_name": "CableBS1"},
    ]
}

def start_fast_router():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # --- CRITICAL BUFFER OPTIMIZATION ---
    # Increases receive and send capacity to 1MB to prevent packet loss (audio stuttering)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024)

    sock.bind((UDP_IP, UDP_PORT))

    print("🚀 Optimized VBAN Router running in the background!")
    print(" (Prints inside the main loop are disabled to prevent audio lag)")

    try:
        while True:
            # Read packet
            data, addr = sock.recvfrom(2048)

            # Check if it is a valid VBAN packet
            if data.startswith(b'VBAN'):
                original_name = data[8:24].decode('ascii', errors='ignore').replace('\x00', '')

                # If the stream name is in our routing table, process it
                if original_name in ROUTES:
                    for dest in ROUTES[original_name]:
                        # Super fast and direct string replacement
                        name_bytes = dest["new_name"].encode('ascii')[:16].ljust(16, b'\x00')
                        modified_packet = data[:8] + name_bytes + data[24:]
                        
                        # Send to the target IP
                        sock.sendto(modified_packet, (dest["dest_ip"], UDP_PORT))

    except KeyboardInterrupt:
        print("\nRouter stopped by user.")
    finally:
        sock.close()

if __name__ == "__main__":
    start_fast_router()