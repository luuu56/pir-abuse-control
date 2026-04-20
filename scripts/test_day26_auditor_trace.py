# scripts/test_day26_auditor_trace.py
import sys
import requests
import time
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.crypto_utils import compute_query_commitment
from services.client.main import acquire_ticket, create_bound_request

config = load_config()
VERIFIER_URL = f"http://{config.get('verifier', {}).get('host', '127.0.0.1')}:8002/api/v1/verifier/execute"
AUDITOR_TRACE_URL = f"http://{config.get('auditor', {}).get('host', '127.0.0.1')}:8004/api/v1/auditor/trace"


def run_auditor_trace_acceptance():
    print("🚀 === Day 26: Auditor Trace & Consistency API Acceptance ===\n")

    # 1. 产生一笔真实交易
    print("1️⃣ Client: 发起交易并保留证据...")
    ticket = acquire_ticket()
    query_payload = "day26_trace_test_payload"
    bound_req = create_bound_request(ticket, query_payload)

    expected_cq = compute_query_commitment(query_payload)
    target_sn = ticket.sn

    # 修改 4: 强化前置交易断言，锁死业务契约
    resp = requests.post(VERIFIER_URL, json=bound_req.model_dump(), timeout=10)
    resp.raise_for_status()
    data = resp.json()
    assert data.get("decision") == "SUCCESS", f"🚨 交易未成功，后续追溯无意义: {data}"

    print(f"   -> 交易完成, 目标 SN: {target_sn[:16]}..., 期望 c_q: {expected_cq[:16]}...")

    # 脆弱等待（目前保持原型级简单实现）
    time.sleep(0.5)

    # 2. 验收点 1：按 SN 查询与链条字段回显
    print("\n2️⃣ Auditor: 按 SN 追溯请求及链条上下文...")
    trace_resp = requests.get(f"{AUDITOR_TRACE_URL}/{target_sn}", timeout=5)
    assert trace_resp.status_code == 200, f"查询失败: {trace_resp.text}"
    trace_data = trace_resp.json()

    assert "chain_context" in trace_data, "未返回日志链上下文"
    print(f"✅ 成功追溯！位于账本第 {trace_data['ledger_line']} 行")
    print(f"   [上一环 Hash]: {trace_data['chain_context']['prev_hash'][:16]}...")
    print(f"   [本环  MAC ]: {trace_data['chain_context']['entry_mac'][:16]}...")

    # 3. 验收点 2：按 SN + c_q 查一致性 (Happy Path)
    print("\n3️⃣ Auditor: 执行一致性校验 (合法 c_q)...")
    valid_verify_resp = requests.get(f"{AUDITOR_TRACE_URL}/{target_sn}?expected_cq={expected_cq}", timeout=5)
    valid_data = valid_verify_resp.json()
    assert valid_data.get("cq_consistent") is True, "一致性校验应为 True"
    print("✅ 一致性判定成功：账本记录的 c_q 与预期完全匹配")

    # 4. 验收点 3：按 SN + 错误 c_q 查一致性 (篡改防护)
    print("\n4️⃣ Auditor: 执行一致性校验 (伪造 c_q)...")
    fake_cq = compute_query_commitment("malicious_payload_after_the_fact")
    fake_verify_resp = requests.get(f"{AUDITOR_TRACE_URL}/{target_sn}?expected_cq={fake_cq}", timeout=5)
    fake_data = fake_verify_resp.json()
    assert fake_data.get("cq_consistent") is False, "伪造 c_q 不应通过一致性校验"
    print("✅ 一致性拦截成功：成功识破事后伪造的载荷承诺！")

    print("\n🎉 [PASS] Day 26 Auditor 追溯与一致性查询接口验收全部通过！")


if __name__ == "__main__":
    run_auditor_trace_acceptance()