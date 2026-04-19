# scripts/test_day29_bridge_mock.py
import requests

PIR_URL = "http://127.0.0.1:8003/api/v1/pir/query"

def run_adapter_acceptance():
    print("🚀 === Day 29 (上): Adapter 层 JSON 进程桥接验收 ===\n")

    # 1. 正常交互
    resp = requests.post(PIR_URL, json={"query_payload": "day29_payload"})
    assert resp.status_code == 200
    assert "[EXTERNAL_PIR_ENGINE]" in resp.json()["data"]
    print("✅ JSON stdin/stdout 协议桥接成功！")

    # 2. 崩溃隔离 (返回 500)
    resp = requests.post(PIR_URL, json={"query_payload": "fatal_crash_test"})
    assert resp.status_code == 500
    print("✅ 外部引擎崩溃（段错误）被隔离，映射为 HTTP 500")

    # 3. 协议失败 (返回 502)
    resp = requests.post(PIR_URL, json={"query_payload": "bad_json_test"})
    assert resp.status_code == 502
    print("✅ 外部引擎脏数据输出被识别，映射为 HTTP 502")

    print("\n🎉 [PASS] Day 29 (上) 薄适配器层与 JSON 协议收口完成！")
    print("⚠️  待办: 真实主候选 PIR demo 验收需在获得真实引擎二进制后切换 YAML 配置执行。")

if __name__ == "__main__":
    run_adapter_acceptance()