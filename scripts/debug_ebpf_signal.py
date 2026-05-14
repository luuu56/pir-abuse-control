# scripts/debug_ebpf_signal.py
import requests
import time
import sys
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

# 引入真正的发包逻辑
from services.client.main import acquire_ticket, create_bound_request

SERVER_IP = "119.45.48.193"  # 这里换成你的云服务器 IP
VERIFIER_URL = f"http://{SERVER_IP}:8002/api/v1/verifier/execute"


def trigger_l4_block():
    print(f"[*] 步骤 1: 正在申请真票并构造重放攻击...")
    try:
        t = acquire_ticket()
        req = create_bound_request(t, "debug_query")
        payload = req.model_dump(mode='json')

        # 第一发：让 Verifier 正常处理并标记为 CONSUMED
        print(f"    ➜ 发射第 1 发 (合法请求，消耗票据)...")
        resp1 = requests.post(VERIFIER_URL, json=payload, timeout=5)
        print(f"      响应: {resp1.status_code} | Decision: {resp1.json().get('decision', 'UNK')}")

        # 第二发：原样重放！这会触发 TicketState.CONSUMED 并拉响 eBPF 警报！
        print(f"    ➜ 发射第 2 发 (恶意重放，触发 eBPF 下发)...")
        resp2 = requests.post(VERIFIER_URL, json=payload, timeout=5)
        print(f"      响应: {resp2.status_code} | Reason: {resp2.json().get('reason', 'UNK')}")

    except Exception as e:
        print(f"    [!] 触发失败: {e}")


def test_l4_connectivity():
    print(f"\n[*] 步骤 2: 正在验证 L4 联通性 (看 eBPF 是否已接管)...")
    try:
        start = time.perf_counter()
        resp = requests.get(f"http://{SERVER_IP}:8002/api/v1/verifier/metrics", timeout=2)
        elapsed = time.perf_counter() - start
        print(f"    \033[91m[失败]\033[0m 请求竟然成功穿透了！耗时: {elapsed:.2f}s")
        return False
    except requests.exceptions.Timeout:
        print(f"    \033[92m[成功]\033[0m 检测到超时！eBPF 正在 DROP 你的包。")
        return True
    except requests.exceptions.ConnectionError:
        print(f"    \033[92m[成功]\033[0m 连接被拒绝/重置！eBPF 铁幕已落下。")
        return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        SERVER_IP = sys.argv[1]

    print(f"=== eBPF 联动快速调试工具 (真票重放版) ===")
    trigger_l4_block()

    print(f"\n[*] 等待 1.5 秒让信号下发至内核...")
    time.sleep(1.5)

    is_blocked = test_l4_connectivity()

    if is_blocked:
        print(f"\n\033[92m[结论] 完美！eBPF 联动逻辑验证通过！可以去跑大规模压测了！\033[0m")
    else:
        print(f"\n\033[91m[结论] 联动依然未生效，请检查 Verifier 终端是否印出了 [UDP 派发成功]\033[0m")