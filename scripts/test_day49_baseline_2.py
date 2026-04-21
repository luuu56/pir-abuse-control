# scripts/test_day49_baseline_2.py
import sys
import time
import json
import asyncio
import argparse
import threading
import secrets
from pathlib import Path
from collections import Counter

try:
    import aiohttp
    import psutil
except ImportError:
    print("❌ 缺少必要依赖！请先运行: pip install aiohttp psutil")
    sys.exit(1)

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

# 导入真正的客户端逻辑与公共工具
from common.config import load_config
from common.crypto_utils import get_current_epoch_id
from services.client.main import acquire_ticket, create_bound_request


class ResourceMonitor:
    """后台资源监控线程，记录压测期间宿主机 (Host) 的 CPU 和 Memory 峰值"""

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
        if self._thread:
            self._thread.join()

    def get_stats(self):
        if not self.cpu_records: return 0.0, 0.0, 0.0, 0.0
        return (
            sum(self.cpu_records) / len(self.cpu_records),
            max(self.cpu_records),
            sum(self.mem_records) / len(self.mem_records),
            max(self.mem_records)
        )


def build_attack_payloads(mode: str, total_requests: int) -> list:
    """在内存中提前预生成攻击载荷"""
    payloads = []
    print(f"[*] 正在内存中预生成 {total_requests} 发 [{mode.upper()}] 攻击载荷...")

    if mode == "schema":
        # 结构残缺攻击：触发 Pydantic 或入口层拦截 (422)
        for i in range(total_requests):
            payloads.append({
                "request_id": f"schema_abuse_{i}",
                "query_payload": "garbage_data"
            })

    elif mode == "crypto":
        # 获取当前真实有效 Epoch，绕过前置过期快拒绝，优先压测密码学校验与业务拒绝路径
        config = load_config()
        epoch_cfg = config.get("epoch", {})
        current_epoch = get_current_epoch_id(epoch_cfg.get("duration_sec", 3600))

        for i in range(total_requests):
            payloads.append({
                "request_id": f"crypto_abuse_{i}",
                "query_payload": "fake_query",
                "ticket": {
                    "sn": secrets.token_hex(32),
                    "sigma": "ZmFrZV9zaWdtYV9iYXNlNjRfZW5jb2RlZA==",  # 伪造的 sigma
                    "epoch_id": current_epoch
                },
                "binding_tag": "0" * 64,
                "witness": {"timestamp_ms": int(time.time() * 1000), "nonce": "abc", "client_state_digest": "def"}
            })

    elif mode == "replay":
        # 重放攻击：触发 Redis 原子锁并发竞争
        print("    ➜ 说明: replay 模式中的母票申请属于预加载阶段，不计入压测时长")
        print("    ➜ 预期结果: 1 次 200_SUCCESS，其余请求主要为 200_REJECTED")
        real_ticket = acquire_ticket()
        real_req = create_bound_request(real_ticket, "replay_target_payload")
        base_payload = real_req.model_dump(mode='json')
        for _ in range(total_requests):
            payloads.append(base_payload)

    return payloads


async def fire_request(session: aiohttp.ClientSession, url: str, payload: dict, sem: asyncio.Semaphore):
    """单次异步压测发射函数（解析 Verifier 业务状态码）"""
    async with sem:
        start_time = time.perf_counter()
        try:
            async with session.post(url, json=payload, timeout=10) as resp:
                resp_text = await resp.text()
                latency = time.perf_counter() - start_time
                status = resp.status

                if status == 200:
                    try:
                        data = json.loads(resp_text)
                        decision = data.get("decision", "UNKNOWN")
                        return latency, f"200_{decision}"
                    except json.JSONDecodeError:
                        return latency, "200_PARSE_ERR"
                elif status == 422:
                    return latency, "422_VALIDATION_ERR"
                else:
                    return latency, f"HTTP_{status}"

        except asyncio.TimeoutError:
            return time.perf_counter() - start_time, "timeout"
        except aiohttp.ClientError:
            return time.perf_counter() - start_time, "client_error"
        except Exception:
            return time.perf_counter() - start_time, "unknown_error"


async def run_l7_defense_stress_test(target_ip: str, mode: str, total_requests: int, concurrency: int):
    verifier_url = f"http://{target_ip}:8002/api/v1/verifier/execute"

    mode_desc = {
        "schema": "入口校验层 (FastAPI/Pydantic) 基线",
        "crypto": "密码学校验层 (RSA验签/HMAC) 基线",
        "replay": "状态机/Redis 并发锁 IO 基线",
    }

    print("=" * 60)
    print("🛡️ Day 49: 基线实验 2 (L7 Verifier 防御极限压测) 🛡️")
    print(f"➜ 攻击目标: {verifier_url}")
    print(f"➜ 攻击模式: {mode.upper()} Abuse")
    print(f"➜ 模式说明: {mode_desc[mode]}")
    print(f"➜ 总请求量: {total_requests}")
    print(f"➜ 并发级别: {concurrency}")
    print("=" * 60 + "\n")

    payloads = build_attack_payloads(mode, total_requests)

    monitor = ResourceMonitor()
    monitor.start()

    print(f"\n[*] 弹药装填完毕！开始以 {concurrency} 并发倾泻火力...")
    start_time = time.perf_counter()

    sem = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=concurrency)) as session:
        tasks = [fire_request(session, verifier_url, payload, sem) for payload in payloads]
        results = await asyncio.gather(*tasks)

    total_time = time.perf_counter() - start_time
    monitor.stop()

    # --- 数据统计 ---
    latencies = [r[0] for r in results]
    status_codes = [r[1] for r in results]
    status_counts = Counter(status_codes)

    request_throughput = total_requests / total_time

    # 修正：根据模式定制防御成功的语义
    if mode == "replay":
        defense_success_count = sum(
            count for code, count in status_counts.items()
            if "REJECTED" in code
        )
        # replay 模式下，唯一合法的 SUCCESS 也是防重放成功的必要组成部分
        defense_success_count += status_counts.get("200_SUCCESS", 0)
    else:
        defense_success_count = sum(
            count for code, count in status_counts.items()
            if "REJECTED" in code or "422" in code
        )

    defense_success_tps = defense_success_count / total_time if total_time > 0 else 0.0

    sorted_latencies = sorted(latencies)

    def percentile(values, p):
        if not values: return 0.0
        return values[int((len(values) - 1) * p)]

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    p95 = percentile(sorted_latencies, 0.95)
    p99 = percentile(sorted_latencies, 0.99)
    max_latency = max(latencies) if latencies else 0.0

    avg_cpu, max_cpu, avg_mem, max_mem = monitor.get_stats()

    print("\n" + "=" * 60)
    print("📊 [L7 防御基线结果汇总] 📊")
    print(f"⏱️  总耗时            : {total_time:.2f} 秒")
    print(f"🚀 攻击发起吞吐量    : {request_throughput:.2f} req/sec")
    print(f"🛡️ 防御成功吞吐量    : {defense_success_tps:.2f} req/sec")
    print("-" * 60)
    print(f"⏳ 全响应混合延迟 (Avg): {avg_latency * 1000:.2f} ms")
    print(f"⏳ 全响应混合延迟 (P95): {p95 * 1000:.2f} ms")
    print(f"⏳ 全响应混合延迟 (P99): {p99 * 1000:.2f} ms")
    print(f"⏳ 全响应混合延迟 (Max): {max_latency * 1000:.2f} ms")
    print("-" * 60)
    print(f"💻 Host CPU (Avg / Max)    : {avg_cpu:.1f}% / {max_cpu:.1f}%")
    print(f"🧠 Host Memory (Avg / Max) : {avg_mem:.1f}% / {max_mem:.1f}%")
    print("-" * 60)
    print("📈 防御拦截状态码分布:")
    for code, count in status_counts.most_common():
        if "422" in code:
            icon = "🧱"
        elif "REJECTED" in code:
            icon = "🛡️"
        elif "SUCCESS" in code and mode == "replay":
            icon = "🎯"  # 标识唯一透传的靶心
        else:
            icon = "  "
        print(f"   {icon} [{code}]: {count} 次")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Day 49 L7 Verifier Baseline Tester")
    parser.add_argument("server_ip", help="Target server IP address")
    parser.add_argument("--mode", choices=["schema", "crypto", "replay"], default="crypto",
                        help="Attack mode (default: crypto)")
    parser.add_argument("--requests", type=int, default=1000, help="Total number of requests")
    parser.add_argument("--concurrency", type=int, default=100, help="Concurrency level")

    args = parser.parse_args()

    try:
        asyncio.run(run_l7_defense_stress_test(args.server_ip, args.mode, args.requests, args.concurrency))
    except KeyboardInterrupt:
        print("\n[!] 压测被手动中断。")
    except Exception as e:
        print(f"\n[❌ FAILED] 致命异常: {e}")