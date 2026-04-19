# scripts/test_day27_dispute_resolution.py
import sys
import time
import requests
import threading
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket, create_bound_request

config = load_config()
VERIFIER_URL = f"http://{config.get('verifier', {}).get('host', '127.0.0.1')}:8002/api/v1/verifier/execute"
VERIFIER_STATE_URL = f"http://{config.get('verifier', {}).get('host', '127.0.0.1')}:8002/api/v1/verifier/ticket_state"
AUDITOR_TRACE_URL = f"http://{config.get('auditor', {}).get('host', '127.0.0.1')}:8004/api/v1/auditor/trace"


def check_evidence(sn: str, expected_state: str):
    """仲裁者工具：提取服务端证据"""
    state_resp = requests.get(f"{VERIFIER_STATE_URL}/{sn}", timeout=5)
    state_resp.raise_for_status()
    actual_state = state_resp.json().get("ticket_state")
    assert actual_state == expected_state, f"状态取证失败: 期望 {expected_state}, 实际 {actual_state}"

    trace_resp = requests.get(f"{AUDITOR_TRACE_URL}/{sn}", timeout=5)
    has_audit = trace_resp.status_code == 200
    return actual_state, has_audit


def run_dispute_resolution():
    print("⚖️ === Day 27: 最小争议验证闭环 (Dispute Resolution) ===\n")

    # -----------------------------------------------------------------
    # 争议 1: 前置拦截 (Dropped Request)
    # -----------------------------------------------------------------
    print("📌 争议 1: 前置拦截 (Dropped Request)")
    ticket1 = acquire_ticket()
    req1 = create_bound_request(ticket1, "payload")
    req1.binding_tag = "invalid_tampered_tag_123"

    # 修正：分步调用，确保抛出明确的 HTTP 错误而不是 JSON 异常
    r1 = requests.post(VERIFIER_URL, json=req1.model_dump(), timeout=10)
    r1.raise_for_status()
    resp1 = r1.json()

    assert resp1["decision"] == "REJECTED"
    assert resp1["reason"] == "Binding Consistency Check Failed"

    state, has_audit = check_evidence(ticket1.sn, "UNUSED")
    assert not has_audit, "被前置 Drop 的请求不应产生审计账本"
    print(f"  ✅ 举证成功: 明确返回原因 [{resp1['reason']}], 票据安全保持在 {state}\n")

    # -----------------------------------------------------------------
    # 争议 2: 处理中重放 (PENDING Collision)
    # -----------------------------------------------------------------
    print("📌 争议 2: 处理中重放 (PENDING Collision)")
    ticket2 = acquire_ticket()
    req2 = create_bound_request(ticket2, "slow_query_payload")

    t1_result = {}

    def fire_req2():
        try:
            r = requests.post(VERIFIER_URL, json=req2.model_dump(), timeout=10)
            r.raise_for_status()
            t1_result["resp"] = r.json()
        except Exception as e:
            t1_result["error"] = str(e)

    t1 = threading.Thread(target=fire_req2)
    t1.start()

    # 原型阶段依赖短暂等待，让首个请求大概率进入 PENDING。
    # 若后续出现不稳定，可改为轮询 state 接口直到观察到 PENDING。
    time.sleep(0.1)

    r2_replay = requests.post(VERIFIER_URL, json=req2.model_dump(), timeout=10)
    r2_replay.raise_for_status()
    resp2_replay = r2_replay.json()

    assert resp2_replay["decision"] == "REJECTED"
    assert "pending" in resp2_replay["reason"].lower() or "concurrent" in resp2_replay["reason"].lower()

    state, _ = check_evidence(ticket2.sn, "PENDING")
    print(f"  ✅ 举证成功: 并发重放被成功阻挡, 原因 [{resp2_replay['reason']}], 票据当前严格处于 {state}")

    t1.join()

    assert "error" not in t1_result, f"请求 1 发生异常: {t1_result.get('error')}"
    assert t1_result["resp"]["decision"] == "SUCCESS", f"请求 1 未成功完成: {t1_result['resp']}"
    assert t1_result["resp"]["ticket_state"] == "CONSUMED", f"请求 1 终态异常: {t1_result['resp']}"
    print("  ✅ 请求 1 最终执行完毕，票据流转至终态 (CONSUMED)。\n")

    # -----------------------------------------------------------------
    # 争议 3: 已核销重放 (CONSUMED Collision)
    # -----------------------------------------------------------------
    print("📌 争议 3: 已核销重放 (CONSUMED Collision)")
    r3 = requests.post(VERIFIER_URL, json=req2.model_dump(), timeout=10)
    r3.raise_for_status()
    resp3 = r3.json()

    assert resp3["decision"] == "REJECTED"
    assert "consumed" in resp3["reason"].lower()

    time.sleep(0.5)
    state, has_audit = check_evidence(ticket2.sn, "CONSUMED")
    assert has_audit, "CONSUMED 状态必须有审计记录支撑"
    print(f"  📎 审计账本存在: {has_audit}")
    print(f"  ✅ 举证成功: 成功识别已完成重放, 原因 [{resp3['reason']}], 物理状态 {state}, 具备底层审计哈希链\n")

    # -----------------------------------------------------------------
    # 争议 4: 后端崩溃与烧毁重放 (FAILED Collision)
    # -----------------------------------------------------------------
    print("📌 争议 4: 后端崩溃与烧毁重放 (FAILED Collision)")
    ticket4 = acquire_ticket()
    req4 = create_bound_request(ticket4, "trigger_failure_test")

    r4 = requests.post(VERIFIER_URL, json=req4.model_dump(), timeout=10)
    r4.raise_for_status()
    resp4 = r4.json()

    assert resp4["decision"] == "REJECTED"
    assert resp4["ticket_state"] == "FAILED"
    assert "burned" in resp4["reason"].lower()

    r4_replay = requests.post(VERIFIER_URL, json=req4.model_dump(), timeout=10)
    r4_replay.raise_for_status()
    resp4_replay = r4_replay.json()

    assert resp4_replay["decision"] == "REJECTED"
    assert "failed" in resp4_replay["reason"].lower()

    time.sleep(0.5)
    state, has_audit = check_evidence(ticket4.sn, "FAILED")
    assert has_audit, "FAILED 状态必须有审计记录支撑"
    print(f"  📎 审计账本存在: {has_audit}")
    print(
        f"  ✅ 举证成功: 后端异常导致票据烧毁为 {state}, 重放被拦截提示 [{resp4_replay['reason']}], 具备底层审计哈希链\n")

    print("🎉 [PASS] Day 27 最小争议验证闭环 (Dispute Resolution) 全场景验收通过！")


if __name__ == "__main__":
    run_dispute_resolution()