import uvicorn
import threading
from config import WEB_PORT
from vban_engine import start_background_router
from web.app import app

def main():
    # Start the VBAN background engine
    vban_thread = threading.Thread(target=start_background_router, daemon=True)
    vban_thread.start()
    
    print(f"🌐 Starting Web Dashboard securely on port {WEB_PORT}...")
    
    # Run the FastAPI web server
    uvicorn.run(app, host="0.0.0.0", port=WEB_PORT)

if __name__ == "__main__":
    main()
