# scripts/test_day16_admission.py
import sys
import time
import requests
from pathlib import Path

# 将根目录加入 sys.path 以便复用 common 模块
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.crypto_utils import canonical_json_bytes, solve_pow

ISSUER_URL = "http://127.0.0.1:8001/api/v1/issuer"
CLIENT_TAG = "day16_test_client"
DUMMY_BLINDED_MSG = "1a2b"  # 随便一个合法的 hex 字符串过 Pydantic


def test_1_no_admission_proof():
    print("--- Test 1: No admission proof -> Should Fail ---")
    payload = {"blinded_message": DUMMY_BLINDED_MSG}
    resp = requests.post(f"{ISSUER_URL}/issue", json=payload)
    print(f"Status: {resp.status_code}")
    assert resp.status_code == 422, "Expected 422 Unprocessable Entity due to missing Pydantic field"
    print("✅ Passed: Cannot issue ticket without admission proof.\n")


def test_2_forged_hmac():
    print("--- Test 2: Forged HMAC -> Should Fail ---")
    # 1. 拿真实的 Challenge
    resp = requests.post(f"{ISSUER_URL}/challenge", json={"client_tag": CLIENT_TAG})
    challenge_data = resp.json()

    # 2. 篡改 HMAC 签名
    proof = {
        "challenge": {
            "payload": challenge_data["payload"],
            "hmac_sig": "0" * 64  # 伪造的 HMAC
        },
        "nonce": 0
    }

    verify_resp = requests.post(f"{ISSUER_URL}/verify_admission", json=proof)
    print(f"Status: {verify_resp.status_code}, Response: {verify_resp.text}")
    assert verify_resp.status_code == 403
    assert "signature mismatch" in verify_resp.text.lower()
    print("✅ Passed: Forged HMAC rejected.\n")


def test_3_invalid_pow():
    print("--- Test 3: Invalid PoW Nonce -> Should Fail ---")
    resp = requests.post(f"{ISSUER_URL}/challenge", json={"client_tag": CLIENT_TAG})
    challenge_data = resp.json()

    # 使用肯定错误的 nonce (这里用 0 可能会碰巧对，但概率极低，用最大值做反例)
    proof = {
        "challenge": challenge_data,
        "nonce": (2 ** 64) - 1
    }

    verify_resp = requests.post(f"{ISSUER_URL}/verify_admission", json=proof)
    print(f"Status: {verify_resp.status_code}, Response: {verify_resp.text}")
    assert verify_resp.status_code == 403
    assert "insufficient work" in verify_resp.text.lower()
    print("✅ Passed: Invalid PoW nonce rejected.\n")


def test_4_replay_attack():
    print("--- Test 4: Replay Attack (Burn Semantics) -> Should Fail on 2nd try ---")
    # 1. 获取合法 Challenge
    resp = requests.post(f"{ISSUER_URL}/challenge", json={"client_tag": CLIENT_TAG})
    challenge_data = resp.json()

    # 2. 本地求解 PoW
    payload_dict = challenge_data["payload"]
    payload_bytes = canonical_json_bytes(payload_dict)
    hmac_sig = challenge_data["hmac_sig"]
    difficulty = payload_dict["difficulty"]

    print(f"Solving PoW (difficulty: {difficulty})...")
    nonce = solve_pow(payload_bytes, hmac_sig, difficulty)

    issue_payload = {
        "blinded_message": DUMMY_BLINDED_MSG,
        "admission_proof": {
            "challenge": challenge_data,
            "nonce": nonce
        }
    }

    # 3. 第一次请求 /issue (预期成功)
    resp1 = requests.post(f"{ISSUER_URL}/issue", json=issue_payload)
    print(f"1st Request Status: {resp1.status_code}")
    assert resp1.status_code == 200, f"Expected 200 OK, got {resp1.text}"

    # 4. 第二次复用同一个 Challenge 请求 /issue (预期被拦截)
    resp2 = requests.post(f"{ISSUER_URL}/issue", json=issue_payload)
    print(f"2nd Request Status: {resp2.status_code}, Response: {resp2.text}")
    assert resp2.status_code == 403
    assert "consumed" in resp2.text.lower() or "replayed" in resp2.text.lower()
    print("✅ Passed: Replay attack successfully blocked by Redis burn semantics.\n")


if __name__ == "__main__":
    try:
        test_1_no_admission_proof()
        test_2_forged_hmac()
        test_3_invalid_pow()
        test_4_replay_attack()
        print("🎉 All Day 16 Admission Logic Tests Passed!")
    except AssertionError as e:
        print(f"❌ Test Failed: {e}")