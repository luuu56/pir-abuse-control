# scripts/test_day44_batch_abuse.py
import sys
import time
import requests
import concurrent.futures
import copy
import argparse
from collections import Counter
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket, create_bound_request

def get_verifier_metrics(metrics_url):
    """获取 Verifier 当前权威指标"""
    try:
        resp = requests.get(metrics_url, timeout=3)
        resp.raise_for_status()  # 【修复 1】：增强容错与报错精细度
        return resp.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch metrics: {e}")
        return None

def fire_request(session, url, payload, req_id):
    """单次压测发射函数，带有耗时统计"""
    start_time = time.time()
    try:
        resp = session.post(url, json=payload, timeout=15)
        latency = time.time() - start_time
        if resp.status_code == 200:
            decision = resp.json().get('decision', 'UNKNOWN')
            reason = resp.json().get('reason', '')
            return latency, f"200_{decision}", reason
        else:
            return latency, f"HTTP_{resp.status_code}", resp.text[:30]
    except requests.exceptions.Timeout:
        return time.time() - start_time, "TIMEOUT", "Request timed out"
    except Exception as e:
        return time.time() - start_time, "ERROR", str(e)

def run_stress_test(phase_name, session, url, payloads, metrics_url, concurrency):
    """执行一轮并发压测并输出包含服务端 Metrics 的联合报表"""
    print(f"\n{'='*65}")
    print(f"🚀 {phase_name} ({len(payloads)} reqs @ {concurrency} workers)")
    print(f"{'='*65}")
    
    baseline = get_verifier_metrics(metrics_url)
    
    results = []
    latencies = []
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = []
        for i, payload in enumerate(payloads):
            futures.append(executor.submit(fire_request, session, url, payload, i))
            
        for future in concurrent.futures.as_completed(futures):
            lat, cat, reason = future.result()
            latencies.append(lat)
            results.append((cat, reason))
            
    total_time = time.time() - start_time
    
    time.sleep(1.0) 
    final_metrics = get_verifier_metrics(metrics_url)
    
    qps = len(payloads) / total_time if total_time > 0 else 0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    cat_counter = Counter([cat for cat, _ in results])
    
    print(f"⏱️  Duration    : {total_time:.2f} s")
    print(f"⚡ Throughput  : {qps:.2f} req/sec (Client perspective)")
    print(f"🐢 Avg Latency : {avg_latency*1000:.1f} ms (Max: {max_latency*1000:.1f} ms)")
    print("-" * 45)
    print("💻 [Client-Side Observations]:")
    for cat, count in cat_counter.items():
        print(f"   [{count:3d}] {cat}")
        
        # 【修复 2】：提取并打印该类别的所有不同 Reason（最多展示前两个）
        unique_reasons = list(set([r for c, r in results if c == cat]))
        for idx, reason in enumerate(unique_reasons[:2]):
            print(f"         └─ Sample Reason {idx+1}: {reason}")
        if len(unique_reasons) > 2:
            print(f"         └─ ... and {len(unique_reasons)-2} more variants.")
            
    print("-" * 45)
    print("🖥️  [Server-Side L7 Metrics Delta]:")
    if baseline and final_metrics:
        v_req = final_metrics["total_requests"] - baseline["total_requests"]
        v_blk = final_metrics["blocked_before_pir"] - baseline["blocked_before_pir"]
        v_pir = final_metrics["pir_invoked"] - baseline["pir_invoked"]
        print(f"   Total Reached Verifier : +{v_req}")
        print(f"   Blocked Before PIR     : +{v_blk}")
        print(f"   Penetrated to PIR      : +{v_pir}")
    else:
        print("   [!] Could not fetch server metrics.")
    print("=" * 65)

def run_day44_batch_tests(target_ip, batch_size, concurrency):
    config = load_config()
    issuer_host = config.get("issuer", {}).get("host", "127.0.0.1")
    if issuer_host in ["127.0.0.1", "localhost"] and target_ip not in ["127.0.0.1", "localhost"]:
        print(f"⚠️ [FATAL WARNING] Client config shows Issuer at {issuer_host}!")
        sys.exit(1)

    verifier_url = f"http://{target_ip}:8002/api/v1/verifier/execute"
    metrics_url = f"http://{target_ip}:8002/api/v1/verifier/metrics"
    
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=concurrency, pool_maxsize=concurrency)
    session.mount('http://', adapter)
    
    print("🚀 === Day 44: Client Batch Abuse & Full Path Stress Test ===\n")
    print(f"[*] Configuration: BATCH_SIZE={batch_size}, CONCURRENCY={concurrency}")
    print("[*] Note: 'Fake ticket' abuse is represented via sigma tampering in this test.")
    
    # ---------------------------------------------------------
    # 阶段 0: 备弹
    # ---------------------------------------------------------
    print(f"\n[*] Pre-acquiring {batch_size} valid tickets (Warming up Issuer)...")
    valid_payloads = []
    for i in range(batch_size):
        sys.stdout.write(f"\r    Acquiring ticket {i+1}/{batch_size} ...")
        sys.stdout.flush()
        ticket = acquire_ticket()
        req = create_bound_request(ticket, f"stress_query_{i}")
        valid_payloads.append(req.model_dump())
    print("\n[+] Ammunition ready.\n")
    
    # ---------------------------------------------------------
    # Phase 1: 合法洪峰
    # ---------------------------------------------------------
    run_stress_test("PHASE 1: Valid Ticket Storm (Full Path Stress)", session, verifier_url, valid_payloads, metrics_url, concurrency)
    
    print("\n[*] Cooling down for 2 seconds to let Verifier & PIR backends settle...")
    time.sleep(2)
    
    # ---------------------------------------------------------
    # Phase 2: 密码学滥用
    # ---------------------------------------------------------
    crypto_abuse_payloads = []
    for i, base_payload in enumerate(valid_payloads):
        bad_payload = copy.deepcopy(base_payload)
        bad_payload["request_id"] = f"crypto-abuse-{i}"
        
        if i % 2 == 0:
            bad_payload["ticket"]["sigma"] = "aW52YWxpZF9iYXNlNjRfc2lnbmF0dXJlX2Zvcl90ZXN0"
        else:
            bad_payload["binding_tag"] = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
            
        crypto_abuse_payloads.append(bad_payload)
        
    run_stress_test("PHASE 2: Crypto Material Abuse (Fake Sigs & Bindings)", session, verifier_url, crypto_abuse_payloads, metrics_url, concurrency)

    print("\n[*] Cooling down for 2 seconds to avoid L7 state bleeding...")
    time.sleep(2)
    
    # ---------------------------------------------------------
    # Phase 3: 无票据滥用
    # ---------------------------------------------------------
    schema_abuse_payloads = []
    for i in range(batch_size):
        schema_abuse_payloads.append({
            "request_id": f"missing-ticket-abuse-{i}",
            "query_payload": "test_garbage_data"
        })
        
    run_stress_test("PHASE 3: Missing Ticket / Missing Witness Abuse", session, verifier_url, schema_abuse_payloads, metrics_url, concurrency)
    
    print("\n✅ Day 44 Batch Abuse & Load Test Completed.")

if __name__ == "__main__":
    import logging
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description="Day 44 Batch Abuse & Load Tester")
    parser.add_argument("server_ip", help="Target server IP address")
    parser.add_argument("--batch", type=int, default=30, help="Number of requests per phase (default: 30)")
    parser.add_argument("--concurrency", type=int, default=15, help="Number of concurrent workers (default: 15)")
    
    args = parser.parse_args()
    run_day44_batch_tests(args.server_ip, args.batch, args.concurrency)