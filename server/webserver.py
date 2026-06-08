#!/usr/bin/env python3
"""
webserver.py — HTTP (TCP) + QoS Echo (UDP)
Port HTTP : 8000
Port UDP  : 9000
"""
import socket
import threading
import os
import sys
from datetime import datetime

# ── Konfigurasi ────────────────────────────────────────────────────────────
HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8000
UDP_HOST  = "0.0.0.0"
UDP_PORT  = 9000

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "HTML")

ROUTES = {
    "/":                    "index.html",
    "/index.html":          "index.html",
    "/osi.html":            "osi.html",
    "/tcpip.html":          "tcpip.html",
    "/qos.html":            "qos.html",
    "/implementation.html": "implementation.html",
}

# ── Helper ──────────────────────────────────────────────────────────────────
def read_file(path):
    with open(path, "rb") as f:
        return f.read()

def get_content_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    return {
        ".html": "text/html; charset=utf-8",
        ".css":  "text/css",
        ".js":   "application/javascript",
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".ico":  "image/x-icon",
        ".mp4":  "video/mp4",
    }.get(ext, "application/octet-stream")

def build_response(status_code, status_text, body: bytes, content_type="text/html; charset=utf-8"):
    header = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode()
    return header + body

def log(client_ip, path, status_code, thread_name=""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[HTTP] {ts} | {client_ip} | {path} | {status_code} | thread={thread_name}")
    
# ── Handle satu koneksi TCP ─────────────────────────────────────────────────
def handle_client(conn, addr):
    thread_name = threading.current_thread().name
    client_ip   = addr[0]
    try:
        raw = conn.recv(4096).decode(errors="ignore")
        if not raw:
            return
 
        first_line = raw.split("\r\n")[0]
        parts = first_line.split()
        if len(parts) < 2:
            conn.sendall(build_response(400, "Bad Request", b"<h1>400 Bad Request</h1>"))
            return
 
        method = parts[0]
        path   = parts[1].split("?")[0]
 
        if method != "GET":
            conn.sendall(build_response(405, "Method Not Allowed", b"<h1>405 Method Not Allowed</h1>"))
            log(client_ip, path, 405, thread_name)
            return
 
        filename = ROUTES.get(path)
        if filename:
            filepath = os.path.join(BASE_DIR, filename)
        else:
            filepath = os.path.join(BASE_DIR, path.lstrip("/"))
 
        try:
            body         = read_file(filepath)
            content_type = get_content_type(filepath)
            response     = build_response(200, "OK", body, content_type)
            log(client_ip, path, 200, thread_name)
        except FileNotFoundError:
            body     = b"<h1>404 Not Found</h1><p>The requested resource was not found.</p>"
            response = build_response(404, "Not Found", body)
            log(client_ip, path, 404, thread_name)
        except Exception as e:
            body     = f"<h1>500 Internal Server Error</h1><p>{e}</p>".encode()
            response = build_response(500, "Internal Server Error", body)
            log(client_ip, path, 500, thread_name)
 
        conn.sendall(response)
 
    except Exception as e:
        print(f"[HTTP] Error {client_ip}: {e}")
    finally:
        conn.close()

# ── UDP Echo Server (QoS Ping) ──────────────────────────────────────────────
def start_udp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_HOST, UDP_PORT))
    print(f"[UDP]  Echo server running on {UDP_HOST}:{UDP_PORT}")

    conn_count = 0
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            conn_count += 1
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[UDP]  {ts} | {addr[0]}:{addr[1]} | {len(data)} bytes | seq={conn_count}")
            sock.sendto(data, addr)  # echo balik payload yang sama
        except Exception as e:
            print(f"[UDP]  Error: {e}")

# ── HTTP Server ─────────────────────────────────────────────────────────────
def start_http_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HTTP_HOST, HTTP_PORT))
    server.listen(20)
    print(f"[HTTP] Server running on http://{HTTP_HOST}:{HTTP_PORT}")
    print(f"[HTTP] Serving files from: {BASE_DIR}")
    print(f"[HTTP] Multithreading aktif")

    conn_count = 0
    while True:
        conn, addr = server.accept()
        conn_count += 1
        t = threading.Thread(
            target=handle_client,
            args=(conn, addr),
            name=f"HTTPWorker-{conn_count}",
            daemon=True
        )
        t.start()

# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  IFLAB Web Server — HTTP + UDP QoS Echo")
    print("=" * 60)

    # Jalankan UDP di thread terpisah
    udp_thread = threading.Thread(target=start_udp_server, name="UDPServer", daemon=True)
    udp_thread.start()

    # HTTP server di main thread
    try:
        start_http_server()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)
