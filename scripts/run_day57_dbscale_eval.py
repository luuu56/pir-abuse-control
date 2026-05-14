# scripts/run_day57_dbscale_eval.py
import sys
import time
import json
import asyncio
import aiohttp
import argparse
import requests
import os
import statistics
from pathlib import Path
from collections import Counter

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

RESULTS_DIR = Path(root_path) / "results" / "dbscale"
for sub in ["raw", "l7_only", "full", "attack", "aggregated"]:
    (RESULTS_DIR / sub).mkdir(parents=True, exist_ok=True)

C_CYAN = '\033[96m'
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_RESET = '\033[0m'


class DBScaleEvaluator:
    def __init__(self, target_ip):
        self.config = load_config()
        self.target_ip = target_ip
        self.raw_url = f"http://{target_ip}:8003/api/v1/pir/query"
        self.protected_url = f"http://{target_ip}:8002/api/v1/verifier/execute"
        self.metrics_url = f"http://{target_ip}:8002/api/v1/verifier/metrics"

        self.execution_topology = "local" if target_ip in ["127.0.0.1", "localhost", "0.0.0.0"] else "remote"

        self.eval_cfg = self.config.get("evaluation", {})
        self.concurrencies = self.eval_cfg.get("concurrency_levels", [1, 10, 30, 50])
        self.test_reqs = self.eval_cfg.get("dbscale_test_requests", 50)
        self.attack_reqs = self.eval_cfg.get("dbscale_attack_requests", 300)

        self.legit_timeout = self.eval_cfg.get("legit_timeout_sec", 20.0)
        self.attack_timeout = self.eval_cfg.get("attack_timeout_sec", 3.0)
        self.attack_concurrency = self.eval_cfg.get("attack_concurrency", 30)

    async def _fire_requests(self, url, payloads, concurrency, is_raw=False, timeout=5.0, label_timeout_as_l4=False):
        sem = asyncio.Semaphore(concurrency)

        async def fire(session, payload):
            start = time.perf_counter()
            async with sem:
                try:
                    async with session.post(url, json=payload, timeout=timeout) as resp:
                        latency = time.perf_counter() - start
                        if resp.status == 200:
                            if is_raw: return "200_SUCCESS", latency
                            decision = (await resp.json()).get("decision", "UNK")
                            return f"200_{decision}", latency
                        return f"HTTP_{resp.status}", latency
                except asyncio.TimeoutError:
                    return "L4_TIMEOUT" if label_timeout_as_l4 else "CLIENT_TIMEOUT", 0
                except aiohttp.ClientError:
                    return "L4_CONN_ERR" if label_timeout_as_l4 else "CLIENT_CONN_ERR", 0
                except Exception:
                    return "ERR", 0

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=concurrency)) as session:
            tasks = [fire(session, p) for p in payloads]
            return await asyncio.gather(*tasks)

    def _get_pir_invocations(self):
        try:
            resp = requests.get(self.metrics_url, timeout=2.0)
            if resp.status_code == 200:
                body = resp.json()
                metrics = body.get("metrics", body)
                return (metrics.get("pir_invoked_total") or metrics.get("pir_invoked") or 0)
        except Exception:
            pass
        return None

    def _do_warmup(self, url, is_raw):
        print(f"  [预热] 发射 5 发预热弹，抛弃 I/O 冷启动与子进程唤醒惩罚...")
        payloads = []
        for _ in range(5):
            if is_raw:
                payloads.append({"query_payload": "warmup_query"})
            else:
                try:
                    t = acquire_ticket()
                    payloads.append(create_bound_request(t, "warmup_query").model_dump(mode='json'))
                except Exception as e:
                    print(f"    [警告] 预热票据获取失败: {e}")
        if payloads:
            asyncio.run(
                self._fire_requests(url, payloads, 2, is_raw, timeout=self.legit_timeout, label_timeout_as_l4=False))
        time.sleep(1)

    def run_legit_sweep(self, mode, db_size, url, is_raw):
        print(f"\n{C_CYAN}▶ 运行合法请求 Sweep | 模式: {mode}{C_RESET}")

        self._do_warmup(url, is_raw)

        results = {
            "db_size_gb": db_size,
            "dataset_mode": "emulated_with_scaling",
            "dataset_path": f"data/pir/db_{db_size}gb.bin",
            "metadata": {
                "measurement_scope": "execution_path_only",
                "ticket_prefetch": not is_raw,
                "execution_topology": self.execution_topology
            },
            "sweep_data": {}
        }
        for c in self.concurrencies:
            print(f"  并发 {c} ... 正在进行 3 轮独立采样...", end="", flush=True)

            run_req_tps_list, run_succ_tps_list, run_lat_list, run_succ_list = [], [], [], []
            run_actual_reqs_list, run_gen_fails_list = [], []  # [新增] 记录每轮实际生成和失败数
            total_outcomes_counter = Counter()

            for run_idx in range(3):
                payloads = []
                gen_fails = 0
                for _ in range(self.test_reqs):
                    if is_raw:
                        payloads.append({"query_payload": "legit_query"})
                    else:
                        try:
                            t = acquire_ticket()
                            payloads.append(create_bound_request(t, "legit_query").model_dump(mode='json'))
                        except Exception as e:
                            gen_fails += 1

                actual_reqs = len(payloads)
                run_actual_reqs_list.append(actual_reqs)
                run_gen_fails_list.append(gen_fails)

                if gen_fails > 0:
                    print(f"\n    [警告] 本轮有 {gen_fails} 个票据获取失败，实际发射量减少。")

                start_time = time.perf_counter()
                outcomes = asyncio.run(
                    self._fire_requests(url, payloads, c, is_raw, timeout=self.legit_timeout,
                                        label_timeout_as_l4=False))
                total_time = time.perf_counter() - start_time

                latencies = [lat for code, lat in outcomes if "SUCCESS" in code]
                success_count = len(latencies)

                total_outcomes_counter.update([code for code, lat in outcomes])

                req_tps = actual_reqs / total_time if total_time > 0 else 0
                success_tps = success_count / total_time if total_time > 0 else 0
                avg_lat = (sum(latencies) / success_count * 1000) if success_count > 0 else 0

                run_req_tps_list.append(req_tps)
                run_succ_tps_list.append(success_tps)
                run_lat_list.append(avg_lat)
                run_succ_list.append(success_count)
                time.sleep(0.5)

            median_req_tps = statistics.median(run_req_tps_list)
            median_succ_tps = statistics.median(run_succ_tps_list)
            median_lat = statistics.median(run_lat_list)
            avg_succ = round(sum(run_succ_list) / 3.0, 2)
            avg_actual_reqs = round(sum(run_actual_reqs_list) / 3.0, 2)

            results["sweep_data"][str(c)] = {
                "request_tps": round(median_req_tps, 2),
                "success_tps": round(median_succ_tps, 2),
                "avg_latency_ms": round(median_lat, 2),
                "success_count": avg_succ,
                "configured_requests": self.test_reqs,  # [修改 1] 改名
                "avg_actual_requests": avg_actual_reqs,  # [修改 1] 新增
                "runs_detail": {
                    "actual_requests": run_actual_reqs_list,  # [修改 2] 彻底透出每轮实发数
                    "generation_failures": run_gen_fails_list,  # [修改 2] 彻底透出每轮失败数
                    "req_tps": [round(x, 2) for x in run_req_tps_list],
                    "success_tps": [round(x, 2) for x in run_succ_tps_list],
                    "latency": [round(x, 2) for x in run_lat_list]
                },
                "total_status_distribution": dict(total_outcomes_counter)
            }
            print(f" -> Median Lat: {median_lat:.2f}ms | Median Succ TPS: {median_succ_tps:.2f}")

        return results

    def run_replay_flood(self, mode, db_size, url):
        print(f"\n{C_RED}▶ 运行【两段式】Replay 洪峰 | 模式: {mode} (洪峰总量 {self.attack_reqs}){C_RESET}")
        ticket = acquire_ticket()

        try:
            payload = create_bound_request(ticket, "flood_target").model_dump(mode='json')
        except Exception as e:
            print(f"{C_RED}[致命错误] 洪峰攻击票据获取失败，无法发起攻击: {e}{C_RESET}")
            return {}

        invocations_before = self._get_pir_invocations()

        # ==========================================
        # Stage 1: 诱导与拉黑 (触发 Derived Block)
        # ==========================================
        print(f"  [Stage 1] 发射第 1 发 (合法消费) 和第 2 发 (诱导重放拉黑)...")
        # 第 1 发：正常消费
        asyncio.run(self._fire_requests(url, [payload], 1, is_raw=False, timeout=self.legit_timeout))
        # 第 2 发：触发 L7 拦截，Verifier 会在此刻将 IP 写入 Redis 恶意名单
        asyncio.run(self._fire_requests(url, [payload], 1, is_raw=False, timeout=self.legit_timeout))

        print(f"  [冷却] 战术静默 1.5 秒，等待 tc_gateway 控制面拉取名单并下发至 eBPF 铁幕...")
        time.sleep(1.5)

        # ==========================================
        # Stage 2: 全面洪峰压制
        # ==========================================
        print(f"  [Stage 2] 发起 {self.attack_reqs} 发重放洪峰，检验 L4 拦截率...")
        payloads = [payload] * self.attack_reqs
        outcomes = asyncio.run(
            self._fire_requests(url, payloads, self.attack_concurrency, is_raw=False, timeout=self.attack_timeout,
                                label_timeout_as_l4=True))

        counts = Counter([code for code, lat in outcomes])

        print(f"  [清理] 等待 6 秒，使 eBPF L4 黑名单 TTL 到期释放本客户端 IP...")
        time.sleep(6.0)

        invocations_after = self._get_pir_invocations()

        success = counts.get("200_SUCCESS", 0)
        l7_blocked = sum(v for k, v in counts.items() if "REJECTED" in k)
        l4_blocked = counts.get("L4_TIMEOUT", 0) + counts.get("L4_CONN_ERR", 0) + counts.get("ERR", 0)

        if invocations_before is None or invocations_after is None:
            print(f"{C_YELLOW}[提示]{C_RESET} 未能提取 metrics 真实 pir_invocation，回退为 estimated。")
            actual_invocations = success
            metric_type = "estimated"
        else:
            actual_invocations = invocations_after - invocations_before
            actual_invocations = max(0, min(actual_invocations, self.attack_reqs))
            metric_type = "measured"

        reduction = ((self.attack_reqs - actual_invocations) / self.attack_reqs) * 100
        blocked_before_compute_ratio = ((self.attack_reqs - actual_invocations) / self.attack_reqs) * 100

        print(
            f"  ➜ 洪峰穿透: {success} | L7 拦截: {l7_blocked} | L4 网卡拦截: {l4_blocked} | 算力保护率: {reduction:.2f}% ({metric_type})")

        return {
            "db_size_gb": db_size,
            "dataset_mode": "emulated_with_scaling",
            "metadata": {
                "execution_topology": self.execution_topology
            },
            "attack_requests": self.attack_reqs,
            "success_count": success,
            "l7_rejected_count": l7_blocked,
            "l4_blocked_count": l4_blocked,
            "blocked_before_compute_ratio_pct": round(blocked_before_compute_ratio, 2),
            "pir_invocation_reduction_pct": round(reduction, 2),
            "reduction_metric_type": metric_type
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("server_ip", default="127.0.0.1", nargs="?")
    args = parser.parse_args()

    evaluator = DBScaleEvaluator(args.server_ip)

    # 彻底解除封印，跑满 1, 2, 4, 8 GB
    all_db_sizes = evaluator.eval_cfg.get("db_sizes_gb", [1, 2, 4, 8])
    db_sizes = all_db_sizes

    print(f"\n{C_YELLOW}🚀 [Day 57 终极决战] 开启全量测试，将执行 {db_sizes} GB 规模的主路径与洪峰防御测试！{C_RESET}")

    if evaluator.execution_topology == "local":
        print(
            f"{C_YELLOW}[拓扑预警] 脚本在本地运行 (127.0.0.1)。Full 模式下的 L4 eBPF 拦截特征可能会被弱化。推荐由外部节点发起请求。{C_RESET}")

    for size in db_sizes:
        print(f"\n{'=' * 60}")
        print(f"📦 开始测试数据库规模: {size} GB")
        print(f"{'=' * 60}")

        input(
            f"\n{C_YELLOW}[手动操作 1]{C_RESET} 请修改 base.yaml 中 dataset_path 为 db_{size}gb.bin，并重启 pir_server。完成后按回车...")

        print(f"\n{C_CYAN}--- [Phase 1: Raw PIR] ---{C_RESET}")
        input(f"{C_YELLOW}确认 pir_server 已启动。按回车开始打 Raw PIR...{C_RESET}")
        raw_res = evaluator.run_legit_sweep("Raw PIR", size, evaluator.raw_url, is_raw=True)
        with open(RESULTS_DIR / "raw" / f"db_{size}gb_raw.json", "w") as f: json.dump(raw_res, f, indent=2)

        print(f"\n{C_CYAN}--- [Phase 2: L7-only] ---{C_RESET}")
        input(
            f"{C_YELLOW}[手动操作 2] 请确保 tc_gateway.py (eBPF) 已关闭！重启 verifier 以清理状态。完成后按回车...{C_RESET}")
        l7_res = evaluator.run_legit_sweep("L7-only", size, evaluator.protected_url, is_raw=False)
        with open(RESULTS_DIR / "l7_only" / f"db_{size}gb_l7_only.json", "w") as f: json.dump(l7_res, f, indent=2)

        # 【解封】执行 L7 洪峰攻击
        l7_atk = evaluator.run_replay_flood("L7-only", size, evaluator.protected_url)
        with open(RESULTS_DIR / "attack" / f"db_{size}gb_l7_only_replay.json", "w") as f: json.dump(l7_atk, f, indent=2)

        print(f"\n{C_CYAN}--- [Phase 3: Full System] ---{C_RESET}")
        input(
            f"{C_YELLOW}[手动操作 3] ⚠️ 极度重要：先去云服务器执行 redis-cli flushall 洗白 IP！然后再启动 sudo python scripts/tc_gateway.py eth0 (开启 eBPF)！完成后按回车...{C_RESET}")
        full_res = evaluator.run_legit_sweep("Full", size, evaluator.protected_url, is_raw=False)
        with open(RESULTS_DIR / "full" / f"db_{size}gb_full.json", "w") as f: json.dump(full_res, f, indent=2)

        # 【解封】执行 Full System 终极 eBPF 洪峰攻击
        full_atk = evaluator.run_replay_flood("Full System", size, evaluator.protected_url)
        with open(RESULTS_DIR / "attack" / f"db_{size}gb_full_replay.json", "w") as f: json.dump(full_atk, f, indent=2)

    print(f"\n🎉 终极战役 {db_sizes} GB 的所有子项测试完毕！数据已落盘。")


if __name__ == "__main__":
    main()
