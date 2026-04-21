# scripts/test_day43_replay_attacks.py
import sys
import requests
import time
import threading
import concurrent.futures
import copy  # 【修复 1】：引入 deepcopy
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket, create_bound_request

def fire_request(url, payload, req_idx, barrier=None):
    """
    单次发射函数
    引入 Barrier 确保多线程绝对统一起跑
    """
    if barrier:
        barrier.wait()
        
    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code == 200:
            decision = resp.json().get('decision', 'UNKNOWN')
            state = resp.json().get('ticket_state', 'UNKNOWN')
            reason = resp.json().get('reason', '')
            
            # 精细化分类返回结果
            if decision == "SUCCESS":
                category = "SUCCESS"
            else:
                category = f"REJECTED_{state}"
                
            return category, f"[Req-{req_idx:02d}] HTTP 200 | {decision} | State: {state} | Reason: {reason}"
        else:
            return "ERROR", f"[Req-{req_idx:02d}] HTTP {resp.status_code} | {resp.text[:30]}"
    except requests.exceptions.Timeout:
        return "TIMEOUT", f"[Req-{req_idx:02d}] TIMEOUT (Likely dropped by eBPF L4 Dampening)"
    except Exception as e:
        return "ERROR", f"[Req-{req_idx:02d}] ERROR: {e}"

def run_day43_replay_tests(target_ip):
    config = load_config()
    issuer_host = config.get("issuer", {}).get("host", "127.0.0.1")
    if issuer_host in ["127.0.0.1", "localhost"] and target_ip not in ["127.0.0.1", "localhost"]:
        print(f"⚠️ [FATAL WARNING] Client config shows Issuer at {issuer_host}!")
        print(f"⚠️ Please update configs/common/base.yaml to point to {target_ip}")
        sys.exit(1)

    verifier_url = f"http://{target_ip}:8002/api/v1/verifier/execute"
    print("🚀 === Day 43: Malicious Client Replay Attacks ===\n")

    # ---------------------------------------------------------
    # 阶段 1: 串行重放 (Sequential Replay)
    # ---------------------------------------------------------
    print("--- Phase 1: Sequential Replay Attack ---")
    ticket_seq = acquire_ticket()
    req_seq = create_bound_request(ticket_seq, "sequential_test").model_dump()

    print("  -> Attempt 1 (Valid):")
    cat1, msg1 = fire_request(verifier_url, req_seq, 1)
    print(f"     {msg1}")

    print("\n  -> Attempt 2 (Replay after 1 sec):")
    time.sleep(1)
    cat2, msg2 = fire_request(verifier_url, req_seq, 2)
    print(f"     {msg2}")

    print("\n  -> Attempt 3 (Replay after derived block likely applied):")
    print("     (Expected: REJECTED or TIMEOUT depending on ms-level timing)")
    cat3, msg3 = fire_request(verifier_url, req_seq, 3)
    print(f"     {msg3}\n")

    # 等待 Phase 1 触发的 eBPF 10秒封禁过期
    print("[*] Sleeping for 11 seconds to let eBPF Derived Block expire...")
    for i in range(11, 0, -1):
        sys.stdout.write(f"\r    Waiting: {i}s ")
        sys.stdout.flush()
        time.sleep(1)
    print("\n")

    # ---------------------------------------------------------
    # 阶段 2: 高并发风暴重放 (Concurrent Replay)
    # ---------------------------------------------------------
    print("--- Phase 2: Concurrent Replay Storm (20 Threads) ---")
    ticket_conc = acquire_ticket()
    req_conc = create_bound_request(ticket_conc, "concurrent_test").model_dump()
    
    concurrency_level = 20
    barrier = threading.Barrier(concurrency_level)
    results = []
    
    print(f"[*] Firing {concurrency_level} requests simultaneously at the exact same millisecond...\n")
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency_level) as executor:
        futures = []
        for i in range(concurrency_level):
            # 【修复 1】：使用深拷贝彻底切断嵌套引用，并附带独立后缀
            payload_i = copy.deepcopy(req_conc)
            payload_i["request_id"] = f"{req_conc['request_id']}-storm-{i:02d}"
            futures.append(executor.submit(fire_request, verifier_url, payload_i, i, barrier))
            
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
            
    duration = time.time() - start_time
    print(f"\n[*] Storm completed in {duration:.2f} seconds.\n")

    # ---------------------------------------------------------
    # 阶段 3: 战果统计与断言验收 (联合防御网络判定)
    # ---------------------------------------------------------
    print("--- Phase 3: Joint Defense Battle Report ---")
    
    stats = {
        "SUCCESS": 0,
        "REJECTED_PENDING": 0,
        "REJECTED_CONSUMED": 0,
        "TIMEOUT": 0,
        "ERROR": 0
    }
    
    # 打印详细结果
    for cat, msg in results:
        if cat not in stats:
            stats[cat] = 0
        stats[cat] += 1
        print(f"  {msg}")

    # 固定顺序的汇总报告
    print("\n==================================================")
    print("📊 DEFENSE METRICS:")
    print(f"   ✅ SUCCESS Penetrations    : {stats.get('SUCCESS', 0)}")
    print(f"   🛑 REJECTED (Pending Lock) : {stats.get('REJECTED_PENDING', 0)}  <- Defeated by Redis setnx")
    print(f"   🛑 REJECTED (Consumed)     : {stats.get('REJECTED_CONSUMED', 0)}  <- Defeated by State Machine")
    print(f"   🛡️ TIMEOUT (L4 Block)      : {stats.get('TIMEOUT', 0)}  <- Defeated by eBPF Derived Action")
    if stats.get('ERROR', 0) > 0:
        print(f"   ⚠️ ERRORS                  : {stats.get('ERROR', 0)}")
    print("==================================================")

    # 最终断言
    if stats.get('SUCCESS', 0) == 1:
        print("✅ PASS: Exactly ONE request succeeded. Race condition DEFEATED!")
        print("         The joint matrix of Redis atomic locks, Verifier state machine,")
        print("         and eBPF L4 dampening held the line perfectly.")
        
        # 【修复 2】：补充异常噪音预警
        if stats.get('ERROR', 0) > 0:
            print("\n         ⚠️ WARN: Replay defense passed, but ERRORS were observed.")
            print("                  This may indicate network instability or test noise.")
            
    elif stats.get('SUCCESS', 0) == 0:
        print("❌ FAIL: Zero successes. The original legitimate request was blocked.")
    else:
        print(f"❌ FATAL: {stats.get('SUCCESS', 0)} requests succeeded! YOU HAVE A DOUBLE SPEND VULNERABILITY!")
    print("==================================================")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_day43_replay_attacks.py <server_ip>")
        sys.exit(1)
    run_day43_replay_tests(sys.argv[1])