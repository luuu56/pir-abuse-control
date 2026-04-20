# scripts/test_day31_dynamic_mapping.py
import requests
import hashlib
import sys

PIR_URL = "http://127.0.0.1:8003/api/v1/pir/query"
DB_SIZE = 1024

test_cases = ["query_apple", "query_banana", "user_12345"]
success_count = 0

print("=== Starting Day 31 Dynamic Mapping Test ===")

for q in test_cases:
    hash_bytes = hashlib.sha256(q.encode('utf-8')).digest()
    expected_index = int.from_bytes(hash_bytes, byteorder='big') % DB_SIZE
    expected_val = expected_index * 101

    print(f"\n[Test] q='{q}'")
    print(f" -> Expected Index: {expected_index}")

    resp = requests.post(PIR_URL, json={"query_payload": q})

    if resp.status_code != 200:
        print(f"❌ HTTP Failed: {resp.status_code} - {resp.text}")
        sys.exit(1)

    data = resp.json()
    mapped_index = data.get("mapped_index")
    recovered_val = data.get("recovered_val")

    assert mapped_index == expected_index, f"Index mismatch! Expected {expected_index}, got {mapped_index}"
    assert recovered_val == expected_val, f"Value mismatch! Expected {expected_val}, got {recovered_val}"

    print(f"✅ Pass: Index mapped to {mapped_index}, recovered crypto value {recovered_val}")
    success_count += 1

print(f"\n=== Test Complete: {success_count}/{len(test_cases)} Passed ===")