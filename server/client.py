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

# ── QoS UDP Ping ────────────────────────────────────────────────────────────
def qos_ping():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(UDP_TIMEOUT)

    rtts, jitters, lost, total_bytes = [], [], 0, 0
    t_start = time.time()

    for seq in range(1, UDP_COUNT + 1):
        payload = f"Ping {seq} {time.time()}".encode()
        t_sent  = time.time()
        try:
            sock.sendto(payload, (SERVER_HOST, SERVER_PORT))
            data, _ = sock.recvfrom(1024)
            rtt = (time.time() - t_sent) * 1000
            rtts.append(rtt)
            total_bytes += len(data)
            if len(rtts) >= 2:
                jitters.append(abs(rtts[-1] - rtts[-2]))
            print(f"  Seq {seq:2d}: Reply dari {SERVER_HOST} | RTT = {rtt:.2f} ms")
        except socket.timeout:
            print(f"  Seq {seq:2d}: Request timed out")
            lost += 1

    duration   = time.time() - t_start
    loss_pct   = (lost / UDP_COUNT) * 100
    throughput = (total_bytes * 8) / (duration * 1000) if duration > 0 else 0
    jitter_std = 0.0
    if len(jitters) > 1:
        mean_j     = sum(jitters) / len(jitters)
        jitter_std = math.sqrt(sum((j - mean_j)**2 for j in jitters) / len(jitters))
    elif len(jitters) == 1:
        jitter_std = jitters[0]

    sock.close()
    print(f"\n  Statistik  : {UDP_COUNT-lost}/{UDP_COUNT} diterima | Packet Loss: {loss_pct:.1f}%")
    if rtts:
        print(f"  Min RTT    : {min(rtts):.2f} ms")
        print(f"  Avg RTT    : {sum(rtts)/len(rtts):.2f} ms")
        print(f"  Max RTT    : {max(rtts):.2f} ms")
    print(f"  Jitter     : {jitter_std:.2f} ms (std dev σ)")
    print(f"  Throughput : {throughput:.2f} kbps")


# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  IFLAB Network Client — Auto Run")
    print("="*60)

    # ── 1. HTTP Test ──────────────────────────────────────────────────────
    print("\n[1] HTTP REQUEST TEST (via Proxy)")
    print("-"*60)
    for path in ["/index.html", "/osi.html", "/missing.html"]:
        http_request(path)

    # ── 2. QoS UDP Ping ───────────────────────────────────────────────────
    print("\n[2] QoS UDP PING TEST")
    print("-"*60)
    qos_ping()


    print("\n" + "="*60)
    print("  Selesai. Cek terminal proxy untuk log HIT/MISS & thread.")
    print("="*60)
