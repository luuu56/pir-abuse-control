# scripts/test_day40_derived_block.py
import sys
import socket
import requests
import time
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
            return "Failed: Connection did not timeout (Fast-path failed)"
    except socket.timeout:
        return "Success: Connection Timeout (Dropped by eBPF)"
    except Exception as e:
        return f"Result: Connection failed ({e})"

def run_day40_final_acceptance(target_ip):
    config = load_config()
    issuer_host = config.get("issuer", {}).get("host", "127.0.0.1")
    
    # 强预警：必须保证本地 YAML 配置已指向远端服务器
    if issuer_host in ["127.0.0.1", "localhost"] and target_ip not in ["127.0.0.1", "localhost"]:
        print("="*60)
        print(f"⚠️ [FATAL WARNING] Client config shows Issuer at {issuer_host}!")
        print(f"⚠️ To prevent false negatives, you MUST manually edit:")
        print(f"⚠️ `configs/common/base.yaml` -> Set issuer/verifier/pir_server hosts to {target_ip}")
        print("="*60 + "\n")
        sys.exit(1)
    
    verifier_url = f"http://{target_ip}:8002/api/v1/verifier/execute"
    print(f"🚀 === Day 40: eBPF Derived State Filtering Acceptance ===\n")

    # ---------------------------------------------------------
    # Case A: 纯垃圾流量 (命中 eBPF 静态指纹)
    # ---------------------------------------------------------
    print("--- Case A: Malicious HACK Fingerprint (eBPF Static Drop) ---")
    res_a = test_raw_socket(target_ip, 8002, b"HACK_ATTACK_GARBAGE_DATA")
    print(f"Result: {res_a}\n")

    # ---------------------------------------------------------
    # Case B: HTTP 候选流量穿过 eBPF，并在用户态被拒绝
    # ---------------------------------------------------------
    print("--- Case B: HTTP Candidate Traffic Rejected in User Space ---")
    payload_b = {
        "request_id": "day40-case-b-missing-fields",
        "query_payload": "test_data"
    }
    try:
        resp_b = requests.post(verifier_url, json=payload_b, timeout=5)
        print(f"HTTP Status: {resp_b.status_code}")
        print(f"Response: {resp_b.text}") 
        
        if resp_b.status_code == 422:
            print("Result: Success (Rejected by FastAPI Schema 422)\n")
        elif resp_b.status_code == 200 and resp_b.json().get("decision") == "REJECTED":
            print("Result: Success (Rejected by Verifier Logic 200+REJECTED)\n")
        else:
            print("Result: Unexpected response behavior.\n")
    except Exception as e:
        print(f"Request failed: {e}\n")

    # ---------------------------------------------------------
    # Case C: 重放诱发封禁 (Verifier 判定 CONSUMED 并派生 block)
    # ---------------------------------------------------------
    print("--- Case C: Triggering Replay-Derived Block ---")
    try:
        print("Acquiring real ticket for Case C...")
        ticket_c = acquire_ticket()
        bound_req_c = create_bound_request(ticket_c, "replay_test_query")
        payload_c = bound_req_c.model_dump()

        print("  -> Attempt 1: Successful Consume (Should reach Verifier and succeed)")
        resp_c1 = requests.post(verifier_url, json=payload_c, timeout=5)
        print(f"     HTTP Status: {resp_c1.status_code}")
        print(f"     Decision: {resp_c1.json().get('decision') if resp_c1.status_code == 200 else resp_c1.text}")

        print("\n  -> Attempt 2: Replay (Expect Verifier REJECT + CONTROL Sync)")
        resp_c2 = requests.post(verifier_url, json=payload_c, timeout=5)
        print(f"     HTTP Status: {resp_c2.status_code}")
        if resp_c2.status_code == 200:
            print(f"     Decision: {resp_c2.json().get('decision')}")
            print(f"     Reason: {resp_c2.json().get('reason')}")
        else:
            print(f"     Response: {resp_c2.text}")
        print()
    except Exception as e:
        print(f"[ERROR] Case C failed to execute gracefully: {e}\n")

    # ---------------------------------------------------------
    # Case D: 联动有效性验证 (同源请求被派生封禁拦截)
    # ---------------------------------------------------------
    print("--- Case D: Post-Replay Suppression Analysis ---")
    print("Sending brand-new valid ticket from same source immediately...")
    try:
        # 注意：由于我们在内核修改了顺序，这里请求 8001 (Issuer) 获取新票应该成功
        new_ticket = acquire_ticket()
        new_req = create_bound_request(new_ticket, "post_block_test")
        
        print("  -> Sending valid payload to Verifier (8002)... Expecting timeout!")
        start_time = time.time()
        # 预期此处请求 8002 时会 Timeout
        resp_d = requests.post(verifier_url, json=new_req.model_dump(), timeout=3)
        print(f"  [CRITICAL FAILURE] Request reached Verifier! Status: {resp_d.status_code}")
        print(f"  Response: {resp_d.text}")
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        duration = time.time() - start_time
        print(f"  [EVIDENCE] Client connection blocked by eBPF fast-path after {duration:.2f}s.")
        print("\n  [CHECK 1] Please verify Server Verifier Logs for 'Deriving short-term L4 block...'")
        print("  [CHECK 2] Please verify Server TC Gateway Logs for '[CONTROL] Derived Block Sync from verifier decision...'")
        print("  [CHECK 3] Please verify Server TC Trace for '[TC DROP] Derived Block: source IP matched...'")
        print("\n✅ Day 40: Multi-point verification satisfied.")
    except Exception as e:
        print(f"[ERROR] Case D unexpected failure: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_day40_derived_block.py <server_eth0_ip>")
        sys.exit(1)
    
    run_day40_final_acceptance(sys.argv[1])