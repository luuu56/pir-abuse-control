# scripts/test_day33_abuse_prevention.py
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
REQ_TIMEOUT = 20  # 建议 2：统一配置 timeout


def run_abuse_test():
    print("🛡️ === Day 33: PIR Execution Isolation & Abuse Prevention ===\n")

    # 记录初始 Metrics
    init_metrics = requests.get(METRICS_URL, timeout=REQ_TIMEOUT).json()
    init_total = init_metrics["total_requests"]
    init_blocked = init_metrics["blocked_before_pir"]
    init_pir = init_metrics["pir_invoked"]

    # --- 攻击波次 1：正常的合法用户 ---
    print(">>> Sending 1 VALID request...")
    ticket_valid = acquire_ticket()
    req_valid = create_bound_request(ticket_valid, "legit_user_query")
    r1 = requests.post(VERIFIER_URL, json=req_valid.model_dump(), timeout=REQ_TIMEOUT)
    assert r1.json()["decision"] == "SUCCESS"
    print("✅ Valid request SUCCESS.")

    # --- 攻击波次 2：篡改载荷的请求 ---
    print("\n>>> Sending MALICIOUS request (Tampered payload)...")
    req_tampered = create_bound_request(acquire_ticket(), "original_query")
    req_tampered.query_payload = "hacked_query"
    r2 = requests.post(VERIFIER_URL, json=req_tampered.model_dump(), timeout=REQ_TIMEOUT)
    assert r2.json()["decision"] == "REJECTED"
    print(f"🚫 Blocked: {r2.json()['reason']}")

    # --- 攻击波次 3：没有 Ticket 的野蛮请求 ---
    print("\n>>> Sending MALICIOUS request (Missing Ticket)...")
    # 建议 1 落地：转 dict 后暴力移除，绕过 Pydantic 客户端校验，实现真实攻击组装
    req_dict_no_ticket = req_valid.model_dump()
    req_dict_no_ticket.pop("ticket", None)

    r3 = requests.post(VERIFIER_URL, json=req_dict_no_ticket, timeout=REQ_TIMEOUT)
    # 因为 Pydantic FastAPI 服务端会拦截缺字段请求，所以大概率是 422
    if r3.status_code == 422:
        print("🚫 Blocked: Fast Fail by FastAPI Validation (422 Unprocessable Entity)")
    else:
        assert r3.json()["decision"] == "REJECTED"
        print(f"🚫 Blocked: {r3.json()['reason']}")

    # --- 攻击波次 4：重放波次 1 的旧请求 ---
    print("\n>>> Sending MALICIOUS request (Replay Attack)...")
    r4 = requests.post(VERIFIER_URL, json=req_valid.model_dump(), timeout=REQ_TIMEOUT)
    assert r4.json()["decision"] == "REJECTED"
    print(f"🚫 Blocked: {r4.json()['reason']}")

    # --- 最终验收：对账 Metrics！ ---
    print("\n📊 === Auditing Verifier Metrics ===")
    final_metrics = requests.get(METRICS_URL, timeout=REQ_TIMEOUT).json()

    added_total = final_metrics["total_requests"] - init_total
    added_pir = final_metrics["pir_invoked"] - init_pir
    added_blocked = final_metrics["blocked_before_pir"] - init_blocked

    print(f"Total Requests Fired : {added_total}")
    # 因为 422 拦截发生在 FastAPI 路由解析层，还没进 execute_query 的业务代码
    # 所以业务内 blocked 计数可能是 2 (篡改 + 重放)，也无妨，只要 PIR = 1 就行。
    print(f"Business Blocked     : {added_blocked}")
    print(f"Actual PIR Invoked   : {added_pir}")

    # 硬核断言
    assert added_pir == 1, "CRITICAL SECURITY BREACH: A malicious request leaked into PIR backend!"

    print("\n✅ Day 33 Success: PIR engine is perfectly isolated from malicious traffic!")


if __name__ == "__main__":
    run_abuse_test()