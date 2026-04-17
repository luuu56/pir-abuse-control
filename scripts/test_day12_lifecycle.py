# scripts/test_day12_lifecycle.py
import sys
import requests
import time
import threading
from copy import deepcopy
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket, create_bound_request

# --- 统一配置加载 ---
config = load_config()
verifier_cfg = config.get("verifier", {})
VERIFIER_URL = f"http://{verifier_cfg.get('host', '127.0.0.1')}:{verifier_cfg.get('port', 8002)}/api/v1/verifier/execute"

# 第一刀：Timeout 也收归配置管理 (默认 5 秒)
REQUEST_TIMEOUT_SEC = config.get("client", {}).get("timeout", 5)
CONCURRENCY_DELAY_SEC = 0.2


def run_tests():
    print("=== Step 0: Preparing Tickets for Multiple Scenarios ===")
    t1 = acquire_ticket()
    t2 = acquire_ticket()
    t3 = acquire_ticket()
    t4 = acquire_ticket()

    # --- 场景 1: PENDING 分支验证 (并发冲突) ---
    print("\n=== Test 1: PENDING Branch (Concurrency Test) ===")
    req1_base = create_bound_request(t1, "slow_query").model_dump()
    req1_dup = deepcopy(req1_base)
    req1_dup["request_id"] = "concurrent-hacker-id"

    # 第二刀：带标签的线程安全结果收集
    results = {}

    def send_req(tag_name, payload):
        try:
            r = requests.post(VERIFIER_URL, json=payload, timeout=REQUEST_TIMEOUT_SEC)
            results[tag_name] = r.json()
        except Exception as e:
            print(f"Request error [{tag_name}]: {e}")

    thread1 = threading.Thread(target=send_req, args=("Req_A (First)", req1_base))
    thread2 = threading.Thread(target=send_req, args=("Req_B (Delayed)", req1_dup))

    thread1.start()
    time.sleep(CONCURRENCY_DELAY_SEC)
    thread2.start()

    thread1.join()
    thread2.join()

    # 【硬断言】
    assert len(results) == 2, "Test 1 Failed: Expected exactly 2 responses"

    # 动态分析谁赢谁输
    winner_tag = next((tag for tag, res in results.items() if res.get("decision") == "SUCCESS"), None)
    loser_tag = next((tag for tag, res in results.items() if res.get("decision") == "REJECTED"), None)

    assert winner_tag and loser_tag, f"Test 1 Failed: Expected 1 SUCCESS and 1 REJECTED. Got: {results}"
    assert results[loser_tag].get(
        "ticket_state") == "PENDING", f"Test 1 Failed: Loser ticket state must be PENDING, got {results[loser_tag].get('ticket_state')}"

    print(f">>> ✅ TEST 1 PASSED: Strict concurrency blocked. Winner: {winner_tag}, Loser (PENDING): {loser_tag}")

    # --- 场景 2: FAILED 分支验证 (异常烧毁) ---
    print("\n=== Test 2: FAILED Branch (Burn-on-Failure Test) ===")
    req2 = create_bound_request(t2, "trigger_failure_test").model_dump()

    r2_1 = requests.post(VERIFIER_URL, json=req2, timeout=REQUEST_TIMEOUT_SEC).json()
    r2_2 = requests.post(VERIFIER_URL, json=req2, timeout=REQUEST_TIMEOUT_SEC).json()

    # 【硬断言】
    assert r2_1.get("decision") == "REJECTED", "Test 2 Failed: First request must fail"
    assert r2_1.get("ticket_state") == "FAILED", "Test 2 Failed: First request must burn ticket to FAILED"
    assert r2_2.get("decision") == "REJECTED", "Test 2 Failed: Second request must be rejected"
    assert "already FAILED" in r2_2.get("reason"), "Test 2 Failed: Incorrect reject reason for burned ticket"
    print(">>> ✅ TEST 2 PASSED: Ticket strictly burned on execution failure.")

    # --- 场景 3: 正常的 CONSUMED 验证 (Happy Path) ---
    print("\n=== Test 3: CONSUMED Branch (Happy Path) ===")
    req3 = create_bound_request(t3, "normal_query").model_dump()

    r3_1 = requests.post(VERIFIER_URL, json=req3, timeout=REQUEST_TIMEOUT_SEC).json()
    r3_2 = requests.post(VERIFIER_URL, json=req3, timeout=REQUEST_TIMEOUT_SEC).json()

    # 【硬断言】
    assert r3_1.get("decision") == "SUCCESS", "Test 3 Failed: First request must succeed"
    assert r3_1.get("ticket_state") == "CONSUMED", "Test 3 Failed: First request must reach CONSUMED"
    assert r3_2.get("decision") == "REJECTED", "Test 3 Failed: Replay must be rejected"
    assert r3_2.get("ticket_state") == "CONSUMED", "Test 3 Failed: Replay must show CONSUMED state"
    print(">>> ✅ TEST 3 PASSED: Happy path consumed ticket and blocked subsequent replays.")

    # --- 场景 4: 边界用例 - 验证失败不吞票 (Day 11 & Day 12 联动) ---
    print("\n=== Test 4: Boundary Branch (Validation Failure Preserves Ticket) ===")
    req4_valid = create_bound_request(t4, "boundary_query").model_dump()
    req4_tampered = deepcopy(req4_valid)

    # 破坏 Binding Tag
    tag = req4_tampered["binding_tag"]
    req4_tampered["binding_tag"] = tag[:-1] + ('a' if tag[-1] != 'a' else 'b')

    r4_tampered = requests.post(VERIFIER_URL, json=req4_tampered, timeout=REQUEST_TIMEOUT_SEC).json()
    # 【硬断言】篡改请求被拒，且票据状态应维持 UNUSED（未被推入 PENDING）
    assert r4_tampered.get("decision") == "REJECTED", "Test 4 Failed: Tampered request must be rejected"
    assert r4_tampered.get(
        "ticket_state") == "UNUSED", f"Test 4 Failed: State should be UNUSED, got {r4_tampered.get('ticket_state')}"

    r4_valid = requests.post(VERIFIER_URL, json=req4_valid, timeout=REQUEST_TIMEOUT_SEC).json()
    assert r4_valid.get(
        "decision") == "SUCCESS", "Test 4 Failed: Valid request should succeed since ticket was not burned"
    assert r4_valid.get("ticket_state") == "CONSUMED", "Test 4 Failed: Ticket should now be CONSUMED"
    assert "Binding Consistency Check Failed" in r4_tampered.get("reason")
    print(">>> ✅ TEST 4 PASSED: Validation failure did not burn ticket; subsequent valid request succeeded.")

    print("\n🎉 ALL LIFECYCLE TESTS PASSED SUCCESSFULLY! 🎉")


if __name__ == "__main__":
    run_tests()