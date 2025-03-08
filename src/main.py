import asyncio
import io
import json
from datetime import datetime

import websockets
from PIL import Image, ImageDraw, ImageFont
from aiohttp import web

# Track active WebSocket connections
active_connections = set()
connection_info = {}

# Generate a dummy 720p frame with the current datetime rendered as text
async def generate_frame():
    # Create a 1280x720 white background image
    img = Image.new("RGB", (1280, 720), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Get the current datetime as a string
    text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Attempt to load a truetype font; fallback to default if not available
    try:
        font = ImageFont.truetype("arial.ttf", 60)
    except IOError:
        font = ImageFont.load_default()
    # Center the text
    text_width, text_height = draw.textsize(text, font=font)
    position = ((1280 - text_width) // 2, (720 - text_height) // 2)
    draw.text(position, text, fill=(0, 0, 0), font=font)
    # Save the image to a bytes buffer as JPEG
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# Continuously send frames over the WebSocket as binary messages (interpreted as Blobs)
async def send_frames(websocket):
    while True:
        frame_bytes = await generate_frame()
        await websocket.send(frame_bytes)
        # Aim for ~10 frames per second (adjust as needed)
        await asyncio.sleep(0.1)


# Listen for incoming messages, parse as JSON, and print GestureData
async def receive_messages(websocket):
    while True:
        try:
            message = await websocket.recv()
            try:
                data = json.loads(message)
                # Expected gesture data structure:
                # { "hand": "l" | "r", "origin": [x, y, z], "direction": [x, y, z] }
                print("Received GestureData:", data)
            except json.JSONDecodeError:
                print("Received non-JSON message:", message)
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed.")
            break


# WebSocket handler that spawns both send and receive tasks
async def handler(websocket, path):
    remote_address = websocket.remote_address
    print(f"New connection from {remote_address}")
    
    # Track this connection
    active_connections.add(websocket)
    connection_info[websocket] = {
        "address": f"{remote_address[0]}:{remote_address[1]}",
        "connected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "messages_received": 0
    }
    
    try:
        send_task = asyncio.create_task(send_frames(websocket))
        recv_task = asyncio.create_task(receive_messages(websocket))
        # Wait until one of the tasks completes (or the connection closes)
        done, pending = await asyncio.wait(
            [send_task, recv_task], return_when=asyncio.FIRST_COMPLETED
        )
        # Cancel any remaining tasks
        for task in pending:
            task.cancel()
    finally:
        # Remove connection when done
        active_connections.discard(websocket)
        if websocket in connection_info:
            del connection_info[websocket]

# HTTP routes for web interface
async def index_handler(request):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Spectacles WebSocket Server Status</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            .status { padding: 10px; margin-bottom: 20px; }
            .active { background-color: #dff0d8; border: 1px solid #d6e9c6; color: #3c763d; }
            .inactive { background-color: #f2dede; border: 1px solid #ebccd1; color: #a94442; }
        </style>
        <script>
            function refreshPage() {
                location.reload();
            }
            // Auto refresh every 5 seconds
            setInterval(refreshPage, 5000);
        </script>
    </head>
    <body>
        <h1>Spectacles WebSocket Server Status</h1>
    """
    
    active_count = len(active_connections)
    status_class = "active" if active_count > 0 else "inactive"
    
    html += f"""
        <div class="status {status_class}">
            <p><strong>Server Status:</strong> Running</p>
            <p><strong>Active Connections:</strong> {active_count}</p>
        </div>
        
        <h2>Active Connections</h2>
    """
    
    if active_count > 0:
        html += """
        <table>
            <tr>
                <th>Remote Address</th>
                <th>Connected At</th>
            </tr>
        """
        
        for conn, info in connection_info.items():
            html += f"""
            <tr>
                <td>{info['address']}</td>
                <td>{info['connected_at']}</td>
            </tr>
            """
        
        html += "</table>"
    else:
        html += "<p>No active connections</p>"
    
    html += """
    </body>
    </html>
    """
    
    return web.Response(text=html, content_type="text/html")

# Setup the HTTP app
async def setup_http_server():
    app = web.Application()
    app.add_routes([web.get('/', index_handler)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("HTTP server started on http://0.0.0.0:8080")

# Main entry point to start both WebSocket and HTTP servers
async def main():
    # Start the HTTP server
    await setup_http_server()
    
    # Start the WebSocket server
    async with websockets.serve(handler, "0.0.0.0", 80):
        print("WebSocket server started on ws://0.0.0.0:80")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
