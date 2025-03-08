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


# WebSocket handler that will be adapted to work with aiohttp
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    remote_address = request.remote
    print(f"New connection from {remote_address}")
    
    # Track this connection
    active_connections.add(ws)
    connection_info[ws] = {
        "address": remote_address,
        "connected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "messages_received": 0
    }
    
    try:
        # Task to send frames
        async def send_frames_task():
            while not ws.closed:
                frame_bytes = await generate_frame()
                await ws.send_bytes(frame_bytes)
                await asyncio.sleep(0.1)  # ~10 fps
                
        # Start sending frames in the background
        send_task = asyncio.create_task(send_frames_task())
        
        # Handle incoming messages
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    print("Received GestureData:", data)
                    connection_info[ws]["messages_received"] += 1
                except json.JSONDecodeError:
                    print("Received non-JSON message:", msg.data)
            elif msg.type == web.WSMsgType.ERROR:
                print(f"WebSocket connection closed with error: {ws.exception()}")
                break
                
        # Cancel the send task when the connection is closed
        send_task.cancel()
        try:
            await send_task
        except asyncio.CancelledError:
            pass
            
    finally:
        # Remove connection when done
        active_connections.discard(ws)
        if ws in connection_info:
            del connection_info[ws]
            
    return ws

# HTTP routes for web interface
async def index_handler(request):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Spectacles-2-Unitree Coordination Server Status</title>
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
        <h1>Spectacles-2-Unitree Coordination Server Status</h1>
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
                <th>Messages Received</th>
            </tr>
        """
        
        for conn, info in connection_info.items():
            html += f"""
            <tr>
                <td>{info['address']}</td>
                <td>{info['connected_at']}</td>
                <td>{info['messages_received']}</td>
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

# Main entry point to start the combined HTTP and WebSocket server
async def main():
    # Create the aiohttp application
    app = web.Application()
    
    # Add routes
    app.add_routes([
        web.get('/', index_handler),
        web.get('/ws', websocket_handler)  # WebSocket endpoint
    ])
    
    # Start the server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 80)
    
    print("Server started on http://0.0.0.0:80")
    print("WebSocket endpoint available at ws://0.0.0.0:80/ws")
    
    await site.start()
    
    # Keep the server running
    await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
