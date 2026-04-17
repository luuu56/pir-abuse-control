# scripts/test_day10_verifier.py
import sys
import time
import uuid
import base64
import requests
from copy import deepcopy
from pathlib import Path

# 把根目录加进 sys.path
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket

# --- 统一配置与常量 ---
config = load_config()
verifier_cfg = config.get("verifier", {})
VERIFIER_URL = f"http://{verifier_cfg.get('host', '127.0.0.1')}:{verifier_cfg.get('port', 8002)}/api/v1/verifier/execute"
REQUEST_TIMEOUT_SEC = 5


def build_request(ticket_dict: dict) -> dict:
    """构造完整的 RequestInstance 结构"""
    return {
        "request_id": str(uuid.uuid4()),
        "query_payload": "day10_test_query",
        "ticket": ticket_dict,
        "binding_tag": "dummy_binding_for_day10",
        "witness": {
            "timestamp_ms": int(time.time() * 1000),
            "nonce": str(uuid.uuid4()),
            "client_state_digest": "dummy_digest"
        }
    }


def run_tests():
    print("=== Step 1: Acquiring valid ticket from Issuer ===")
    try:
        ticket = acquire_ticket()
        base_req = build_request(ticket.model_dump())
    except Exception as e:
        print(f"Failed to acquire ticket. Is Issuer running? Error: {e}")
        return

    print("\n=== Test 1: Happy Path (Valid Ticket) ===")
    print("Expected: HTTP 200, Decision: SUCCESS")
    try:
        r1 = requests.post(VERIFIER_URL, json=base_req, timeout=REQUEST_TIMEOUT_SEC)
        print(f"HTTP Status: {r1.status_code}")
        print(f"Response: {r1.json() if r1.status_code == 200 else r1.text}")
    except Exception as e:
        print(f"Request failed: {e}")

    print("\n=== Test 2: Negative Path (Tampered SN) ===")
    print("Expected: HTTP 200, Decision: REJECTED")
    req2 = deepcopy(base_req)
    req2["request_id"] = str(uuid.uuid4())
    old_sn = req2["ticket"]["sn"]

    # 篡改最后一位，保持合法 hex
    tampered_sn = old_sn[:-1] + ('a' if old_sn[-1] != 'a' else 'b')
    req2["ticket"]["sn"] = tampered_sn
    print(f"Tampered SN: ...{tampered_sn[-8:]}")

    try:
        r2 = requests.post(VERIFIER_URL, json=req2, timeout=REQUEST_TIMEOUT_SEC)
        print(f"HTTP Status: {r2.status_code}")
        print(f"Response: {r2.json() if r2.status_code == 200 else r2.text}")
    except Exception as e:
        print(f"Request failed: {e}")

    print("\n=== Test 3: Negative Path (Tampered Sigma) ===")
    print("Expected: HTTP 200, Decision: REJECTED")
    req3 = deepcopy(base_req)
    req3["request_id"] = str(uuid.uuid4())
    old_sigma = req3["ticket"]["sigma"]

    # 纯净的 Sigma 篡改：解码 -> 改最后一个字节 -> 重新编码，保证 Base64 格式绝对合法
    sig_bytes = bytearray(base64.b64decode(old_sigma))
    sig_bytes[-1] = (sig_bytes[-1] + 1) % 256
    tampered_sigma = base64.b64encode(sig_bytes).decode('utf-8')

    req3["ticket"]["sigma"] = tampered_sigma
    print(f"Tampered Sigma: ...{tampered_sigma[-10:]}")

    try:
        r3 = requests.post(VERIFIER_URL, json=req3, timeout=REQUEST_TIMEOUT_SEC)
        print(f"HTTP Status: {r3.status_code}")
        print(f"Response: {r3.json() if r3.status_code == 200 else r3.text}")
    except Exception as e:
        print(f"Request failed: {e}")


if __name__ == "__main__":
    run_tests()