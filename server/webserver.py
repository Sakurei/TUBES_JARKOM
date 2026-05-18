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

