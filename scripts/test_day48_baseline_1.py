# scripts/test_day48_baseline_1.py
import sys
import time
import asyncio
import argparse
import threading
from pathlib import Path
from collections import Counter

# 尝试导入压测和监控依赖
try:
    import aiohttp
    import psutil
except ImportError:
    print("❌ 缺少必要依赖！请先运行: pip install aiohttp psutil")
    sys.exit(1)

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))


class ResourceMonitor:
    """后台资源监控线程，记录压测期间宿主机 (Host) 的 CPU 和 Memory 峰值"""

    def __init__(self):
        self.is_running = False
        self.cpu_records = []
        self.mem_records = []
        self._thread = None

    def _monitor_loop(self):
        # 抛弃第一次采样（通常是 0.0）
        psutil.cpu_percent(interval=None)
        while self.is_running:
            self.cpu_records.append(psutil.cpu_percent(interval=None))
            self.mem_records.append(psutil.virtual_memory().percent)
            time.sleep(0.5)  # 每 0.5 秒采样一次

    def start(self):
        self.is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False
        if self._thread:
            self._thread.join()

    def get_stats(self):
        if not self.cpu_records:
            return 0.0, 0.0, 0.0, 0.0
        return (
            sum(self.cpu_records) / len(self.cpu_records),
            max(self.cpu_records),
            sum(self.mem_records) / len(self.mem_records),
            max(self.mem_records)
        )


async def fire_request(session: aiohttp.ClientSession, url: str, payload: dict, sem: asyncio.Semaphore):
    """单次异步压测发射函数"""
    async with sem:
        # 优化 1：使用高精度单调时钟替代 time.time()
        start_time = time.perf_counter()
        try:
            async with session.post(url, json=payload, timeout=20) as resp:
                await resp.read()  # 确保读完响应体
                latency = time.perf_counter() - start_time
                return latency, resp.status
        except asyncio.TimeoutError:
            latency = time.perf_counter() - start_time
            return latency, "timeout"
        except aiohttp.ClientError:
            latency = time.perf_counter() - start_time
            return latency, "client_error"
        except Exception:
            latency = time.perf_counter() - start_time
            return latency, "unknown_error"


async def run_baseline_stress_test(target_ip: str, total_requests: int, concurrency: int):
    pir_url = f"http://{target_ip}:8003/api/v1/pir/query"

    print("=" * 60)
    print("🔥 Day 48: 基线实验 1 (无 access-control 的 PIR 服务基线) 🔥")
    print(f"➜ 攻击目标: {pir_url}")
    print(f"➜ 总请求量: {total_requests}")
    print(f"➜ 并发级别: {concurrency}")
    print("➜ 载荷模式: 固定 query_payload（用于稳定基线）")
    print("=" * 60 + "\n")

    monitor = ResourceMonitor()
    monitor.start()

    print("[*] 开始发动高并发异步火力压制...")
    start_time = time.perf_counter()

    # 固定载荷
    payload = {"query_payload": "baseline_stress_test_index_42"}
    sem = asyncio.Semaphore(concurrency)

    # 使用 aiohttp ClientSession 进行连接池复用
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=concurrency)) as session:
        tasks = [fire_request(session, pir_url, payload, sem) for _ in range(total_requests)]
        results = await asyncio.gather(*tasks)

    total_time = time.perf_counter() - start_time
    monitor.stop()

    # --- 数据统计 ---
    latencies = [r[0] for r in results]
    status_codes = [r[1] for r in results]

    success_latencies = [r[0] for r in results if r[1] == 200]
    success_count = len(success_latencies)

    request_throughput = total_requests / total_time
    success_throughput = success_count / total_time

    avg_latency = sum(success_latencies) / success_count if success_count else 0.0

    sorted_success = sorted(success_latencies)

    # 优化 2：声明统计精度边界
    # 简单离散百分位近似，满足当前基线实验需求，不追求统计学插值精度
    def percentile(values, p):
        if not values: return 0.0
        idx = int((len(values) - 1) * p)
        return values[idx]

    p95 = percentile(sorted_success, 0.95)
    p99 = percentile(sorted_success, 0.99)
    max_latency = max(success_latencies) if success_latencies else 0.0
    min_latency = min(success_latencies) if success_latencies else 0.0

    status_counts = Counter(status_codes)
    avg_cpu, max_cpu, avg_mem, max_mem = monitor.get_stats()

    print("\n" + "=" * 60)
    print("📊 [基线压测结果汇总] 📊")
    print(f"⏱️  总耗时            : {total_time:.2f} 秒")
    print(f"🚀 发射吞吐量 (TPS)  : {request_throughput:.2f} req/sec")
    print(f"✅ 成功吞吐量 (TPS)  : {success_throughput:.2f} req/sec")
    print("-" * 60)
    print(f"⏳ 成功请求延迟 (Avg): {avg_latency * 1000:.2f} ms")
    print(f"⏳ 成功请求延迟 (P95): {p95 * 1000:.2f} ms")
    print(f"⏳ 成功请求延迟 (P99): {p99 * 1000:.2f} ms")
    print(f"⏳ 成功请求延迟 (Max): {max_latency * 1000:.2f} ms")
    print(f"⏳ 成功请求延迟 (Min): {min_latency * 1000:.2f} ms")
    print("-" * 60)
    print(f"💻 Host CPU (Avg / Max)    : {avg_cpu:.1f}% / {max_cpu:.1f}%")
    print(f"🧠 Host Memory (Avg / Max) : {avg_mem:.1f}% / {max_mem:.1f}%")
    print("-" * 60)
    print("📈 状态码分布:")
    for code, count in status_counts.items():
        print(f"   [{code}]: {count} 次")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Day 48 Baseline 1 Stress Tester")
    parser.add_argument("server_ip", help="Target server IP address")
    parser.add_argument("--requests", type=int, default=1000, help="Total number of requests (default: 1000)")
    parser.add_argument("--concurrency", type=int, default=100, help="Concurrency level (default: 100)")

    args = parser.parse_args()

    try:
        asyncio.run(run_baseline_stress_test(args.server_ip, args.requests, args.concurrency))
    except KeyboardInterrupt:
        print("\n[!] 压测被手动中断。")
    except Exception as e:
        print(f"\n[❌ FAILED] 致命异常: {e}")