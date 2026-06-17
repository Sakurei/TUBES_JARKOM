#!/usr/bin/env python3
"""
proxy.py — IFLAB Caching Proxy Server
Jalankan: python proxy.py
Listen  : 0.0.0.0:8080
Forward : ke webserver di 127.0.0.1:8000
"""
import socket
import threading
import time
from datetime import datetime

# ── Konfigurasi ────────────────────────────────────────────────────────────
PROXY_HOST  = "0.0.0.0"
PROXY_PORT  = 8080
SERVER_HOST = "127.0.0.1"   # webserver di mesin yang sama
SERVER_PORT = 8000

# ── Cache (in-memory) ───────────────────────────────────────────────────────
cache      = {}
cache_lock = threading.Lock()

# ── Logger ──────────────────────────────────────────────────────────────────
def log(client_ip, path, status, hit_miss, thread_name=""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[PROXY] {ts} | {client_ip} | {path} | {status} | {hit_miss} | thread={thread_name}")

# ── Forward request ke webserver ────────────────────────────────────────────
def fetch_from_server(path):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect((SERVER_HOST, SERVER_PORT))
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {SERVER_HOST}:{SERVER_PORT}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode()
    sock.sendall(request)
    response = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response += chunk
    sock.close()
    return response

# ── Handle satu koneksi dari client ─────────────────────────────────────────
def handle_client(conn, addr):
    thread_name = threading.current_thread().name
    client_ip   = addr[0]
    try:
        raw = conn.recv(4096).decode(errors="ignore")
        if not raw:
            return

        first_line = raw.split("\r\n")[0]
        parts      = first_line.split()
        if len(parts) < 2:
            conn.sendall(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n<h1>400</h1>")
            return

        method = parts[0]
        path   = parts[1].split("?")[0]

        if method != "GET":
            conn.sendall(b"HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\n\r\n<h1>405</h1>")
            return

        # ── Cek cache ──────────────────────────────────────────────────────
        with cache_lock:
            if path in cache:
                response = cache[path]
                hit_miss = "HIT"
            else:
                hit_miss = "MISS"
                response = None

        if response is None:
            try:
                response = fetch_from_server(path)
                with cache_lock:
                    cache[path] = response
            except Exception as e:
                body     = f"<h1>502 Bad Gateway</h1><p>{e}</p>".encode()
                response = (
                    f"HTTP/1.1 502 Bad Gateway\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    f"Connection: close\r\n\r\n"
                ).encode() + body
                log(client_ip, path, 502, "MISS", thread_name)
                conn.sendall(response)
                return

        # ── Ambil status code dari response ───────────────────────────────
        status_line = response.split(b"\r\n")[0].decode(errors="ignore")
        status_code = status_line.split()[1] if len(status_line.split()) > 1 else "???"

        log(client_ip, path, status_code, hit_miss, thread_name)
        conn.sendall(response)

    except Exception as e:
        print(f"[PROXY] Error {client_ip}: {e}")
    finally:
        conn.close()

# ── Main proxy server ────────────────────────────────────────────────────────
if __name__ == "__main__":
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((PROXY_HOST, PROXY_PORT))
    server.listen(20)

    print("=" * 60)
    print("  IFLAB Caching Proxy Server")
    print("=" * 60)
    print(f"  Listen  : {PROXY_HOST}:{PROXY_PORT}")
    print(f"  Forward : {SERVER_HOST}:{SERVER_PORT}")
    print(f"  Cache   : in-memory (HIT/MISS logged)")
    print(f"  Thread  : per-connection")
    print("=" * 60)

    conn_count = 0
    try:
        while True:
            conn, addr = server.accept()
            conn_count += 1
            t = threading.Thread(
                target=handle_client,
                args=(conn, addr),
                name=f"ProxyWorker-{conn_count}",
                daemon=True
            )
            t.start()
    except KeyboardInterrupt:
        print("\n[PROXY] Server stopped.")