# scripts/test_day34_functional_metrics.py
import sys
import requests
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket, create_bound_request

config = load_config()
v_cfg = config.get("verifier", {})
VERIFIER_URL = f"http://{v_cfg.get('host', '127.0.0.1')}:{v_cfg.get('port', 8002)}/api/v1/verifier/execute"
METRICS_URL = f"http://{v_cfg.get('host', '127.0.0.1')}:{v_cfg.get('port', 8002)}/api/v1/verifier/metrics"
REQ_TIMEOUT = 10


def run_functional_metrics():
    print("📊 === Day 34: Functional Metrics & Defense Report ===\n")

    # 1. 记录初始系统指标
    try:
        init_metrics = requests.get(METRICS_URL, timeout=REQ_TIMEOUT).json()
        print(f"[Debug] Init Metrics: {init_metrics}")
    except Exception as e:
        print(f"❌ Failed to reach Verifier metrics: {e}")
        sys.exit(1)

    init_total = init_metrics["total_requests"]
    init_pir = init_metrics["pir_invoked"]

    stats = {
        "valid_sent": 0, "valid_success": 0,
        "replay_sent": 0, "replay_blocked": 0,
        "binding_sent": 0, "binding_blocked": 0,
        "sig_sent": 0, "sig_blocked": 0
    }

    valid_requests_cache = []

    print("\n🚀 Firing 10 deterministic test requests...\n")

    # --- 波次 A: 5 个正常请求 ---
    for i in range(5):
        req = create_bound_request(acquire_ticket(), f"query_valid_{i}")
        resp = requests.post(VERIFIER_URL, json=req.model_dump(), timeout=REQ_TIMEOUT)
        stats["valid_sent"] += 1
        if resp.status_code == 200 and resp.json().get("decision") == "SUCCESS":
            stats["valid_success"] += 1
            valid_requests_cache.append(req)
        print(f"  [Valid] Request {i + 1}/5 fired.")

    # 建议 1 落地：保护断言，Fail-Fast 机制
    assert len(
        valid_requests_cache) > 0, "❌ Critical: Normal requests failed, cannot perform replay attacks! Fix the main path first."

    # --- 波次 B: 3 个重放攻击 (复用波次 A 的载荷) ---
    for i in range(3):
        req = valid_requests_cache[i % len(valid_requests_cache)]
        resp = requests.post(VERIFIER_URL, json=req.model_dump(), timeout=REQ_TIMEOUT)
        stats["replay_sent"] += 1
        if resp.status_code == 200 and resp.json().get("decision") == "REJECTED":
            stats["replay_blocked"] += 1
        print(f"  [Replay] Attack {i + 1}/3 fired.")

    # --- 波次 C: 1 个 Binding 篡改请求 ---
    req_tampered = create_bound_request(acquire_ticket(), "query_binding")
    req_tampered.query_payload = "hacked_payload"
    resp = requests.post(VERIFIER_URL, json=req_tampered.model_dump(), timeout=REQ_TIMEOUT)
    stats["binding_sent"] += 1
    if resp.status_code == 200 and resp.json().get("decision") == "REJECTED":
        stats["binding_blocked"] += 1
    print("  [Binding] Tampered request fired.")

    # --- 波次 D: 1 个伪造签名请求 ---
    req_bad_sig = create_bound_request(acquire_ticket(), "query_sig")
    orig_sig = req_bad_sig.ticket.sigma
    # 建议 2 落地：使用合法的 Base64 字符 "A" 且严格保持长度不变，确保稳死在验签层
    tampered_sig = orig_sig[:10] + "AAAA" + orig_sig[14:] if len(orig_sig) > 14 else "A" * len(orig_sig)
    req_bad_sig.ticket.sigma = tampered_sig

    resp = requests.post(VERIFIER_URL, json=req_bad_sig.model_dump(), timeout=REQ_TIMEOUT)
    stats["sig_sent"] += 1
    if resp.status_code == 200 and resp.json().get("decision") == "REJECTED":
        stats["sig_blocked"] += 1
    print("  [Signature] Forged signature request fired.\n")

    # 3. 计算与出具最终报表
    final_metrics = requests.get(METRICS_URL, timeout=REQ_TIMEOUT).json()
    print(f"[Debug] Final Metrics: {final_metrics}\n")

    added_total = final_metrics["total_requests"] - init_total
    added_pir = final_metrics["pir_invoked"] - init_pir

    # 核心指标计算
    valid_success_rate = (stats["valid_success"] / stats["valid_sent"]) * 100
    replay_block_rate = (stats["replay_blocked"] / stats["replay_sent"]) * 100
    binding_block_rate = (stats["binding_blocked"] / stats["binding_sent"]) * 100
    sig_block_rate = (stats["sig_blocked"] / stats["sig_sent"]) * 100
    pir_entry_ratio = (added_pir / added_total) * 100 if added_total > 0 else 0

    print("==================================================")
    print(" 🛡️  PIR Anti-Abuse Functional Metrics Report  🛡️")
    print("==================================================")
    print(
        f" 🟢 Normal Request Success Rate  : {valid_success_rate:6.2f}% ({stats['valid_success']}/{stats['valid_sent']})")
    print(
        f" 🔴 Replay Interception Rate     : {replay_block_rate:6.2f}% ({stats['replay_blocked']}/{stats['replay_sent']})")
    print(
        f" 🔴 Binding Interception Rate    : {binding_block_rate:6.2f}% ({stats['binding_blocked']}/{stats['binding_sent']})")
    print(f" 🟣 Signature Interception Rate  : {sig_block_rate:6.2f}% ({stats['sig_blocked']}/{stats['sig_sent']})")
    print("--------------------------------------------------")
    print(f" ⚙️  Total Requests Processed     : {added_total}")
    print(f" 🎯 Expected PIR Invocations     : {stats['valid_success']}")
    print(f" ⚡ Actual PIR Engine Invoked    : {added_pir}")
    print(f" 📉 PIR Entry Proportion         : {pir_entry_ratio:6.2f}%")
    print("==================================================")

    assert valid_success_rate == 100.0, "System failing to serve valid users!"
    assert replay_block_rate == 100.0, "System failing to block replays!"
    assert binding_block_rate == 100.0, "System failing to block binding tampering!"
    assert sig_block_rate == 100.0, "System failing to block signature forgery!"

    assert added_pir == stats[
        "valid_success"], f"PIR leakage! Expected {stats['valid_success']}, but invoked {added_pir}."


if __name__ == "__main__":
    run_functional_metrics()