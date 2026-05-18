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
