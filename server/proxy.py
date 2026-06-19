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
from collections import OrderedDict

# ── Konfigurasi ────────────────────────────────────────────────────────────
PROXY_HOST  = "0.0.0.0"
PROXY_PORT  = 8080
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000

# ── Cache Config ────────────────────────────────────────────────────────────
CACHE_TTL      = 120    # detik — entry expired setelah 120 detik
CACHE_MAX_SIZE = 50    # maksimal 50 entry, LRU dibuang kalau penuh

# ══════════════════════════════════════════════════════════════════════════════
#  LRU Cache dengan TTL
# ══════════════════════════════════════════════════════════════════════════════
class LRUCacheTTL:
    """
    Thread-safe LRU Cache dengan TTL per-entry.
    - Kalau cache penuh → entry paling lama tidak dipakai (LRU) dibuang.
    - Kalau entry sudah melewati TTL → dianggap expired (MISS).
    """
    def __init__(self, max_size=50, ttl=30):
        self.max_size  = max_size
        self.ttl       = ttl
        self._store    = OrderedDict()   # key → (response_bytes, timestamp)
        self._lock     = threading.Lock()

        # Stats
        self._hits     = 0
        self._misses   = 0
        self._evictions = 0
        self._expirations = 0

    def get(self, key):
        """Return (response, 'HIT') atau (None, 'MISS')."""
        with self._lock:
            if key not in self._store:
                self._misses += 1
                return None, "MISS"

            response, ts = self._store[key]

            # Cek TTL
            if time.time() - ts > self.ttl:
                del self._store[key]
                self._expirations += 1
                self._misses += 1
                return None, "MISS (EXPIRED)"

            # Cache HIT → pindah ke akhir (most recently used)
            self._store.move_to_end(key)
            self._hits += 1
            return response, "HIT"

    def set(self, key, value):
        """Simpan entry baru. Buang LRU kalau sudah penuh."""
        with self._lock:
            if key in self._store:
                # Update existing → pindah ke akhir
                self._store.move_to_end(key)
            else:
                # Evict LRU kalau penuh
                if len(self._store) >= self.max_size:
                    evicted_key, _ = self._store.popitem(last=False)
                    self._evictions += 1
                    print(f"[CACHE] Evicted LRU entry: {evicted_key}")

            self._store[key] = (value, time.time())

    def stats(self):
        with self._lock:
            total    = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "size"       : len(self._store),
                "max_size"   : self.max_size,
                "ttl_sec"    : self.ttl,
                "hits"       : self._hits,
                "misses"     : self._misses,
                "hit_rate"   : f"{hit_rate:.1f}%",
                "evictions"  : self._evictions,
                "expirations": self._expirations,
            }

    def flush(self):
        """Hapus semua entry cache."""
        with self._lock:
            self._store.clear()
            print("[CACHE] Cache flushed.")


# ── Inisialisasi cache ───────────────────────────────────────────────────────
cache = LRUCacheTTL(max_size=CACHE_MAX_SIZE, ttl=CACHE_TTL)

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

        # ── Cek cache (LRU + TTL) ─────────────────────────────────────────
        response, hit_miss = cache.get(path)

        if response is None:
            # MISS → fetch dari webserver
            try:
                response = fetch_from_server(path)
                # Hanya cache response sukses (200)
                status_line = response.split(b"\r\n")[0].decode(errors="ignore")
                if "200" in status_line:
                    cache.set(path, response)
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

# ── Stats printer (background thread) ───────────────────────────────────────
def stats_printer(interval=3):
    """Print cache stats setiap N detik."""
    while True:
        time.sleep(interval)
        s = cache.stats()
        print(
            f"\n[CACHE STATS] Size: {s['size']}/{s['max_size']} | "
            f"TTL: {s['ttl_sec']}s | "
            f"Hits: {s['hits']} | Misses: {s['misses']} | "
            f"Hit Rate: {s['hit_rate']} | "
            f"Evictions: {s['evictions']} | Expirations: {s['expirations']}\n"
        )

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
    print(f"  Cache   : LRU + TTL | max={CACHE_MAX_SIZE} entries | ttl={CACHE_TTL}s")
    print(f"  Thread  : per-connection")
    print("=" * 60)

    # Background thread: print stats tiap 10 detik
    stats_thread = threading.Thread(target=stats_printer, args=(3,), daemon=True, name="StatsThread")
    stats_thread.start()

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
        print("\n[PROXY] Final Cache Stats:")
        s = cache.stats()
        for k, v in s.items():
            print(f"  {k:15s}: {v}")
        print("\n[PROXY] Server stopped.")