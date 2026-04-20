# scripts/test_day38_xdp.py
import socket
import requests
import time

TARGET_HOST = "127.0.0.1"
TARGET_PORT = 8002

print("=== Day 38: eBPF Early Filtering Test (Evidence Chain) ===")

# ==========================================
# Test 1: 证明 eBPF 能真实丢弃明显非法流量
# ==========================================
print(f"\n[Test 1] 🔴 Sending explicit garbage bytes ('HACK...') to port {TARGET_PORT}...")
print("   -> 🚨 IMPORTANT: The REAL proof is seeing '[XDP 🛡️] DROP' in the eBPF trace terminal!")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect((TARGET_HOST, TARGET_PORT))
    s.sendall(b"HACK_ATTACK_GARBAGE_PAYLOAD\n\n")
    data = s.recv(1024)
    print("   ❌ App Layer Failed: The Verifier responded? eBPF DROP did not trigger.")
except Exception as e:
    print(f"   ✅ App Layer Disconnected ({type(e).__name__}).")
    print("   👉 Check Terminal 2: If it printed the DROP log, the kernel defense is SUCCESSFUL!")
finally:
    s.close()

time.sleep(1)

# ==========================================
# Test 2: 证明 eBPF 不误伤格式正确的请求
# ==========================================
print(f"\n[Test 2] 🟢 Sending format-valid but business-invalid HTTP POST...")
print("   -> Goal: Prove eBPF safely passes requests that look like HTTP.")
try:
    payload = {"ticket": {"sn": "fake_sn"}, "query_payload": "test"}
    resp = requests.post(f"http://{TARGET_HOST}:{TARGET_PORT}/api/v1/verifier/execute", json=payload)
    print(f"   ✅ Success: Request traversed the eBPF shield safely!")
    print(f"   👉 Verifier returned HTTP {resp.status_code}. (Note: Even 422 or 401 means eBPF success, as it reached the app!)")
except Exception as e:
    print(f"   ❌ Failed: Valid HTTP request was blocked incorrectly: {e}")