# scripts/test_day17_full_e2e.py
import sys
import requests
from pathlib import Path

# 将根目录加入 sys.path
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.logging_utils import setup_logger
from services.client.main import acquire_ticket, create_bound_request

# --- 1. 初始化配置与环境参数 ---
config = load_config()
logger = setup_logger("e2e_test", config)

# 动态提取各服务配置项，用于 URL 构造及错误提示
issuer_cfg = config.get("issuer", {})
verifier_cfg = config.get("verifier", {})
pir_cfg = config.get("pir_server", {})  # 适配层配置
client_cfg = config.get("client", {})

I_PORT = issuer_cfg.get("port", 8001)
V_PORT = verifier_cfg.get("port", 8002)
P_PORT = pir_cfg.get("port", 8003)

VERIFIER_URL = f"http://{verifier_cfg.get('host', '127.0.0.1')}:{V_PORT}/api/v1/verifier/execute"
REQUEST_TIMEOUT_SEC = client_cfg.get("timeout", 10)


def run_full_e2e():
    """
    Day 17+ 全链路烟雾测试 (Smoke Test)
    验证：Client -> Admission -> Issuer -> Binding -> Verifier -> PIR Server
    """
    print("\n" + "=" * 50)
    print("🚀 DAY 17+ FULL E2E SMOKE TEST")
    print("=" * 50 + "\n")

    try:
        # 1. 拿票 (Admission 核心协议流)
        print(">>> Phase 1: Ticket Acquisition (PoW + Blind Sign)")
        ticket = acquire_ticket()
        print(f"✅ Ticket obtained. SN: {ticket.sn[:16]}...\n")

        # 2. 绑定载荷
        print(">>> Phase 2: Payload Binding")
        payload = "grand_e2e_test_query_payload"
        bound_req = create_bound_request(ticket, payload)
        print(f"✅ Request bound locally.\n")

        # 3. 发送给 Verifier
        print(">>> Phase 3: Verifier Execution & PIR Bridge")
        print(f"⏳ Sending to Verifier: {VERIFIER_URL}")

        resp = requests.post(
            VERIFIER_URL,
            json=bound_req.model_dump(),
            timeout=REQUEST_TIMEOUT_SEC
        )

        # 4. 响应分发处理
        if resp.status_code == 200:
            result = resp.json()
            decision = result.get("decision")
            if decision == "SUCCESS":
                print(f"✅ PIR SUCCESS: Data received ({len(str(result.get('data')))} bytes)")
                # 补：输出成功原因（如 "PIR execution completed"）
                print(f"Reason: {result.get('reason')}")
                print("\n🎉 [PASS] Full End-to-End Flow is Functional!")
            else:
                print(f"⚠️  BUSINESS REJECT: Decision={decision}, Reason={result.get('reason')}")
                print("❌ [FAIL] Flow reached Verifier but was rejected.")

        elif resp.status_code == 403:
            print(f"❌ [FAIL] Forbidden (403): Verify failed (Ticket reuse, Binding mismatch, or Expired).")
            print(f"Detail: {resp.text}")

        elif resp.status_code == 422:
            print(f"❌ [FAIL] Data Error (422): Pydantic validation failed.")
            print(f"Detail: {resp.text}")

        elif resp.status_code >= 500:
            print(f"❌ [FAIL] Internal Error (5xx): PIR Bridge failed or Verifier crashed.")
            print(f"Detail: {resp.text}")

        # 补：处理其他非预期 HTTP 状态码
        else:
            print(f"❌ [FAIL] Unexpected HTTP Status: {resp.status_code}")
            print(f"Detail: {resp.text}")

    except requests.exceptions.Timeout:
        print(f"❌ [FAIL] Request Timed Out (Limit: {REQUEST_TIMEOUT_SEC}s).")

    except requests.exceptions.ConnectionError:
        # 补：基于配置动态构造连接错误提示
        print(f"❌ [FAIL] Connection Refused.")
        print(f"👉 Please ensure Issuer({I_PORT}), Verifier({V_PORT}), and PIR({P_PORT}) are ALL running.")

    except Exception as e:
        print(f"❌ [FAIL] Unexpected Exception: {e}")


if __name__ == "__main__":
    run_full_e2e()