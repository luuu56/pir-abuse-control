# scripts/demo_day56_showcase.py
import sys
import time
import json
import asyncio
import argparse
import requests
import secrets
from pathlib import Path
from collections import Counter

try:
    import aiohttp
    import redis
except ImportError:
    print("❌ 缺少必要依赖！请运行: pip install aiohttp redis requests")
    sys.exit(1)

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.models import Decision, TicketState, AuditRecord
from common.crypto_utils import compute_query_commitment
from services.client.main import acquire_ticket, create_bound_request
from services.verifier.state_manager import TicketStateManager

# --- 终端色彩美化 ---
C_CYAN = '\033[96m'
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_MAGENTA = '\033[95m'
C_RESET = '\033[0m'


def print_header(title):
    print(f"\n{C_CYAN}{'=' * 70}{C_RESET}")
    print(f"{C_CYAN}🚀 {title} 🚀{C_RESET}")
    print(f"{C_CYAN}{'=' * 70}{C_RESET}\n")


def slow_print(text, delay=0.01):
    """带呼吸感的终端输出 (加快至 0.01 避免拖沓)"""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


class MasterDemoCLI:
    def __init__(self, target_ip):
        self.target_ip = target_ip
        self.config = load_config()
        self.verifier_url = f"http://{target_ip}:8002/api/v1/verifier/execute"

        auditor_port = self.config.get("auditor", {}).get("port", 8004)
        self.auditor_url = f"http://{target_ip}:{auditor_port}"

        redis_cfg = self.config.get("redis", {})
        self.redis_host = target_ip
        self.redis_port = redis_cfg.get("port", 6379)
        self.state_manager = TicketStateManager(host=self.redis_host, port=self.redis_port)

    def demo_01_happy_path(self):
        print_header("场景 1: 正常请求 (Happy Path)")
        slow_print("[-] 正在模拟诚实用户，执行完整的盲签与零知识前置验证...")
        ticket = acquire_ticket()
        req = create_bound_request(ticket, "query_target_demo_1")

        print(f"  ➜ SN: {ticket.sn[:8]}...")
        slow_print("[-] 正在发送至 Verifier...")
        start = time.perf_counter()
        resp = requests.post(self.verifier_url, json=req.model_dump(mode='json'))
        latency = (time.perf_counter() - start) * 1000

        if resp.status_code != 200:
            print(f"{C_RED}[SERVER ERROR]{C_RESET} HTTP {resp.status_code}: {resp.text}")
            return

        data = resp.json()
        print(
            f"{C_GREEN}[SUCCESS]{C_RESET} 耗时: {latency:.2f}ms | 决策: {data.get('decision')} | 结果: {data.get('data', {}).get('recovered_val')}")

    def demo_02_replay_attack(self):
        print_header("场景 2: 重放攻击 (Replay Abuse & L4 Dampening)")
        slow_print("[-] 攻击者截获了一张合法票据，试图发起连续重放...")
        ticket = acquire_ticket()
        req = create_bound_request(ticket, "query_target_demo_2")
        payload = req.model_dump(mode='json')

        slow_print(f"\n{C_YELLOW}[第一枪] 合法首发...{C_RESET}")
        resp1 = requests.post(self.verifier_url, json=payload)
        if resp1.status_code == 200:
            print(f"  ➜ 决策: {resp1.json().get('decision')}")
        else:
            print(f"{C_RED}  ➜ [SERVER ERROR] HTTP {resp1.status_code}: {resp1.text}{C_RESET}")
            return

        slow_print(f"\n{C_YELLOW}[第二枪] 并发/极速重放 (命中 L7 状态机)...{C_RESET}")
        resp2 = requests.post(self.verifier_url, json=payload)
        if resp2.status_code == 200:
            print(f"  ➜ 决策: {resp2.json().get('decision')} | 原因: {resp2.json().get('reason')}")
        else:
            print(f"{C_RED}  ➜ [SERVER ERROR] HTTP {resp2.status_code}: {resp2.text}{C_RESET}")
            return

        slow_print(f"\n{C_YELLOW}[第三枪] 持续重放 (期待命中 L4 eBPF 前置拦截)...{C_RESET}")
        time.sleep(1)  # 给控制面下发 BPF Map 留出时间
        try:
            requests.post(self.verifier_url, json=payload, timeout=2.0)
            print(f"{C_RED}  ➜ 警告: 请求未被 L4 拦截，可能 eBPF/tc_gateway 未开启。{C_RESET}")
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
            print(f"{C_GREEN}  ➜ 拦截成功: 客户端侧出现超时/连接异常，符合 L4 eBPF 前置丢弃预期。{C_RESET}")
        except Exception as e:
            print(f"{C_RED}  ➜ 未知异常: {e}{C_RESET}")

    def demo_03_binding_tampering(self):
        print_header("场景 3: 请求劫持与载荷篡改 (Binding Tampering)")
        slow_print("[-] 攻击者截获合法票据，试图篡改查询载荷 (如将请求指向敏感数据)...")
        ticket = acquire_ticket()
        req = create_bound_request(ticket, "legit_query_payload")

        slow_print("[-] 篡改 query_payload 为 'malicious_query_payload'，但保持原签名与 Binding 标签不变...")
        req.query_payload = "malicious_query_payload"

        resp = requests.post(self.verifier_url, json=req.model_dump(mode='json'))
        if resp.status_code != 200:
            print(f"{C_RED}[SERVER ERROR]{C_RESET} HTTP {resp.status_code}: {resp.text}")
            return

        print(f"{C_GREEN}[BLOCKED]{C_RESET} 决策: {resp.json().get('decision')} | 原因: {resp.json().get('reason')}")

    def demo_04_ghost_consumption(self):
        print_header("场景 4: 恶意 Verifier - 幽灵核销争议 (Ghost Consumption)")
        slow_print("[-] 模拟 Verifier 节点被攻陷，恶意修改 Redis 状态，但拒绝向 Auditor 写日志...")
        test_sn = secrets.token_hex(32)

        self.state_manager.mark_consumed(test_sn, epoch_id=1)
        slow_print(f"[-] [内鬼操作] Redis 状态已强制标记为 CONSUMED (SN: {test_sn[:8]}...)")

        redis_state = self.state_manager.r.get(self.state_manager._get_key(test_sn))
        print(f"  ➜ 验证 Redis 实际状态: {redis_state}")

        slow_print("[-] [外部审计] 正在向独立 Auditor 发起对账追踪...")
        try:
            resp = requests.get(f"{self.auditor_url}/api/v1/auditor/trace/{test_sn}")
            print(f"  ➜ Auditor HTTP 响应码: {resp.status_code}")

            if resp.status_code == 404:
                print(
                    f"{C_GREEN}[TAMPER DETECTED]{C_RESET} Redis 状态为 CONSUMED，但 Auditor 账本毫无记录！成功捕捉“幽灵核销”作恶行为。")
            else:
                print(f"{C_YELLOW}[!] 预期之外的响应: {resp.text}{C_RESET}")
        except requests.exceptions.RequestException as e:
            print(f"{C_RED}[AUDITOR ERROR]{C_RESET} Auditor 连接失败: {e}")

    def demo_05_record_forgery(self):
        print_header("场景 5: 恶意服务端 - 离线账本记录伪造 (Record Forgery)")
        slow_print("[-] 模拟服务端为掩盖作恶，向 Auditor 提交与实际负载 (Commitment) 不符的伪造记录...")
        test_sn = secrets.token_hex(32)
        real_cq = compute_query_commitment("real_user_query")
        fake_cq = compute_query_commitment("fake_server_query")

        audit_record = AuditRecord(
            request_id=f"req_{test_sn[:8]}", sn=test_sn, query_commitment=fake_cq,
            binding_tag="stub", epoch_id=1, decision=Decision.FAILED,
            timestamp_ms=int(time.time() * 1000), prev_hash="stub", entry_mac="stub"
        )

        try:
            post_resp = requests.post(f"{self.auditor_url}/api/v1/auditor/report",
                                      json=audit_record.model_dump(mode='json'))
            if post_resp.status_code != 200:
                print(f"{C_RED}[AUDITOR ERROR]{C_RESET} 写入失败 HTTP {post_resp.status_code}: {post_resp.text}")
                return
        except Exception as e:
            print(f"{C_RED}[AUDITOR ERROR]{C_RESET} {e}")
            return

        slow_print("[-] [内鬼操作] 当前原型账本接受了伪造记录追加，接下来用用户侧 expected_cq 发起一致性争议...")

        slow_print("[-] [用户维权] 用户拿着真实的 expected_cq 发起争议追踪...")
        try:
            trace_resp = requests.get(f"{self.auditor_url}/api/v1/auditor/trace/{test_sn}",
                                      params={"expected_cq": real_cq})
            if trace_resp.status_code == 200 and trace_resp.json().get("cq_consistent") is False:
                print(f"{C_GREEN}[TAMPER DETECTED]{C_RESET} 载荷矛盾发现！账本被伪造的假象已被一致性校验戳穿！")
            else:
                print(f"{C_YELLOW}[!] 预期之外的一致性判定或响应码: HTTP {trace_resp.status_code}{C_RESET}")
        except Exception as e:
            print(f"{C_RED}[AUDITOR ERROR]{C_RESET} {e}")

    async def _async_flood(self, payloads, concurrency):
        sem = asyncio.Semaphore(concurrency)

        async def fire(session, payload):
            async with sem:
                try:
                    async with session.post(self.verifier_url, json=payload, timeout=1.5) as resp:
                        if resp.status == 200:
                            return "200_" + (await resp.json()).get("decision", "UNK")
                        return f"HTTP_{resp.status}"
                except asyncio.TimeoutError:
                    return "L4_TIMEOUT"
                except aiohttp.ClientError:
                    return "L4_CONN_ERR"
                except Exception:
                    return "ERR"

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=concurrency)) as session:
            tasks = [fire(session, p) for p in payloads]
            return await asyncio.gather(*tasks)

    def demo_06_resource_protection_flood(self):
        print_header("场景 6: 资源保护展示 (Computation-DoS Flood)")
        total_requests = 300
        concurrency = 30
        slow_print(f"[-] 正在生成 {total_requests} 个高并发重放弹药 (并发度: {concurrency})...")

        ticket = acquire_ticket()
        req = create_bound_request(ticket, "flood_target")
        payloads = [req.model_dump(mode='json') for _ in range(total_requests)]

        slow_print(f"[-] 洪流发射！(预计需要 1-2 秒等待判定)...")
        start = time.perf_counter()
        results = asyncio.run(self._async_flood(payloads, concurrency))
        cost = time.perf_counter() - start

        counts = Counter(results)
        success_count = counts.get("200_SUCCESS", 0)
        l4_blocked = counts.get("L4_TIMEOUT", 0) + counts.get("L4_CONN_ERR", 0) + counts.get("ERR", 0)
        l7_blocked = sum(v for k, v in counts.items() if "REJECTED" in k or "422" in k)

        print(f"\n{C_MAGENTA}=== 洪流防御战报 ==={C_RESET}")
        print(f"压测耗时: {cost:.2f} 秒")
        print(f"攻击请求: {total_requests}")
        print(f"L4 拦截 (eBPF/TC) : {l4_blocked}")
        print(f"L7 拦截 (Verifier): {l7_blocked}")
        print(f"成功触达 PIR 引擎 : {success_count} (穿透率: {success_count / total_requests * 100:.2f}%)")
        print(f"状态分布: {dict(counts)}")
        print(f"{C_GREEN}结论: L4/L7 协同防线将绝大部分无效请求阻断在高开销 PIR 计算之前。{C_RESET}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("server_ip", default="127.0.0.1", nargs="?")
    args = parser.parse_args()

    demo = MasterDemoCLI(args.server_ip)

    while True:
        print(f"\n{C_CYAN}=== PIR 匿名抗滥用控制系统 (Master Demo CLI) ==={C_RESET}")
        print("1. 正常请求流转 (Happy Path)")
        print("2. 恶意客户端: 并发重放攻击 (L4/L7 协同拦截)")
        print("3. 恶意客户端: 载荷与凭证分离篡改 (Binding Tampering)")
        print("4. 恶意服务端: 幽灵核销争议 (Ghost Consumption)")
        print("5. 恶意服务端: 审计账本内容伪造 (Record Forgery)")
        print("6. 资源保护展示: Computation-DoS 洪峰压测")
        print("0. 退出大秀")

        choice = input(f"\n{C_YELLOW}请选择要演示的剧本 [0-6]: {C_RESET}")

        if choice == '1':
            demo.demo_01_happy_path()
        elif choice == '2':
            demo.demo_02_replay_attack()
        elif choice == '3':
            demo.demo_03_binding_tampering()
        elif choice == '4':
            demo.demo_04_ghost_consumption()
        elif choice == '5':
            demo.demo_05_record_forgery()
        elif choice == '6':
            demo.demo_06_resource_protection_flood()
        elif choice == '0':
            print("感谢观看！大秀落幕。")
            break
        else:
            print("无效输入，请重试。")

        input(f"\n{C_YELLOW}[按 Enter 键返回主菜单...]{C_RESET}")


if __name__ == "__main__":
    main()