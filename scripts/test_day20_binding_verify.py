# scripts/test_day20_binding_verify.py
import sys
import requests
from pathlib import Path

# 将根目录加入 sys.path
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket, create_bound_request

# --- 1. 初始化配置与超时设置 ---
config = load_config()
verifier_cfg = config.get("verifier", {})
v_host = verifier_cfg.get("host", "127.0.0.1")
v_port = verifier_cfg.get("port", 8002)
VERIFIER_URL = f"http://{v_host}:{v_port}/api/v1/verifier/execute"

client_cfg = config.get("client", {})
REQUEST_TIMEOUT_SEC = client_cfg.get("timeout", 10)


def safe_assert_rejection(resp: requests.Response, expected_reason_keyword: str, step_name: str):
    """安全断言 Helper：防范非 JSON 响应，并提供清晰的失败上下文"""
    try:
        data = resp.json()
    except Exception:
        raise AssertionError(f"[{step_name}] Expected JSON response, but got HTTP {resp.status_code}: {resp.text}")

    assert data.get(
        "decision") == "REJECTED", f"[{step_name}] Expected REJECTED, got {data.get('decision')}. Data: {data}"
    assert expected_reason_keyword in data.get("reason",
                                               ""), f"[{step_name}] Wrong rejection reason. Expected to contain '{expected_reason_keyword}', got: '{data.get('reason')}'"


def test_binding_verification():
    print("🚀 === Day 20: Binding Verification & Tampering Test ===\n")
    try:
        # 1. 拿到合法的 Ticket 和绑定的 Request
        print("Step 1: Acquiring ticket and creating genuine bound request...")
        ticket = acquire_ticket()
        original_payload = "day20_genuine_query_payload"
        bound_req = create_bound_request(ticket, original_payload)
        print(f"✅ Genuine Request generated. Binding Tag: {bound_req.binding_tag[:16]}...")

        # -------------------------------------------------------------
        # 负例测试：必须在合法请求发送前进行，以免票据被提前消费
        # -------------------------------------------------------------

        # 2. 篡改 q (query_payload)
        print("\nStep 2: Malicious Action -> Tampering with q (query_payload)...")
        req_tampered_q = bound_req.model_copy(deep=True)
        req_tampered_q.query_payload = "malicious_injected_query"
        resp_q = requests.post(VERIFIER_URL, json=req_tampered_q.model_dump(), timeout=REQUEST_TIMEOUT_SEC)
        safe_assert_rejection(resp_q, "Binding Consistency Check Failed", "Tamper q")
        print("✅ Defender Win: Tampered query correctly rejected.")

        # 3. 篡改 b (binding_tag)
        print("\nStep 3: Malicious Action -> Tampering with b (binding_tag)...")
        req_tampered_b = bound_req.model_copy(deep=True)
        last_char = "0" if req_tampered_b.binding_tag[-1] != "0" else "1"
        req_tampered_b.binding_tag = req_tampered_b.binding_tag[:-1] + last_char
        resp_b = requests.post(VERIFIER_URL, json=req_tampered_b.model_dump(), timeout=REQUEST_TIMEOUT_SEC)
        safe_assert_rejection(resp_b, "Binding Consistency Check Failed", "Tamper b")
        print("✅ Defender Win: Tampered binding tag correctly rejected.")

        # 4. 篡改 w (witness)
        print("\nStep 4: Malicious Action -> Tampering with w (witness nonce)...")
        req_tampered_w = bound_req.model_copy(deep=True)
        req_tampered_w.witness.nonce = "00000000-0000-0000-0000-000000000000"
        resp_w = requests.post(VERIFIER_URL, json=req_tampered_w.model_dump(), timeout=REQUEST_TIMEOUT_SEC)
        safe_assert_rejection(resp_w, "Binding Consistency Check Failed", "Tamper w")
        print("✅ Defender Win: Tampered witness correctly rejected.")

        # 5. 缺失 Witness (Day 20 补充单测)
        print("\nStep 5: Malicious Action -> Removing Witness entirely...")
        req_no_w = bound_req.model_copy(deep=True)
        req_no_w.witness = None
        resp_no_w = requests.post(VERIFIER_URL, json=req_no_w.model_dump(), timeout=REQUEST_TIMEOUT_SEC)
        safe_assert_rejection(resp_no_w, "Missing Request Witness", "Missing w")
        print("✅ Defender Win: Missing witness correctly rejected.")

        # -------------------------------------------------------------
        # 正例测试：最后发送合法请求，验证核销链路
        # -------------------------------------------------------------
        print("\nStep 6: Verifying genuine request (Happy Path)...")
        resp_genuine = requests.post(VERIFIER_URL, json=bound_req.model_dump(), timeout=REQUEST_TIMEOUT_SEC)

        try:
            genuine_data = resp_genuine.json()
        except Exception:
            raise AssertionError(
                f"[Happy Path] Expected JSON response, but got HTTP {resp_genuine.status_code}: {resp_genuine.text}")

        assert genuine_data.get(
            "decision") == "SUCCESS", f"Genuine request failed! Reason: {genuine_data.get('reason')}"
        print("✅ Genuine request correctly accepted and executed (Ticket Consumed).")

        print("\n🎉 [PASS] Day 20 Acceptance Criteria Met: All verification branches tested and passed!")

    except AssertionError as ae:
        print(f"\n❌ [FAIL] Assertion Error: {ae}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ [FAIL] Unexpected Exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    test_binding_verification()