"""
client.py — IFLAB Network Client
Jalankan: python client.py
Otomatis: HTTP test, QoS UDP ping, dan 5 client simultan
"""
import socket
import time
import sys
import math
import threading

# ── Konfigurasi ────────────────────────────────────────────────────────────
PROXY_HOST  = "127.0.0.1"
PROXY_PORT  = 8080
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 9000
UDP_COUNT   = 10
UDP_TIMEOUT = 1

# ── HTTP Request ────────────────────────────────────────────────────────────
def http_request(path="/", label=""):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((PROXY_HOST, PROXY_PORT))
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {PROXY_HOST}:{PROXY_PORT}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode()

        t_start = time.time()
        sock.sendall(request)
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        elapsed = time.time() - t_start
        sock.close()

        decoded     = response.decode(errors="ignore")
        status_line = decoded.split("\r\n")[0]
        throughput  = (len(response) * 8) / (elapsed * 1000) if elapsed > 0 else 0
        prefix      = f"[{label}] " if label else ""

        print(f"  {prefix}GET {path:25s} → {status_line} | {elapsed*1000:.1f} ms | {throughput:.1f} kbps")
        return status_line, elapsed * 1000, len(response)

    except ConnectionRefusedError:
        print(f"  [ERROR] Tidak bisa konek ke proxy. Pastikan proxy.py jalan.")
        return "ERROR", 0, 0
    except Exception as e:
        print(f"  [ERROR] {e}")
        return "ERROR", 0, 0