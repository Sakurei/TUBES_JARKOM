#!/usr/bin/env python3
"""
proxy.py — Proxy Server dengan Caching
Port : 8080
Forward ke Web Server : localhost:8000
"""
import socket
import threading
import sys
from datetime import datetime

# ── Konfigurasi ────────────────────────────────────────────────────────────
PROXY_HOST  = "0.0.0.0"
PROXY_PORT  = 8080
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
TIMEOUT     = 5   # detik

# Cache: { path: bytes_response }
cache      = {}
cache_lock = threading.Lock()

# ── Log ─────────────────────────────────────────────────────────────────────
def log(client_ip, url, status, hit_miss, thread_name="", elapsed_ms=0):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[PROXY] {ts} | {client_ip} | {url} | {status} | {hit_miss} | {elapsed_ms:.1f}ms | thread={thread_name}")

# ── Forward request ke web server ──────────────────────────────────────────
def forward_to_server(raw_request: bytes) -> bytes:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        sock.connect((SERVER_HOST, SERVER_PORT))
        sock.sendall(raw_request)

        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        sock.close()
        return response

    except socket.timeout:
        return (
            b"HTTP/1.1 504 Gateway Timeout\r\n"
            b"Content-Type: text/html; charset=utf-8\r\n"
            b"Content-Length: 28\r\n\r\n"
            b"<h1>504 Gateway Timeout</h1>"
        )
    except Exception as e:
        body   = f"<h1>502 Bad Gateway</h1><p>{e}</p>".encode()
        header = (
            f"HTTP/1.1 502 Bad Gateway\r\n"
            f"Content-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n\r\n"
        ).encode()
        return header + body

# ── Handle satu client ──────────────────────────────────────────────────────
def handle_client(conn, addr):
    thread_name = threading.current_thread().name
    client_ip   = addr[0]
    t_start     = __import__("time").time()

    try:
        raw = conn.recv(4096)
        if not raw:
            return

        first_line = raw.decode(errors="ignore").split("\r\n")[0]
        parts = first_line.split()
        path  = parts[1].split("?")[0] if len(parts) >= 2 else "/"

        # ── Cek cache (HIT) ──────────────────────────────────────────────
        with cache_lock:
            if path in cache:
                conn.sendall(cache[path])
                elapsed = (__import__("time").time() - t_start) * 1000
                log(client_ip, path, 200, "HIT", thread_name, elapsed)
                return

        # ── Cache MISS → forward ke server ───────────────────────────────
        response    = forward_to_server(raw)
        status_line = response.split(b"\r\n")[0].decode(errors="ignore")
        elapsed     = (__import__("time").time() - t_start) * 1000

        if "200" in status_line:
            with cache_lock:
                cache[path] = response
            log(client_ip, path, 200, "MISS", thread_name, elapsed)
        elif "404" in status_line:
            log(client_ip, path, 404, "MISS", thread_name, elapsed)
        elif "504" in status_line:
            log(client_ip, path, 504, "MISS", thread_name, elapsed)
        elif "502" in status_line:
            log(client_ip, path, 502, "MISS", thread_name, elapsed)
        else:
            log(client_ip, path, status_line.split()[1] if len(status_line.split()) > 1 else "???", "MISS", thread_name, elapsed)

        conn.sendall(response)

    except Exception as e:
        print(f"[PROXY] Error {client_ip}: {e}")
    finally:
        conn.close()

# ── Main ────────────────────────────────────────────────────────────────────
def start_proxy():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((PROXY_HOST, PROXY_PORT))
    server.listen(20)
    print(f"[PROXY] Running on http://{PROXY_HOST}:{PROXY_PORT}")
    print(f"[PROXY] Forwarding to http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"[PROXY] Multithreading aktif | Cache enabled")

    conn_count = 0
    while True:
        conn, addr = server.accept()
        conn_count += 1
        t = threading.Thread(
            target=handle_client,
            args=(conn, addr),
            name=f"ProxyWorker-{conn_count}",
            daemon=True
        )
        print(f"[PROXY] New connection from {addr[0]} → spawning {t.name}")
        t.start()

if __name__ == "__main__":
    try:
        start_proxy()
    except KeyboardInterrupt:
        print("\nProxy stopped.")
        sys.exit(0)
