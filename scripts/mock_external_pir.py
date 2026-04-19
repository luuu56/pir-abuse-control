# scripts/mock_external_pir.py
import sys
import json
import time


def main():
    try:
        input_data = sys.stdin.read()
        req = json.loads(input_data)
        # 兼容当前 payload，同时为 Day 31 预留 pir_input 字段
        query_payload = req.get("query_payload", "")
        pir_input = req.get("pir_input", query_payload)
    except Exception as e:
        print(json.dumps({
            "status": "error", "error_type": "protocol_error",
            "error_message": f"Invalid JSON input: {e}", "engine_meta": {}
        }))
        sys.exit(1)

    time.sleep(0.2)

    if query_payload == "fatal_crash_test":
        print("Segmentation fault (core dumped) in C++ PIR backend", file=sys.stderr)
        sys.exit(139)

    if query_payload == "bad_json_test":
        print("This is not a valid JSON output!", file=sys.stdout)
        sys.exit(0)

    # 标准化、具备元数据的成功输出
    resp = {
        "status": "success",
        "result": f"[EXTERNAL_PIR_ENGINE] Processed input: {pir_input}",
        "error_type": None,
        "error_message": None,
        "engine_meta": {"mock_version": "1.0", "processed_bytes": len(pir_input)}
    }
    print(json.dumps(resp))
    sys.exit(0)


if __name__ == "__main__":
    main()