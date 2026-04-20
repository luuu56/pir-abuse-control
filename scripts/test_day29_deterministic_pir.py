# scripts/test_day29_deterministic_pir.py
import sys
import requests

PIR_URL = "http://127.0.0.1:8003/api/v1/pir/query"


def run_deterministic_acceptance():
    print("🚀 === Day 29 (下-2): 确定性 PIR 核心计算红线基线 ===\n")
    print("⚠️  [诚实基线声明]")
    print("   在真实 SimplePIR 核心未接入 Go wrapper 之前，本脚本【预期必定失败】。")
    print("   本脚本用于严防 Placeholder 假阳性。只有底层实现『固定小 DB + 查索引 42 -> 确定性解密出 4242』后，方可通过。\n")

    test_index = "42"
    expected_value = "4242"

    print(f"📡 发起确定性 PIR 查询 (Index: {test_index})...")
    resp = requests.post(PIR_URL, json={"query_payload": test_index})

    assert resp.status_code == 200, f"引擎调用失败，状态码: {resp.status_code}, {resp.text}"
    result_data = resp.json()["data"]

    # 建议 4：硬断言，失败即抛出 AssertionError 退出进程，符合 CI 规范
    assert expected_value in result_data, (
        f"\n❌ [红线拦截] 未在引擎返回中找到确定的解密真值!\n"
        f"   期望值包含: {expected_value}\n"
        f"   实际返回为: {result_data}\n"
        f"   结论: 真实 SimplePIR 核心库尚未被正确调用。"
    )

    print(f"✅ 成功穿透 Python 适配器，真实密码学计算链路已验证！")
    print(f"📦 引擎精确还原了隐藏数据: {result_data}\n")
    print("🎉 [PASS] Day 29 终极目标大满贯达成！真实主候选核心计算完全闭环！")


if __name__ == "__main__":
    run_deterministic_acceptance()