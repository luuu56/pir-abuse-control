# scripts/test_day29_go_wrapper.py
import requests

PIR_URL = "http://127.0.0.1:8003/api/v1/pir/query"

def run_wrapper_acceptance():
    print("🚀 === Day 29 (中): 真实 Go Wrapper 二进制边界接入验收 ===\n")

    # 1. 正常交互测试
    print("1️⃣ 测试正常唤起与 JSON 交互...")
    resp = requests.post(PIR_URL, json={"query_payload": "day29_payload"})
    assert resp.status_code == 200
    assert "[REAL_GO_WRAPPER]" in resp.json()["data"]
    print("   ✅ 结果: 真实 Go 二进制成功执行并返回成功 JSON。\n")

    # 2. 崩溃隔离测试 (Exit 139)
    print("2️⃣ 测试进程崩溃隔离 (EngineProcessError)...")
    resp = requests.post(PIR_URL, json={"query_payload": "fatal_crash_test"})
    assert resp.status_code == 500
    print("   ✅ 结果: Go 进程段错误被隔离，Python 正确映射为 500。\n")

    # 3. 脏数据协议测试 (Invalid JSON)
    print("3️⃣ 测试协议异常拦截 (EngineProtocolError)...")
    resp = requests.post(PIR_URL, json={"query_payload": "bad_json_test"})
    assert resp.status_code == 502
    print("   ✅ 结果: Go 吐出非 JSON 字符被拦截，Python 正确映射为 502。\n")

    # 4. 业务逻辑错误测试 (Status: Error)
    print("4️⃣ 测试业务逻辑报错 (EngineResponseError)...")
    resp = requests.post(PIR_URL, json={"query_payload": "status_error_test"})
    assert resp.status_code == 500
    print("   ✅ 结果: Go 返回 status=error JSON，Python 正确识别逻辑失败并映射为 500。\n")

    print("🎉 [PASS] Day 29 (中) 完成：跨语言二进制边界及其四类异常路径全部闭环！")

if __name__ == "__main__":
    run_wrapper_acceptance()