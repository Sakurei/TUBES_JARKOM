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