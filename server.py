import os
import asyncio
import websockets
import json
import urllib
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

UPLOAD_DIR = "uploads"
HTML_FILE = "index.html"
SHARED_TXT = "shared.txt"

os.makedirs(UPLOAD_DIR, exist_ok=True)

if not os.path.exists(SHARED_TXT):
    with open(SHARED_TXT, "w", encoding="utf-8") as f:
        f.write(
            "Welcome to the shared notes!\n\n"
            "Markdown links work: [Python](https://www.python.org)\n"
            "Normal links: https://github.com\n"
        )

def get_file_links():
    files = os.listdir(UPLOAD_DIR)
    links = []
    for filename in files:
        safe_name = urllib.parse.quote(filename)
        links.append(f'<li><a href="/download?file={safe_name}">{filename}</a></li>')
    return "\n".join(links)

def get_shared_txt():
    with open(SHARED_TXT, "r", encoding="utf-8") as f:
        return f.read()

def save_shared_txt(new_text):
    with open(SHARED_TXT, "w", encoding="utf-8") as f:
        f.write(new_text)

# ------------------ HTTP Server ------------------
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/download'):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            filename = params.get("file", [""])[0]
            filename = os.path.basename(filename)
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.exists(file_path):
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Content-Length', str(os.path.getsize(file_path)))
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"File not found.")
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open(HTML_FILE, "r", encoding="utf-8") as f:
                html = f.read()
            html = html.replace("{file_links}", get_file_links())
            html = html.replace("{shared_txt}", get_shared_txt())
            self.wfile.write(html.encode())

    def do_POST(self):
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(content_length)

        if "multipart/form-data" in content_type:
            boundary = content_type.split("boundary=")[1].encode()
            parts = data.split(b"--" + boundary)
            for part in parts:
                if b"filename=" in part:
                    header, file_content = part.split(b"\r\n\r\n", 1)
                    header_str = header.decode(errors="ignore")
                    filename = header_str.split("filename=")[1].split("\r\n")[0].strip('"')
                    file_content = file_content.rstrip(b"\r\n--")
                    if filename:
                        with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
                            f.write(file_content)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Files uploaded successfully.")
            return

        elif "application/x-www-form-urlencoded" in content_type:
            post_data = urllib.parse.parse_qs(data.decode())
            if "shared_txt" in post_data:
                new_text = post_data["shared_txt"][0]
                save_shared_txt(new_text)
                asyncio.run(send_update_to_clients())  # Push update to everyone
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Shared text updated.")
                return

        self.send_response(400)
        self.end_headers()
        self.wfile.write(b"Invalid request.")

# ------------------ WebSocket Server ------------------
connected_clients = set()

async def ws_handler(websocket):
    connected_clients.add(websocket)
    try:
        await websocket.send(json.dumps({"text": get_shared_txt()}))
        async for _ in websocket:
            pass
    finally:
        connected_clients.remove(websocket)

async def send_update_to_clients():
    if connected_clients:
        data = json.dumps({"text": get_shared_txt()})
        await asyncio.gather(*(client.send(data) for client in connected_clients))

async def ws_server():
    async with websockets.serve(ws_handler, "", 8765):
        await asyncio.Future()  # run forever

def start_http():
    import socket
    port = 8000
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()
    print(f"HTTP Server: http://{local_ip}:{port}/")
    httpd = HTTPServer(('', port), SimpleHTTPRequestHandler)
    httpd.serve_forever()

if __name__ == '__main__':
    threading.Thread(target=start_http, daemon=True).start()
    print("WebSocket Server: ws://localhost:8765/")
    asyncio.run(ws_server())
