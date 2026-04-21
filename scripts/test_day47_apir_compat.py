# scripts/test_day47_apir_optional.py
import sys
import requests
from pathlib import Path

# 确保能加载 common 包
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket, create_bound_request


def run_apir_optional_smoke_test():
    config = load_config()
    verifier_cfg = config.get("verifier", {})
    verifier_url = f"http://{verifier_cfg.get('host', '127.0.0.1')}:{verifier_cfg.get('port', 8002)}/api/v1/verifier/execute"

    print("=" * 60)
    print("🛡️ Day 47: Proof 缺失时的架构向下兼容性测试 (Smoke Test) 🛡️")
    print("=" * 60 + "\n")

    # 注意：这里使用普通 payload，不触发后端生成 proof
    print("1️⃣ 客户端构建普通请求 (不期望 APIR 证明)...")
    ticket = acquire_ticket()
    req = create_bound_request(ticket, "standard_query_payload_999")

    print("2️⃣ 提交请求并穿透 Verifier...")
    resp = requests.post(verifier_url, json=req.model_dump(mode='json'), timeout=10)
    resp.raise_for_status()

    data = resp.json()
    payload = data.get("data", {})

    apir_proof = payload.get("apir_proof")
    recovered_val = payload.get("recovered_val")

    print(f"\n3️⃣ 客户端解析响应...")
    print(f"   ➜ 恢复数值: {recovered_val}")
    print(f"   ➜ 收到证明: {apir_proof}")

    # 核心断言：没有 proof，但也成功拿到了核心结果
    if apir_proof is None and recovered_val is not None:
        print("\n[✅ PASSED] 核心结构字段解析成功，且 Optional Proof 平滑缺失。")
        print("   结论：主链逻辑未被 Proof 字段绑死，Verifier 完美遵守了向下兼容与松耦合契约！")
    else:
        print("\n[❌ FAILED] 期望 proof 为 None 且核心数据存在，但断言失败。")


if __name__ == "__main__":
    try:
        run_apir_optional_smoke_test()
    except Exception as e:
        print(f"执行异常: {e}")