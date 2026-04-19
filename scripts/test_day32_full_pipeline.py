# scripts/test_day32_full_pipeline.py
import sys
import requests
import hashlib
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket, create_bound_request

config = load_config()
v_cfg = config.get("verifier", {})
VERIFIER_URL = f"http://{v_cfg.get('host', '127.0.0.1')}:{v_cfg.get('port', 8002)}/api/v1/verifier/execute"


def run_day32_integration():
    print("🚀 === Day 32: Full Pipeline Integration (The Happy Path) ===\n")

    QUERY_STR = "user_777_request"
    DB_SIZE = 1024

    hash_bytes = hashlib.sha256(QUERY_STR.encode('utf-8')).digest()
    expected_index = int.from_bytes(hash_bytes, 'big') % DB_SIZE
    expected_val = expected_index * 101

    try:
        print(f"Step 1: Client acquiring ticket & creating binding for '{QUERY_STR}'...")
        ticket = acquire_ticket()
        bound_req = create_bound_request(ticket, QUERY_STR)

        print("Step 2: Submitting request to Verifier...")
        # 兼容性提示：若项目较老可换回 bound_req.dict()
        resp = requests.post(VERIFIER_URL, json=bound_req.model_dump(), timeout=20)

        # 建议 4 落地：增强 debug 打印
        print("\n--- Raw Verifier Response ---")
        print(f"Status Code: {resp.status_code}")
        try:
            payload = resp.json()
            print(f"Decision: {payload.get('decision')}")
            print(f"Reason: {payload.get('reason')}")
            print(f"Data: {payload.get('data')}")
        except Exception as e:
            print(f"Failed to parse JSON: {resp.text}")
            sys.exit(1)
        print("-----------------------------\n")

        assert resp.status_code == 200, f"HTTP Error: {resp.text}"
        assert payload.get("decision") == "SUCCESS", f"Decision REJECTED: {payload.get('reason')}"

        pir_data = payload.get("data")
        assert pir_data is not None, "Response data is None, expected dict!"

        actual_index = pir_data.get("mapped_index")
        actual_val = pir_data.get("recovered_val")

        print(f"[Verification Result]")
        print(f" - Mapped Index: {actual_index} (Expected: {expected_index})")
        print(f" - Recovered Val: {actual_val} (Expected: {expected_val})")

        assert actual_index == expected_index, "PIR Index Mismatch!"
        assert actual_val == expected_val, "PIR Recovered Value Mismatch!"

        print("\n✅ Day 32 Success: Full pipeline from Blind-Sign to SimplePIR is verified!")

    except Exception as e:
        print(f"\n❌ Integration Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_day32_integration()