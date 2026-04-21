# scripts/test_day39_two_level_defense.py
import sys
import socket
import requests
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket, create_bound_request

def test_raw_socket(ip, port, payload):
    try:
        with socket.create_connection((ip, port), timeout=2) as sock:
            sock.sendall(payload)
            sock.recv(1024)
            return "Failed: Connection did not timeout"
    except socket.timeout:
        return "Success: Connection Timeout (Dropped by eBPF)"
    except Exception as e:
        return f"Result: Connection failed ({e})"

def run_day39_tests(target_ip):
    config = load_config()
    issuer_host = config.get("issuer", {}).get("host", "127.0.0.1")
    
    # 【关键问题 1 收口】：强预警，提示必须走方案 A 修改 base.yaml
    if issuer_host in ["127.0.0.1", "localhost"] and target_ip not in ["127.0.0.1", "localhost"]:
        print("="*60)
        print(f"⚠️ [FATAL WARNING] Client config shows Issuer at {issuer_host}!")
        print(f"⚠️ To prevent false negatives in Case C & D, you MUST manually edit:")
        print(f"⚠️ `configs/common/base.yaml` -> Set issuer/verifier/pir_server hosts to {target_ip}")
        print("="*60 + "\n")
    
    verifier_url = f"http://{target_ip}:8002/api/v1/verifier/execute"
    print(f"🚀 === Day 39: eBPF & Verifier Two-Level Defense Integration ===\n")

    # ---------------------------------------------------------
    # Case A: 纯垃圾流量 (命中 eBPF HACK 指纹)
    # ---------------------------------------------------------
    print("--- Case A: Malicious HACK Fingerprint (eBPF Drop) ---")
    res_a = test_raw_socket(target_ip, 8002, b"HACK_ATTACK_GARBAGE_DATA")
    print(f"Result: {res_a}\n")

    # ---------------------------------------------------------
    # Case B: HTTP 候选流量穿过 eBPF，并在用户态被拒绝
    # ---------------------------------------------------------
    print("--- Case B: HTTP Candidate Traffic Rejected in User Space ---")
    payload_b = {
        "request_id": "day39-case-b-missing-fields",
        "query_payload": "test_data"
    }
    try:
        resp_b = requests.post(verifier_url, json=payload_b, timeout=5)
        print(f"HTTP Status: {resp_b.status_code}")
        print(f"Response: {resp_b.text}") # 【小修 2】：打印返回体判定拒绝层级
        
        if resp_b.status_code == 422:
            print("Result: Success (Rejected by FastAPI Schema 422)\n")
        elif resp_b.status_code == 200 and resp_b.json().get("decision") == "REJECTED":
            print("Result: Success (Rejected by Verifier Logic 200+REJECTED)\n")
        else:
            print("Result: Unexpected response behavior.\n")
    except Exception as e:
        print(f"Request failed: {e}\n")

    # ---------------------------------------------------------
    # Case C: 业务重放 / 双花攻击 (Verifier 状态机拦截)
    # ---------------------------------------------------------
    print("--- Case C: Double Spend / Replay Attack (Verifier REJECTED) ---")
    try:
        print("Acquiring real ticket for Case C...")
        ticket_c = acquire_ticket()
        bound_req_c = create_bound_request(ticket_c, "query_target_C")
        payload_c = bound_req_c.model_dump()

        print("  -> First submission (Should reach verifier and normally succeed):")
        resp_c1 = requests.post(verifier_url, json=payload_c, timeout=5)
        print(f"  HTTP Status: {resp_c1.status_code}")
        print(f"  Response: {resp_c1.text}") # 【小修 3】：打印全貌防丢关键错误

        print("\n  -> Second submission (Replay - Should be REJECTED by state machine):")
        resp_c2 = requests.post(verifier_url, json=payload_c, timeout=5)
        print(f"  HTTP Status: {resp_c2.status_code}")
        print(f"  Response: {resp_c2.text}\n")
    except Exception as e:
        print(f"[ERROR] Case C failed to execute gracefully: {e}\n")

    # ---------------------------------------------------------
    # Case D: 完美的合法流量 (穿透全链路)
    # ---------------------------------------------------------
    print("--- Case D: The Happy Path (Full Pipeline Success) ---")
    try: # 【关键问题 2 收口】：增加 Try/Except 保护防脚本崩塌
        print("Acquiring new ticket for Case D...")
        ticket_d = acquire_ticket()
        bound_req_d = create_bound_request(ticket_d, "query_target_D")
        payload_d = bound_req_d.model_dump()

        resp_d = requests.post(verifier_url, json=payload_d, timeout=5)
        print(f"HTTP Status: {resp_d.status_code}")
        print(f"Response: {resp_d.text}")
    except Exception as e:
        print(f"[ERROR] Case D failed to execute gracefully: {e}")

    print("\n✅ Day 39 Tests Completed.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_day39_two_level_defense.py <server_eth0_ip>")
        sys.exit(1)
    
    run_day39_tests(sys.argv[1])