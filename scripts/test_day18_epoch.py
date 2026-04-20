# scripts/test_day18_epoch.py
import sys
import time
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from services.client.main import acquire_ticket, create_bound_request
import requests


def test_epoch_expiration():
    print("🚀 === Day 18: Epoch Expiration Test ===")

    # 1. 正常流程：拿到当前纪元的票据
    print("Step 1: Acquiring a fresh ticket...")
    ticket = acquire_ticket()
    print(f"✅ Acquired ticket for Epoch: {ticket.epoch_id}")

    # 2. 模拟过期：篡改 Ticket 的 EpochID 模拟一个显著过期的纪元
    print("\nStep 2: Simulating a clearly expired ticket...")
    expired_ticket = ticket.model_copy()
    # 强制设为两个纪元之前，确保无论是否在宽限期都会被拒
    expired_ticket.epoch_id = ticket.epoch_id - 2

    bound_req = create_bound_request(expired_ticket, "expired_test_payload")

    # 3. 发送给 Verifier
    print(f"Sending expired ticket to Verifier...")
    v_url = "http://127.0.0.1:8002/api/v1/verifier/execute"
    resp = requests.post(v_url, json=bound_req.model_dump())

    print(f"Status Code: {resp.status_code}")
    result = resp.json()
    print(f"Decision: {result.get('decision')}")
    print(f"Reason: {result.get('reason')}")

    if result.get('decision') == "REJECTED" and "expired" in result.get('reason').lower():
        print("\n🎉 [PASS] Expired ticket was successfully rejected by Verifier!")
    else:
        print("\n❌ [FAIL] Verifier accepted or wrongly handled the expired ticket.")


if __name__ == "__main__":
    test_epoch_expiration()