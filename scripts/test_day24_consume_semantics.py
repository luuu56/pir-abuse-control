# scripts/test_day24_consume_semantics.py
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
TIMEOUT = config.get("client", {}).get("timeout", 10)


def run_consume_semantics_check():
    print("🚀 === Day 24: Atomic Consume & State Semantics Review ===\n")
    try:
        # ---------------------------------------------------------
        # Case 1: 正常请求 (Happy Path)
        # ---------------------------------------------------------
        print("Case 1: Normal Request (The Happy Path)")
        ticket = acquire_ticket()
        bound_req = create_bound_request(ticket, "normal_query")
        resp1 = requests.post(VERIFIER_URL, json=bound_req.model_dump(), timeout=TIMEOUT)
        data1 = resp1.json()
        assert data1.get("decision") == "SUCCESS", f"Case 1 Failed: {data1}"
        assert data1.get("ticket_state") == "CONSUMED", f"Case 1 State Error: {data1.get('ticket_state')}"
        print("✅ 正常请求 -> 决策: SUCCESS, 终态: CONSUMED")

        # ---------------------------------------------------------
        # Case 2: 无票据请求 (Missing Ticket)
        # ---------------------------------------------------------
        print("\nCase 2: No Ticket (Anonymity Check)")
        req_no_ticket = bound_req.model_copy(deep=True)
        req_no_ticket.ticket = None
        resp2 = requests.post(VERIFIER_URL, json=req_no_ticket.model_dump(), timeout=TIMEOUT)
        data2 = resp2.json()
        assert data2.get("decision") == "REJECTED", "Case 2 should be rejected"
        assert data2.get("reason") == "Missing Ticket in request", f"Case 2 wrong reason: {data2.get('reason')}"
        assert data2.get("ticket_state") == "UNUSED", f"Case 2 State Error: {data2.get('ticket_state')}"
        print("✅ 缺失票据 -> 决策: REJECTED, 原因锁死, 终态: UNUSED")

        # ---------------------------------------------------------
        # Case 3: 过期票据 (Expired Ticket)
        # ---------------------------------------------------------
        print("\nCase 3: Expired Ticket (Time Window Check)")
        ticket_expired = acquire_ticket()
        ticket_expired.epoch_id -= 2  # 篡改纪元
        req_expired = create_bound_request(ticket_expired, "expired_query")
        resp3 = requests.post(VERIFIER_URL, json=req_expired.model_dump(), timeout=TIMEOUT)
        data3 = resp3.json()
        assert data3.get("decision") == "REJECTED", "Case 3 should be rejected"
        assert "expired" in data3.get("reason").lower(), f"Case 3 wrong reason: {data3.get('reason')}"
        assert data3.get("ticket_state") == "UNUSED", f"Case 3 State Error: {data3.get('ticket_state')}"
        print("✅ 过期票据 -> 决策: REJECTED, 原因锁死, 终态: UNUSED")

        # ---------------------------------------------------------
        # Case 4: 篡改绑定 (Tampered Binding)
        # ---------------------------------------------------------
        print("\nCase 4: Tampered Binding (Consistency Check)")
        ticket_valid = acquire_ticket()
        req_tampered = create_bound_request(ticket_valid, "genuine_payload")
        req_tampered.query_payload = "malicious_payload"  # 篡改
        resp4 = requests.post(VERIFIER_URL, json=req_tampered.model_dump(), timeout=TIMEOUT)
        data4 = resp4.json()
        assert data4.get("decision") == "REJECTED", "Case 4 should be rejected"
        assert data4.get("reason") == "Binding Consistency Check Failed", f"Case 4 wrong reason: {data4.get('reason')}"
        assert data4.get("ticket_state") == "UNUSED", f"Case 4 State Error: {data4.get('ticket_state')}"
        print("✅ 篡改绑定 -> 决策: REJECTED, 原因锁死, 终态: UNUSED")

        # ---------------------------------------------------------
        # Case 5: PIR 后端失败 (PIR Failure)
        # ---------------------------------------------------------
        print("\nCase 5: PIR Backend Failure (Ticket Burned)")
        ticket_fail = acquire_ticket()
        # 触发我们在 pir_server 里埋好的故障注入
        req_fail = create_bound_request(ticket_fail, "trigger_failure_test")
        resp5 = requests.post(VERIFIER_URL, json=req_fail.model_dump(), timeout=TIMEOUT)
        data5 = resp5.json()

        # 严格断言：PIR执行失败，必须走向 REJECTED 决策和 FAILED 烧毁终态
        assert data5.get("decision") == "REJECTED", f"Case 5 Decision Error: {data5.get('decision')}"
        assert data5.get(
            "ticket_state") == "FAILED", f"Case 5 State Error: 期望 FAILED, 实际 {data5.get('ticket_state')}"
        assert "burned" in data5.get("reason").lower(), f"Case 5 wrong reason: {data5.get('reason')}"
        print("✅ 后端失败 -> 决策: REJECTED, 原因包含 burned, 终态: FAILED (票据严格烧毁)")

        print("\n🎉 [PASS] Day 24 Atomic Consume Semantics Complete! State machine strictly aligned with decisions.")

    except AssertionError as ae:
        print(f"\n❌ [FAIL] Assertion Error: {ae}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ [FAIL] Unexpected Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_consume_semantics_check()