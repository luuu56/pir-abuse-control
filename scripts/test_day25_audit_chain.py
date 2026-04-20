# scripts/test_day25_audit_chain.py
import sys
import json
import hmac
import hashlib
import time
import shutil
import requests
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket, create_bound_request

config = load_config()
auditor_cfg = config.get("auditor", {})
LEDGER_PATH = Path(auditor_cfg.get("ledger_path", "logs/audit_ledger.jsonl"))
AUDIT_SECRET_KEY = auditor_cfg.get("hmac_secret", "day25_default_key").encode("utf-8")
VERIFIER_URL = f"http://{config.get('verifier', {}).get('host', '127.0.0.1')}:8002/api/v1/verifier/execute"


def verify_integrity(path: Path):
    """验证指定账本文件的完整性"""
    if not path.exists():
        print(f"⚠️ 账本文件不存在: {path}")
        return True

    expected_prev = "0" * 64
    count = 0  # --- 修正 4: 补齐计数器 ---

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            count += 1
            record = json.loads(line.strip())

            if record["prev_hash"] != expected_prev:
                print(f"🚨 [链断裂] 行 {count}: prev_hash 不匹配")
                return False

            payload = f"{record['sn']}|{record['query_commitment']}|{record['decision']}|{record['timestamp_ms']}|{record['prev_hash']}"
            computed_mac = hmac.new(AUDIT_SECRET_KEY, payload.encode('utf-8'), hashlib.sha256).hexdigest()

            if computed_mac != record["entry_mac"]:
                print(f"🚨 [篡改发现] 行 {count}: entry_mac 校验失败")
                return False

            expected_prev = record["entry_mac"]

    if count == 0:
        print("⚠️ 审计账本为空")
    else:
        print(f"✅ 完整性验证通过 (共 {count} 条记录)")
    return True


def run_acceptance():
    print("🚀 === Day 25: Tamper-Evident Ledger Acceptance ===\n")

    # 1. 产生真实交易
    print("1️⃣ 构建正常审计链...")
    for _ in range(2):
        ticket = acquire_ticket()
        req = create_bound_request(ticket, "audit_test")
        # 必补 2: 增加 timeout，并显式检查响应状态，防范因环境没起好导致的误判
        resp = requests.post(VERIFIER_URL, json=req.model_dump(), timeout=10)
        resp.raise_for_status()

    time.sleep(0.5)

    # 2. 验证真实账本
    print("\n2️⃣ 验证真实账本...")
    assert verify_integrity(LEDGER_PATH) is True

    # 3. --- 修正 3: 模拟篡改 (使用副本) ---
    print("\n3️⃣ 在副本上模拟篡改攻击...")
    TAMPERED_PATH = LEDGER_PATH.with_name("audit_ledger_tampered.jsonl")
    shutil.copyfile(LEDGER_PATH, TAMPERED_PATH)

    with open(TAMPERED_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if lines:
        record = json.loads(lines[-1])
        record["decision"] = "SUCCESS" if record["decision"] != "SUCCESS" else "REJECTED"
        lines[-1] = json.dumps(record) + "\n"
        with open(TAMPERED_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"   -> 副本 {TAMPERED_PATH.name} 已被修改决策值")

    # 4. 再次验证
    print("\n4️⃣ 验证副本...")
    is_valid = verify_integrity(TAMPERED_PATH)
    assert is_valid is False, "❌ 审计链路未能发现副本中的篡改！"
    print("✅ 成功在副本中捕获篡改行为，真实账本保持完好。")

    # 清理副本
    if TAMPERED_PATH.exists(): TAMPERED_PATH.unlink()

    print("\n🎉 [PASS] Day 25 审计账本篡改留痕机制生效！")


if __name__ == "__main__":
    run_acceptance()