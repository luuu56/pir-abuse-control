# scripts/test_day41_metrics.py
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
    """发送绕过 HTTP 栈的纯字节流"""
    try:
        with socket.create_connection((ip, port), timeout=1) as sock:
            sock.sendall(payload)
            sock.recv(1024)
    except Exception:
        pass

def get_verifier_metrics(verifier_url):
    """获取 Verifier 当前指标"""
    metrics_url = verifier_url.replace("/execute", "/metrics")
    try:
        resp = requests.get(metrics_url, timeout=3)
        return resp.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch metrics: {e}")
        return None

def run_day41_metrics_test(target_ip):
    config = load_config()
    issuer_host = config.get("issuer", {}).get("host", "127.0.0.1")
    if issuer_host in ["127.0.0.1", "localhost"] and target_ip not in ["127.0.0.1", "localhost"]:
        print(f"⚠️ [FATAL WARNING] Client config shows Issuer at {issuer_host}!")
        print(f"⚠️ Please update configs/common/base.yaml to point to {target_ip}")
        sys.exit(1)
        
    verifier_url = f"http://{target_ip}:8002/api/v1/verifier/execute"
    print("🚀 === Day 41: Defense Metrics & Funnel Analysis ===\n")

    print("[*] Fetching initial metrics baseline...")
    baseline = get_verifier_metrics(verifier_url)
    if not baseline:
        sys.exit(1)
    
    total_sent_attempts = 0
    # 客户端观测到的完整 HTTP 往返次数（不代表成功进入了后端逻辑）
    http_responses_received = 0

    # --- 1. 正常流量 (5 次) ---
    print("\n[*] Sending 5 NORMAL requests...")
    for i in range(5):
        total_sent_attempts += 1
        try:
            ticket = acquire_ticket()
            req = create_bound_request(ticket, f"normal_q_{i}")
            resp = requests.post(verifier_url, json=req.model_dump(), timeout=5)
            http_responses_received += 1
            
            decision = resp.json().get('decision', 'N/A') if resp.status_code == 200 else f'HTTP {resp.status_code}'
            reason = resp.json().get('reason', '') if resp.status_code == 200 else resp.text[:30]
            print(f"    - Normal req {i+1} answered (Status: {resp.status_code}, Decision: {decision}, Reason: {reason})")
            
            # 【关键修 1】：显式警告正常流量未达预期的意外情况
            if resp.status_code == 200 and decision != "SUCCESS":
                print(f"      [WARN] Normal flow did not succeed as expected! Funnel may be skewed.")
        except Exception as e:
            print(f"    - Normal req {i+1} failed: {e}")

    # --- 2. 无票据流量 (5 次) ---
    print("\n[*] Sending 5 MISSING TICKET requests...")
    for i in range(5):
        total_sent_attempts += 1
        try:
            payload = {"request_id": f"missing-ticket-{i}", "query_payload": "test"}
            resp = requests.post(verifier_url, json=payload, timeout=2)
            http_responses_received += 1
            
            decision = resp.json().get('decision', 'N/A') if resp.status_code == 200 else f'HTTP {resp.status_code}'
            reason = resp.json().get('reason', '') if resp.status_code == 200 else resp.text[:30]
            print(f"    - Missing ticket req {i+1} answered (Status: {resp.status_code}, Decision: {decision}, Reason: {reason})")
        except Exception as e:
            print(f"    - Missing ticket req {i+1} failed: {e}")

    # --- 3. 静态恶意指纹流量 (5 次) ---
    print("\n[*] Sending 5 STATIC MALICIOUS FINGERPRINT requests (Raw Socket)...")
    for i in range(5):
        total_sent_attempts += 1
        test_raw_socket(target_ip, 8002, b"HACK_ATTACK_GARBAGE_DATA")
        print(f"    - Malicious fingerprint req {i+1} sent (No HTTP response expected)")

    # --- 4. 重放与联动封禁测试 ---
    time.sleep(0.5)  
    print("\n[*] Executing REPLAY storm (1 Orig + 5 Replays)...")
    ticket_replay = acquire_ticket()
    req_replay = create_bound_request(ticket_replay, "replay_target")
    payload_replay = req_replay.model_dump()

    # 4.1 第一次合法消费
    total_sent_attempts += 1
    try:
        resp = requests.post(verifier_url, json=payload_replay, timeout=5)
        http_responses_received += 1
        decision = resp.json().get('decision', 'N/A') if resp.status_code == 200 else f'HTTP {resp.status_code}'
        reason = resp.json().get('reason', '') if resp.status_code == 200 else resp.text[:30]
        print(f"    - Original valid consume answered (Status: {resp.status_code}, Decision: {decision}, Reason: {reason})")
        
        # 【关键修 2】：确保重放风暴的前置条件成立
        if resp.status_code == 200 and decision != "SUCCESS":
            print(f"      [WARN] Original consume did not succeed! Subsequent replay funnel will be invalid.")
    except Exception as e:
        print(f"    - Original valid consume failed: {e}")

    # 4.2 瞬间重放 5 次
    for i in range(5):
        total_sent_attempts += 1
        try:
            resp = requests.post(verifier_url, json=payload_replay, timeout=2)
            http_responses_received += 1
            
            decision = resp.json().get("decision", "N/A") if resp.status_code == 200 else f"HTTP {resp.status_code}"
            reason = resp.json().get("reason", "") if resp.status_code == 200 else resp.text[:30]
            print(f"    - Replay attempt {i+1} answered (Status: {resp.status_code}, Decision: {decision}, Reason: {reason})")
        except requests.exceptions.Timeout:
            print(f"    - Replay attempt {i+1} Timeout (Likely dropped by eBPF fast-path)")
        except Exception as e:
            print(f"    - Replay attempt {i+1} failed: {e}")

    # --- 5. 冷却与数据收集 ---
    print("\n[*] Waiting 2 seconds for logs and metrics to flush...")
    time.sleep(2)
    
    final_metrics = get_verifier_metrics(verifier_url)
    if not final_metrics: 
        print("[ERROR] Failed to fetch final metrics. Cannot compute funnel.")
        sys.exit(1)
    
    # --- 6. 数据精算与漏斗输出 ---
    v_req_delta = final_metrics["total_requests"] - baseline["total_requests"]
    v_block_delta = final_metrics["blocked_before_pir"] - baseline["blocked_before_pir"]
    v_pir_delta = final_metrics["pir_invoked"] - baseline["pir_invoked"]
    
    ebpf_drops_approx = total_sent_attempts - v_req_delta

    print("\n" + "="*70)
    print("📊 DAY 41 TRAFFIC FUNNEL REPORT")
    print("="*70)
    print(f"Total Traffic Sent Attempts : {total_sent_attempts}")
    print(f"┣━ 📨  HTTP Responses Received    : {http_responses_received}")
    print(f"┣━ 🛡️  eBPF Gateway Drops (Approx)*: {ebpf_drops_approx}")
    print(f"┃     (Typically: All malicious fingerprints + Most derived replays)")
    print(f"┗━ 🚪 Reached Verifier (L7)       : {v_req_delta}")
    print(f"   ┣━ 🛑 Verifier Logic Blocks   : {v_block_delta}")
    print(f"   ┃     (Typically: Missing tickets + The first replay attempt)")
    print(f"   ┗━ ✅ Penetrated to PIR       : {v_pir_delta}")
    print(f"         (Typically: Normal traffic + The original valid request)")
    print("="*70)
    print("* NOTE 1: eBPF drop count is a lab approximation calculated as")
    print("  (Total Sent - Verifier Reached), assuming zero external network loss.")
    print("* NOTE 2: HTTP responses received is a client-side observation;")
    print("  Reached Verifier (L7) is derived from server-side metrics and ")
    print("  is the authoritative count.")
    print("="*70)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_day41_metrics.py <server_ip>")
        sys.exit(1)
    run_day41_metrics_test(sys.argv[1])