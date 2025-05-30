import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib
import cgi

UPLOAD_DIR = "uploads"
HTML_FILE = "index.html"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_file_links():
    files = os.listdir(UPLOAD_DIR)
    links = []
    for filename in files:
        safe_name = urllib.parse.quote(filename)
        links.append(f'<li><a href="/download?file={safe_name}">{filename}</a></li>')
    return "\n".join(links)

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/download'):
            # Download file logic
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            filename = params.get("file", [""])[0]
            filename = os.path.basename(filename)  # Prevent path traversal
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
            # Serve the HTML with file list
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            # Read the HTML file
            with open(HTML_FILE, "r", encoding="utf-8") as f:
                html = f.read()
            # Replace {file_links} with the actual list
            html = html.replace("{file_links}", get_file_links())
            self.wfile.write(html.encode())

    def do_POST(self):
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD':'POST'}
        )
        if "file" in form:
            file_item = form["file"]
            filename = os.path.basename(file_item.filename)
            filepath = os.path.join(UPLOAD_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(file_item.file.read())
            self.send_response(200)
            self.end_headers()
            self.wfile.write(f"File '{filename}' uploaded successfully.".encode())
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No file uploaded.")

if __name__ == '__main__':
    import socket
    port = 8000
    # Get your local IP address so you can access from phone
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()
    print(f"Server started: http://{local_ip}:{port}/")
    httpd = HTTPServer(('', port), SimpleHTTPRequestHandler)
    httpd.serve_forever()
