# scripts/test_day11_binding.py
import sys
import requests
from copy import deepcopy
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket, create_bound_request

config = load_config()
verifier_cfg = config.get("verifier", {})
VERIFIER_URL = f"http://{verifier_cfg.get('host', '127.0.0.1')}:{verifier_cfg.get('port', 8002)}/api/v1/verifier/execute"
REQUEST_TIMEOUT_SEC = 5

def run_tests():
    print("=== Step 1: Acquiring and Binding Ticket ===")
    try:
        ticket = acquire_ticket()
        req_obj = create_bound_request(ticket, "original_clean_query")
        base_req = req_obj.model_dump()
    except Exception as e:
        print(f"Failed to setup: {e}")
        return

    def send_and_verify(test_name, payload, expected_decision):
        print(f"\n=== {test_name} ===")
        print(f"Expected: {expected_decision}")
        try:
            r = requests.post(VERIFIER_URL, json=payload, timeout=REQUEST_TIMEOUT_SEC)
            print(f"HTTP Status: {r.status_code}")
            resp_json = r.json() if r.status_code == 200 else r.text
            print(f"Response: {resp_json}")
            if r.status_code == 200 and resp_json.get("decision") != expected_decision:
                print(">>> ❌ TEST FAILED: Unexpected decision!")
            elif r.status_code == 200:
                print(">>> ✅ TEST PASSED")
        except Exception as e:
            print(f"Request failed: {e}")

    # Test 1: 合法 Binding 通过
    send_and_verify("Test 1: Happy Path (Valid Binding)", base_req, "SUCCESS")

    # Test 2: 篡改 query_payload 被拒绝
    req2 = deepcopy(base_req)
    req2["query_payload"] = "malicious_injected_query"
    send_and_verify("Test 2: Tampered Query Payload", req2, "REJECTED")

    # Test 3: 篡改 witness 被拒绝
    req3 = deepcopy(base_req)
    req3["witness"]["timestamp_ms"] = req3["witness"]["timestamp_ms"] - 10000
    send_and_verify("Test 3: Tampered Witness (Timestamp)", req3, "REJECTED")

    # Test 4: 篡改 binding_tag 被拒绝
    req4 = deepcopy(base_req)
    # 改动 tag 的最后一位
    tag = req4["binding_tag"]
    req4["binding_tag"] = tag[:-1] + ('a' if tag[-1] != 'a' else 'b')
    send_and_verify("Test 4: Tampered Binding Tag", req4, "REJECTED")

if __name__ == "__main__":
    run_tests()