# 🚀 Setup Instructions
This project features a Web Dashboard to easily manage and route your VBAN audio streams across multiple computers.

## Step 1: Install Dependencies
Open your terminal and install the required web framework libraries:
```bash
    pip install fastapi uvicorn
```

## Step 2: Run the Hub
Start the application from your terminal:
```bash
    python3 vban_router.py
```
(Make sure to replace vban_router.py with the actual name of your file if you changed it).

## Step 3: Open the Dashboard
1. Open a web browser on any device connected to your network.
2. Type the IP address of your Raspberry Pi, followed by port 8000.
    - Example: `http://192.168.1.42:8000`

## Step 4: Add Your Routes
1. Use the "➕ Add New Route" section at the top of the webpage.
2. Enter the Sender IP, the Stream Name, and your Target IP.
3. Click Add Route. The system will automatically create a `vban_config.json` file to remember your settings even if you restart the Raspberry Pi!