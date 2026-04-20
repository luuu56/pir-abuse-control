# scripts/test_day21_integration.py
import sys
import requests
import time
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket, create_bound_request

config = load_config()
v_cfg = config.get("verifier", {})
VERIFIER_URL = f"http://{v_cfg.get('host', '127.0.0.1')}:{v_cfg.get('port', 8002)}/api/v1/verifier/execute"
TIMEOUT = config.get("client", {}).get("timeout", 10)

def run_integration():
    print("🚀 === Day 21: Weekly Integration - Final Defense Review ===\n")
    try:
        # 1. 正常请求
        print("Case 1: Normal Request (The Happy Path)")
        ticket = acquire_ticket()
        bound_req = create_bound_request(ticket, "normal_query")
        resp1 = requests.post(VERIFIER_URL, json=bound_req.model_dump(), timeout=TIMEOUT)
        data1 = resp1.json()
        assert data1.get("decision") == "SUCCESS", f"Case 1 Failed: {data1}"
        print("✅ 正常请求 -> SUCCESS")

        # 2. 无票据请求
        print("\nCase 2: No Ticket (Anonymity Check)")
        req_no_ticket = bound_req.model_copy(deep=True)
        req_no_ticket.ticket = None
        resp2 = requests.post(VERIFIER_URL, json=req_no_ticket.model_dump(), timeout=TIMEOUT)
        data2 = resp2.json()
        assert data2.get("decision") == "REJECTED", "Case 2 should be rejected"
        # 修正：使用全等断言锁死业务契约
        assert data2.get("reason") == "Missing Ticket in request", f"Case 2 wrong reason: {data2.get('reason')}"
        print("✅ 缺失票据 -> 真实区分 (Missing Ticket in request)")

        # 3. 过期票据 (必须先改 epoch，再做 binding)
        print("\nCase 3: Expired Ticket (Time Window Check)")
        ticket_expired = acquire_ticket()
        ticket_expired.epoch_id -= 2  # 篡改纪元
        req_expired = create_bound_request(ticket_expired, "expired_query") # 使用篡改后的纪元做绑定
        resp3 = requests.post(VERIFIER_URL, json=req_expired.model_dump(), timeout=TIMEOUT)
        data3 = resp3.json()
        assert data3.get("decision") == "REJECTED", "Case 3 should be rejected"
        # 保持：由于包含动态纪元数字，使用部分匹配
        assert "expired" in data3.get("reason").lower(), f"Case 3 wrong reason: {data3.get('reason')}"
        print("✅ 过期票据 -> 真实区分 (Ticket expired)")

        # 4. 篡改绑定请求
        print("\nCase 4: Tampered Binding (Consistency Check)")
        ticket_valid = acquire_ticket()
        req_tampered = create_bound_request(ticket_valid, "genuine_payload")
        req_tampered.query_payload = "malicious_payload" # 篡改 payload，使得原有 binding_tag 失效
        resp4 = requests.post(VERIFIER_URL, json=req_tampered.model_dump(), timeout=TIMEOUT)
        data4 = resp4.json()
        assert data4.get("decision") == "REJECTED", "Case 4 should be rejected"
        # 修正：使用全等断言锁死业务契约
        assert data4.get("reason") == "Binding Consistency Check Failed", f"Case 4 wrong reason: {data4.get('reason')}"
        print("✅ 篡改绑定 -> 真实区分 (Binding Consistency Check Failed)")

        print("\n🎉 [PASS] Day 21 Weekly Integration Complete! All scenarios distinctly handled.")

    except AssertionError as ae:
        print(f"\n❌ [FAIL] Assertion Error: {ae}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ [FAIL] Unexpected Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_integration()