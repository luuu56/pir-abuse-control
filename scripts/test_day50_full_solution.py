# scripts/test_day50_full_solution.py
import sys
import time
import json
import asyncio
import argparse
import threading
from pathlib import Path
from collections import Counter

try:
    import aiohttp
    import psutil
except ImportError:
    print("❌ 缺少必要依赖！")
    sys.exit(1)

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from services.client.main import acquire_ticket, create_bound_request


class ResourceMonitor:
    def __init__(self):
        self.is_running = False
        self.cpu_records = []
        self.mem_records = []
        self._thread = None

    def _monitor_loop(self):
        psutil.cpu_percent(interval=None)
        while self.is_running:
            self.cpu_records.append(psutil.cpu_percent(interval=None))
            self.mem_records.append(psutil.virtual_memory().percent)
            time.sleep(0.5)

    def start(self):
        self.is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False
        if self._thread: self._thread.join()

    def get_stats(self):
        if not self.cpu_records: return 0.0, 0.0, 0.0, 0.0
        return (sum(self.cpu_records) / len(self.cpu_records), max(self.cpu_records),
                sum(self.mem_records) / len(self.mem_records), max(self.mem_records))


def build_attack_payloads(total_requests: int) -> list:
    payloads = []
    print(f"[*] 正在申请 1 张真票，并生成 {total_requests} 份并发重放载荷...")
    # 补充预加载口径说明
    print("    ➜ 说明: 母票申请与绑定属于预加载阶段，不计入 Day 50 主压测耗时")
    real_ticket = acquire_ticket()
    real_req = create_bound_request(real_ticket, "ebpf_ultimate_test")
    base_payload = real_req.model_dump(mode='json')
    for _ in range(total_requests):
        payloads.append(base_payload)
    return payloads


async def fire_request(session: aiohttp.ClientSession, url: str, payload: dict, sem: asyncio.Semaphore):
    async with sem:
        start_time = time.perf_counter()
        try:
            async with session.post(url, json=payload, timeout=1.5) as resp:
                resp_text = await resp.text()
                latency = time.perf_counter() - start_time
                status = resp.status
                if status == 200:
                    try:
                        decision = json.loads(resp_text).get("decision", "UNKNOWN")
                        return latency, f"200_{decision}"
                    except:
                        return latency, "200_PARSE_ERR"
                elif status == 422:
                    return latency, "422_VALIDATION_ERR"
                else:
                    return latency, f"HTTP_{status}"
        except asyncio.TimeoutError:
            return time.perf_counter() - start_time, "L4_OR_NET_TIMEOUT"
        except aiohttp.ClientError:
            return time.perf_counter() - start_time, "L4_OR_NET_CONN_ERR"
        except Exception:
            return time.perf_counter() - start_time, "UNKNOWN_ERROR"


async def run_full_solution_test(target_ip: str, total_requests: int, concurrency: int):
    verifier_url = f"http://{target_ip}:8002/api/v1/verifier/execute"

    print("=" * 65)
    print("🧪 Day 50: 完整方案实验 (L7 Verifier + L4 eBPF 协同防御) 🧪")
    print(f"➜ 攻击目标: {verifier_url}")
    print(f"➜ 攻击模式: 高并发重放")
    print(f"➜ 总请求量: {total_requests}")
    print(f"➜ 并发级别: {concurrency}")
    print("➜ 判定口径: 1.5s 短超时仅用于加速识别疑似 L4 黑洞，不代表内核层唯一证据")
    print("=" * 65 + "\n")

    payloads = build_attack_payloads(total_requests)

    monitor = ResourceMonitor()
    monitor.start()

    print(f"\n[*] 弹药装填完毕！开始执行高并发压测...")
    start_time = time.perf_counter()

    sem = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=concurrency)) as session:
        tasks = [fire_request(session, verifier_url, payload, sem) for payload in payloads]
        results = await asyncio.gather(*tasks)

    total_time = time.perf_counter() - start_time
    monitor.stop()

    # 获取基础统计信息
    latencies = [r[0] for r in results]
    status_codes = [r[1] for r in results]
    status_counts = Counter(status_codes)

    # 细化分层拦截比例
    l7_rejected = sum(count for code, count in status_counts.items() if "REJECTED" in code or "422" in code)
    l4_suspected = sum(count for code, count in status_counts.items() if "L4_OR_NET_" in code)
    success_count = status_counts.get("200_SUCCESS", 0)

    # 增加综合防御成功率
    defense_success_rate = ((total_requests - success_count) / total_requests) * 100 if total_requests else 0.0

    # 增加总体平均耗时（反映 L4 慢超时与 L7 快拒绝的混合效应）
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    avg_cpu, max_cpu, avg_mem, max_mem = monitor.get_stats()

    print("\n" + "=" * 65)
    print("📊 [全链路协同防御数据汇总] 📊")
    print(f"⏱️  总压测耗时        : {total_time:.2f} 秒")
    print(f"⏳ 客户端平均观测耗时 : {avg_latency * 1000:.2f} ms")
    print("-" * 65)
    print(f"🛡️ 综合防御成功率    : {defense_success_rate:.2f} %")
    print(f"   ├─ L7 业务拒绝占比: {(l7_rejected / total_requests) * 100:.2f} %")
    print(f"   ├─ L4 疑似拦截占比: {(l4_suspected / total_requests) * 100:.2f} %")
    print(f"   └─ 成功穿透占比   : {(success_count / total_requests) * 100:.2f} %")
    print("-" * 65)
    print(f"💻 Host CPU (Avg/Max): {avg_cpu:.1f}% / {max_cpu:.1f}%")
    print(f"🧠 Host Mem (Avg/Max): {avg_mem:.1f}% / {max_mem:.1f}%")
    print("-" * 65)
    print("📈 客户端视角状态分布:")
    for code, count in status_counts.most_common():
        print(f"   [{code}]: {count} 次")
    print("=" * 65)

    print("\n[验收提示]：")
    print("客户端出现大量 L4_OR_NET 现象与 L4 丢弃机制预期一致，可作为协同防线介入的近似证据。")
    print("为确保证据闭环，请额外核对以下服务端日志：")
    print("1. Verifier 日志中应出现 'Derived short-term L4 block for source...'")
    print("2. tc_gateway.py (eBPF) 终端应输出 '[CONTROL] Derived Block Sync from verifier decision...'")
    print("3. Auditor 审计账本中仅记录早期实际触达 L7 的有限几条事件。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Day 50 Full Pipeline Evaluation")
    parser.add_argument("server_ip", help="Target server IP address")
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=100)
    args = parser.parse_args()

    try:
        asyncio.run(run_full_solution_test(args.server_ip, args.requests, args.concurrency))
    except KeyboardInterrupt:
        print("\n[!] 压测被手动中断。")