# scripts/run_day58_mixed_workload_eval.py
import sys
import time
import json
import asyncio
import aiohttp
import argparse
import requests
import random
import os
import math
import threading
import concurrent.futures
from pathlib import Path

try:
    import psutil
except ImportError:
    print("❌ 缺少 psutil！请执行: pip install psutil")
    sys.exit(1)

os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["no_proxy"] = "127.0.0.1,localhost"
os.environ["NO_PROXY"] = "127.0.0.1,localhost"

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket, create_bound_request

RESULTS_DIR = Path(root_path) / "results" / "mixed_workload"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

C_CYAN = '\033[96m'
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_RESET = '\033[0m'


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

    def get_avg_stats(self):
        avg_cpu = sum(self.cpu_records) / len(self.cpu_records) if self.cpu_records else 0.0
        avg_mem = sum(self.mem_records) / len(self.mem_records) if self.mem_records else 0.0
        return avg_cpu, avg_mem


def _generate_single_legit_payload(_):
    for attempt in range(3):
        try:
            t = acquire_ticket()
            return create_bound_request(t, "legit_mix_query").model_dump(mode='json')
        except requests.exceptions.ReadTimeout:
            time.sleep(random.uniform(0.5, 2.0))
        except Exception as e:
            print(f"\n[票据生成报错] {type(e).__name__}: {e}")
            return None

    print("\n[票据生成警告] Issuer 压力过大，连续 3 次 ReadTimeout，放弃该票据。")
    return None


class MixedWorkloadEvaluator:
    def __init__(self, target_ip):
        self.config = load_config()
        self.target_ip = target_ip
        self.url = f"http://{target_ip}:8002/api/v1/verifier/execute"
        self.metrics_url = f"http://{target_ip}:8002/api/v1/verifier/metrics"

        self.eval_cfg = self.config.get("evaluation", {})
        self.concurrencies = self.eval_cfg.get("mixed_workload_concurrencies", [1, 10, 30, 50, 100])

        self.total_reqs_per_run = 300
        self.attack_ratios = [0.0, 0.1, 0.5, 0.9]

        self.legit_timeout = 15.0
        self.attack_timeout = 3.0

        self.ebpf_block_ttl_sec = self.config.get("ebpf", {}).get("derived_block_ttl_sec", 10)

    def _get_pir_invocations(self):
        try:
            resp = requests.get(self.metrics_url, timeout=2.0)
            if resp.status_code == 200:
                body = resp.json()
                metrics = body.get("metrics", body)
                return metrics.get("pir_invoked_total") or metrics.get("pir_invoked") or 0
        except:
            pass
        return 0

    def build_mixed_workload(self, ratio: float, attack_type="replay"):
        requested_attack_count = int(self.total_reqs_per_run * ratio)
        requested_legit_count = self.total_reqs_per_run - requested_attack_count

        workload = []

        if requested_legit_count > 0:
            print(f"    [装填] 多核预加载 {requested_legit_count} 发 Legit 票据...", flush=True)
            start_t = time.time()
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                # 采用 as_completed 实现细腻的进度条
                futures = [executor.submit(_generate_single_legit_payload, i) for i in range(requested_legit_count)]
                completed = 0
                for future in concurrent.futures.as_completed(futures):
                    results.append(future.result())
                    completed += 1
                    pct = int(completed / requested_legit_count * 100)
                    bar = "█" * (pct // 2) + "-" * (50 - pct // 2)
                    sys.stdout.write(f"\r    [装填进度] [{bar}] {completed}/{requested_legit_count} ({pct}%)")
                    sys.stdout.flush()

            print(f"\n    [装填] 耗时 {time.time() - start_t:.1f}s")

            valid_legits = [r for r in results if r is not None]
            for p in valid_legits:
                workload.append(("legit", p))

        if requested_attack_count > 0 and attack_type == "replay":
            print(f"    [装填] 生成 1 发母票并克隆为 {requested_attack_count} 发 Replay 弹药...")
            try:
                t = acquire_ticket()
                base_attack_payload = create_bound_request(t, "flood_target").model_dump(mode='json')
                for _ in range(requested_attack_count):
                    workload.append(("attack", base_attack_payload))
            except Exception as e:
                print(f"    {C_RED}[致命错误] Attack 母票生成失败: {e}{C_RESET}")

        random.shuffle(workload)
        return workload, requested_legit_count, requested_attack_count

    async def _fire_requests(self, workload, concurrency):
        sem = asyncio.Semaphore(concurrency)
        total_reqs = len(workload)
        completed = 0

        async def fire(session, req_type, payload):
            nonlocal completed
            timeout = self.attack_timeout if req_type == "attack" else self.legit_timeout
            start = time.perf_counter()
            async with sem:
                try:
                    async with session.post(self.url, json=payload, timeout=timeout) as resp:
                        lat = time.perf_counter() - start
                        if resp.status == 200:
                            decision = (await resp.json()).get("decision", "UNK")
                            ret = req_type, lat, f"200_{decision}"
                        else:
                            ret = req_type, lat, f"HTTP_{resp.status}"
                except asyncio.TimeoutError:
                    ret = req_type, time.perf_counter() - start, "L4_TIMEOUT"
                except aiohttp.ClientError:
                    ret = req_type, time.perf_counter() - start, "L4_CONN_ERR"
                except Exception:
                    ret = req_type, 0, "ERR"

            # 退出并发锁后，安全更新进度条
            completed += 1
            pct = int(completed / total_reqs * 100)
            bar = "█" * (pct // 2) + "-" * (50 - pct // 2)
            sys.stdout.write(f"\r  [发射进度] [{bar}] {completed}/{total_reqs} ({pct}%)")
            sys.stdout.flush()

            return ret

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=concurrency)) as session:
            tasks = [fire(session, req_type, p) for req_type, p in workload]
            results = await asyncio.gather(*tasks)
            print()  # 进度条跑完后换行
            return results

    def run_sweep(self, mode: str):
        print(f"\n{C_CYAN}▶ 运行混合流量压测矩阵 | 模式: {mode}{C_RESET}")

        results = {
            "mode": mode,
            "mode_metadata": {
                "tc_gateway_expected": mode == "full",
                "ebpf_block_ttl_sec": self.ebpf_block_ttl_sec,
                "description": "L7-only runs Verifier purely; Full relies on Verifier+eBPF/TC synchronization.",
                "measurement_scope": "verifier_and_pir_path_only (pre-fetched tickets)",
                "workload_profile": "burst-style mixed workload"
            },
            "sweep_data": {}
        }

        for ratio in self.attack_ratios:
            ratio_key = f"ratio_{int(ratio * 100)}"
            results["sweep_data"][ratio_key] = {}
            print(f"\n{C_YELLOW}--- 攻击占比: {ratio * 100:.0f}% Attack / {(1 - ratio) * 100:.0f}% Legit ---{C_RESET}")

            for c in self.concurrencies:
                if c == 300:
                    print(f"\n  [警告] 并发 C=300 将触发极端 Burst-style (浪涌) 请求，考验系统瞬时承压...")
                else:
                    print(f"\n  [并发 C={c}] 准备弹药...")

                workload, requested_legit, requested_attack = self.build_mixed_workload(ratio)
                actual_legit = sum(1 for t, _ in workload if t == "legit")
                actual_attack = sum(1 for t, _ in workload if t == "attack")
                legit_generation_failures = requested_legit - actual_legit
                attack_generation_failures = requested_attack - actual_attack

                # [熔断与标记] 判断本轮样本输入质量是否退化
                degraded_input = (legit_generation_failures > 0) or (attack_generation_failures > 0)
                invalid_for_plot = attack_generation_failures > 0
                if attack_generation_failures > 0:
                    print(
                        f"    {C_RED}⚰️  [严重警告] 攻击载荷严重缺失 (预期 {requested_attack} / 实际 {actual_attack})！本档位数据将被标记为退化！{C_RESET}")
                elif legit_generation_failures > 0:
                    print(
                        f"    {C_YELLOW}⚠️  [注意] 合法载荷发生缩水 (丢失 {legit_generation_failures} 发)，但仍可用于评估在线阶段延迟。{C_RESET}")

                monitor = ResourceMonitor()
                monitor.start()

                invocations_before = self._get_pir_invocations()

                print(f"  [发射] 混合发送 {len(workload)} 个请求...", flush=True)
                start_time = time.perf_counter()
                outcomes = asyncio.run(self._fire_requests(workload, c))
                total_time = time.perf_counter() - start_time

                time.sleep(1)
                invocations_after = self._get_pir_invocations()
                monitor.stop()

                legit_lats = [lat for t, lat, code in outcomes if t == "legit" and "SUCCESS" in code]
                legit_success_count = len(legit_lats)
                legit_failed = actual_legit - legit_success_count

                # --- 修改 Legit 的死因统计 ---
                legit_codes = [code for t, lat, code in outcomes if t == "legit"]
                legit_l4_timeout = sum(1 for c in legit_codes if "L4_TIMEOUT" in c)  # 极可能是 eBPF 丢包
                legit_conn_err = sum(1 for c in legit_codes if "L4_CONN_ERR" in c or "ERR" in c)  # 服务过载或挂了
                legit_l7_failed = len(legit_codes) - legit_success_count - legit_l4_timeout - legit_conn_err

                # --- 修改 Attack 的死因统计 ---
                attack_codes = [code for t, lat, code in outcomes if t == "attack"]
                att_l7_blocked = sum(1 for c in attack_codes if "REJECTED" in c)
                att_l4_timeout = sum(1 for c in attack_codes if "L4_TIMEOUT" in c)  # eBPF 防线战果
                att_conn_err = sum(1 for c in attack_codes if "L4_CONN_ERR" in c or "ERR" in c)  # 服务挂了

                def p95(lats):
                    if not lats: return 0.0
                    s_lats = sorted(lats)
                    idx = max(0, min(len(s_lats) - 1, math.ceil(len(s_lats) * 0.95) - 1))
                    return s_lats[idx]

                pir_diff = max(0, invocations_after - invocations_before)
                pure_attack_pir = max(0, pir_diff - legit_success_count)

                overall_blocked_before_compute_ratio_pct = ((len(workload) - pir_diff) / len(workload) * 100) if len(
                    workload) else 0.0
                pure_attack_pir_reduction_proxy_pct = (
                            (actual_attack - pure_attack_pir) / actual_attack * 100) if actual_attack else 0.0

                avg_cpu, avg_mem = monitor.get_avg_stats()

                metrics = {
                    "degraded_input_quality": degraded_input,
                    "invalid_for_primary_plot": invalid_for_plot,
                    "legit_metrics": {
                        "requested_legit_count": requested_legit,
                        "actual_legit_count": actual_legit,
                        "legit_generation_failures": legit_generation_failures,
                        "success_rate_pct": (legit_success_count / actual_legit * 100) if actual_legit else 100.0,
                        "l4_failed": legit_l4_timeout,  # Mapping to L4_TIMEOUT (likely eBPF)
                        "conn_err": legit_conn_err,     # Mapping to service overload
                        "l7_failed": legit_l7_failed,   # Mapping to L7 explicit rejection
                        "avg_latency_ms": (sum(legit_lats) / len(legit_lats) * 1000) if legit_lats else 0.0,
                        "p95_latency_ms": p95(legit_lats) * 1000,
                        "request_tps": round(actual_legit / total_time, 2) if total_time > 0 else 0.0,
                        "success_tps": round(legit_success_count / total_time, 2) if total_time > 0 else 0.0
                    },
                    "attack_metrics": {
                        "requested_attack_count": requested_attack,
                        "actual_attack_count": actual_attack,
                        "attack_generation_failures": attack_generation_failures,
                        "total_sent": actual_attack,
                        "l7_blocked": att_l7_blocked,
                        "l4_blocked": att_l4_timeout,   # L4 intercept
                        "conn_err": att_conn_err,       # Server overload mapping
                        "penetrated": actual_attack - att_l7_blocked - att_l4_timeout - att_conn_err
                    },
                    "system_metrics": {
                        "test_duration_sec": round(total_time, 2),
                        "host_avg_cpu_pct": round(avg_cpu, 1),
                        "host_avg_mem_pct": round(avg_mem, 1),
                        "pir_invocations_diff": pir_diff,
                        "pure_attack_pir_invocations": pure_attack_pir,
                        "overall_blocked_before_compute_ratio_pct": round(overall_blocked_before_compute_ratio_pct, 2),
                        "pure_attack_pir_reduction_proxy_pct": round(pure_attack_pir_reduction_proxy_pct, 2)
                    }
                }

                results["sweep_data"][ratio_key][f"c_{c}"] = metrics

                print(
                    f"    ➜ Legit 成功率: {metrics['legit_metrics']['success_rate_pct']:.1f}% | P95 延迟: {metrics['legit_metrics']['p95_latency_ms']:.2f} ms")
                print(
                    f"    ➜ Attack 拦截: L7={att_l7_blocked}, L4={att_l4_timeout}, ConnErr={att_conn_err} | 纯攻击算力保护 (Proxy): {metrics['system_metrics']['pure_attack_pir_reduction_proxy_pct']}%")

                if mode == "full" and legit_failed > 0 and ratio > 0:
                    # 统计合法的具体死因 (比如是 L4_TIMEOUT 还是 HTTP_500 还是 ERR)
                    legit_fail_codes = [c for t, lat, c in outcomes if t == "legit" and "SUCCESS" not in c]
                    from collections import Counter
                    fail_distribution = dict(Counter(legit_fail_codes))

                    print(
                        f"    {C_RED}[战损通报] {legit_failed} 个合法请求同源失败。死因分布: {fail_distribution}{C_RESET}")
                    print(
                        f"    {C_YELLOW}        (注: 若 L4_TIMEOUT>0，部分失败属于 eBPF 同源连坐战损；若包含 HTTP/ERR 则是后端过载导致){C_RESET}")

                if mode == "full":
                    safe_sleep = self.ebpf_block_ttl_sec + 2
                    print(f"    [冷却] 等待 {safe_sleep} 秒，确保 eBPF {self.ebpf_block_ttl_sec}s 黑名单彻底过期释放...")
                    time.sleep(safe_sleep)

        return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("server_ip", default="127.0.0.1", nargs="?")
    args = parser.parse_args()

    evaluator = MixedWorkloadEvaluator(args.server_ip)

    print(f"\n{C_YELLOW}🚀 [Day 58 核心实验 A] Same-Source Mixed Workload (同源混合战损与降级评估){C_RESET}")
    print("⚠️  学术界定（论文话术防杠声明）：")
    print("   当前环境所有的 Legit 与 Attack 流量均来自同一个 Source IP。")
    print("   在 Full 模式下，Legit 成功率下降精确衡量的是【源 IP 级战损 (Collateral Damage)】。")
    print("   实验采用严格剥离合法请求的 Pure Attack PIR Reduction 算法，确保证据链闭环。")
    print("   当前测试阶段：仅针对 REPLAY 攻击进行扫雷。")
    print("=" * 60)

    input(
        f"\n{C_YELLOW}[手动操作 1]{C_RESET} 混合测试对后端性能消耗极大，请确保 base.yaml 中 dataset_path 为 db_1gb.bin，并重启 pir_server。完成后按回车...")

    # ==========================
    # Phase 1: L7-Only
    # ==========================
    print(f"\n{C_CYAN}--- [Phase 1: L7-Only 防御] ---{C_RESET}")
    input(
        f"{C_YELLOW}[手动操作 2] 请确保 tc_gateway.py (eBPF) 已关闭！重启 verifier 以清理状态。完成后按回车...{C_RESET}")
    l7_res = evaluator.run_sweep("l7_only")
    with open(RESULTS_DIR / "replay_mix_l7_only.json", "w") as f: json.dump(l7_res, f, indent=2)

    # ==========================
    # Phase 2: Full System
    # ==========================
    print(f"\n{C_CYAN}--- [Phase 2: Full System 防御] ---{C_RESET}")
    input(
        f"{C_YELLOW}[手动操作 3] ⚠️ 请去云服务器执行 redis-cli -a 'Zsw121381' flushall！然后启动 sudo python scripts/tc_gateway.py eth0！完成后按回车...{C_RESET}")
    full_res = evaluator.run_sweep("full")
    with open(RESULTS_DIR / "replay_mix_full.json", "w") as f: json.dump(full_res, f, indent=2)

    print(f"\n🎉 实验 A 同源混合流量测评全部完成！数据已保存至 {RESULTS_DIR}")


if __name__ == "__main__":
    main()