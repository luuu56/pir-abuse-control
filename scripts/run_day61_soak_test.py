# scripts/run_day61_soak_test.py
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
from datetime import datetime

try:
    import psutil
    import redis
except ImportError:
    print("❌ 缺少依赖！请在云服务器上执行: pip install psutil redis")
    sys.exit(1)

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket, create_bound_request

RESULTS_DIR = Path(root_path) / "results" / "soak"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
SOAK_FILE = RESULTS_DIR / "soak_8h_metrics.jsonl"

C_CYAN = '\033[96m'
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_RESET = '\033[0m'


def _generate_legit(_):
    for _ in range(3):
        try:
            t = acquire_ticket()
            return create_bound_request(t, "soak_legit_query").model_dump(mode='json')
        except Exception:
            time.sleep(0.5)
    return None


class SoakTestRunner:
    def __init__(self, duration_hours: float):
        self.config = load_config()
        self.target_ip = "127.0.0.1"
        self.url = f"http://{self.target_ip}:8002/api/v1/verifier/execute"
        self.metrics_url = f"http://{self.target_ip}:8002/api/v1/verifier/metrics"

        self.duration_hours = duration_hours

        self.round_interval_sec = 10
        self.total_rounds = int(duration_hours * 3600 / self.round_interval_sec)
        self.monitor_interval_sec = 60

        self.req_legit = 10
        self.req_rep = 3
        self.req_stale = 2
        self.req_tamp = 2
        self.concurrency = 10

        redis_cfg = self.config.get("redis", {})
        self.redis_client = redis.Redis(
            host=redis_cfg.get("host", "127.0.0.1"),
            port=redis_cfg.get("port", 6379),
            db=redis_cfg.get("db", 0),
            username=redis_cfg.get("username"),
            password=redis_cfg.get("password"),
            decode_responses=True
        )

        log_dir = Path(root_path) / self.config.get("log_dir", "logs")
        self.files_to_monitor = {
            "ledger_mb": Path(root_path) / self.config.get("auditor", {}).get("ledger_path", "logs/audit_ledger.jsonl"),
            "verifier_log_mb": log_dir / "verifier.log",
            "auditor_log_mb": log_dir / "auditor.log",
            "pir_server_log_mb": log_dir / "pir_server.log"
        }

        self.current_stats = self._reset_stats()
        self.stats_lock = threading.Lock()

        self.stop_event = threading.Event()
        self.start_time = None

    def _reset_stats(self):
        return {
            "legit_req": 0, "legit_sent": 0, "legit_succ": 0, "legit_l4": 0, "legit_conn": 0, "legit_err": 0,
            "legit_l7": 0, "legit_l7_reasons": {}, "lats": [],
            "rep_req": 0, "rep_sent": 0, "rep_l4": 0, "rep_err": 0, "rep_l7": 0, "rep_acc": 0,
            "stale_req": 0, "stale_sent": 0, "stale_l4": 0, "stale_err": 0, "stale_l7": 0, "stale_acc": 0,
            "tamp_req": 0, "tamp_sent": 0, "tamp_l4": 0, "tamp_err": 0, "tamp_l7": 0, "tamp_acc": 0,
            "degraded_rounds": 0
        }

    def _get_file_sizes(self) -> dict:
        sizes = {}
        for key, path in self.files_to_monitor.items():
            if path.exists():
                sizes[key] = round(path.stat().st_size / (1024 * 1024), 3)
            else:
                sizes[key] = 0.0
        return sizes

    def _get_redis_keys(self) -> int:
        try:
            return self.redis_client.dbsize()
        except:
            return -1

    def _get_verifier_metrics_raw(self):
        try:
            resp = requests.get(self.metrics_url, timeout=2.0)
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        return {}

    def build_batch(self):
        workload = []
        actual_legit, actual_rep, actual_stale, actual_tamp = 0, 0, 0, 0
        degraded = False

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(_generate_legit, i) for i in range(self.req_legit)]
            for f in concurrent.futures.as_completed(futures):
                res = f.result()
                if res:
                    workload.append(("legit", res))
                    actual_legit += 1
                else:
                    degraded = True

        try:
            t1 = acquire_ticket()
            p_rep = create_bound_request(t1, "soak_replay").model_dump(mode='json')
            for _ in range(self.req_rep): workload.append(("attack_replay", p_rep))
            actual_rep = self.req_rep
        except:
            degraded = True

        try:
            t2 = acquire_ticket()
            req_stale = create_bound_request(t2, "soak_stale")
            req_stale.ticket.epoch_id = 0
            for _ in range(self.req_stale): workload.append(("attack_stale", req_stale.model_dump(mode='json')))
            actual_stale = self.req_stale
        except:
            degraded = True

        try:
            t3 = acquire_ticket()
            req_tamp = create_bound_request(t3, "soak_tamper")
            req_tamp.query_payload = "tampered"
            for _ in range(self.req_tamp): workload.append(("attack_tamper", req_tamp.model_dump(mode='json')))
            actual_tamp = self.req_tamp
        except:
            degraded = True

        random.shuffle(workload)
        return workload, actual_legit, actual_rep, actual_stale, actual_tamp, degraded

    async def _fire_batch(self, workload):
        sem = asyncio.Semaphore(self.concurrency)
        outcomes = []

        async def fire(session, req_type, payload):
            start = time.perf_counter()
            async with sem:
                try:
                    async with session.post(self.url, json=payload, timeout=5.0) as resp:
                        lat = time.perf_counter() - start
                        if resp.status == 200:
                            data = await resp.json()
                            ret = req_type, lat, f"200_{data.get('decision', 'UNK')}_{data.get('reason', 'none')}"
                        else:
                            ret = req_type, lat, f"HTTP_{resp.status}"
                except asyncio.TimeoutError:
                    ret = req_type, time.perf_counter() - start, "L4_TIMEOUT"
                except aiohttp.ClientError:
                    ret = req_type, time.perf_counter() - start, "L4_CONN_ERR"
                except Exception as e:
                    ret = req_type, time.perf_counter() - start, f"ERR_{type(e).__name__}"
            outcomes.append(ret)

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=self.concurrency)) as session:
            tasks = [fire(session, t, p) for t, p in workload]
            await asyncio.gather(*tasks)

        self._parse_and_accumulate(outcomes)

    def _parse_and_accumulate(self, outcomes):
        with self.stats_lock:
            for t, lat, c in outcomes:
                if t == "legit":
                    self.current_stats["legit_sent"] += 1
                    if "SUCCESS" in c:
                        self.current_stats["legit_succ"] += 1
                        self.current_stats["lats"].append(lat)
                    elif "L4_TIMEOUT" in c:
                        self.current_stats["legit_l4"] += 1
                    elif "L4_CONN_ERR" in c:
                        self.current_stats["legit_conn"] += 1
                    elif "ERR" in c or "HTTP" in c:
                        self.current_stats["legit_err"] += 1
                    else:
                        self.current_stats["legit_l7"] += 1
                        # 记录具体的 L7 死因
                        parts = c.split('_', 2)
                        reason = parts[2] if len(parts) >= 3 else "unknown_reason"
                        self.current_stats["legit_l7_reasons"][reason] = self.current_stats["legit_l7_reasons"].get(reason, 0) + 1
                else:
                    prefix = "rep" if "replay" in t else ("stale" if "stale" in t else "tamp")
                    self.current_stats[f"{prefix}_sent"] += 1
                    if "SUCCESS" in c:
                        self.current_stats[f"{prefix}_acc"] += 1
                    elif "L4_TIMEOUT" in c:
                        self.current_stats[f"{prefix}_l4"] += 1
                    elif "ERR" in c or "HTTP" in c or "CONN" in c:
                        self.current_stats[f"{prefix}_err"] += 1
                    else:
                        self.current_stats[f"{prefix}_l7"] += 1

    def monitor_worker(self):
        init_metrics_raw = self._get_verifier_metrics_raw()
        init_body = init_metrics_raw.get("metrics", init_metrics_raw)
        pir_last = init_body.get("pir_invoked_total") or init_body.get("pir_invoked") or 0
        min_idx = 0

        while not self.stop_event.is_set():
            is_stopped = self.stop_event.wait(self.monitor_interval_sec)
            if is_stopped:
                break

            min_idx += 1
            elapsed_sec = round(time.time() - self.start_time, 2) if self.start_time else 0.0

            with self.stats_lock:
                snap = self.current_stats.copy()
                self.current_stats = self._reset_stats()

            metrics_raw = self._get_verifier_metrics_raw()
            metrics_body = metrics_raw.get("metrics", metrics_raw)
            pir_now = metrics_body.get("pir_invoked_total") or metrics_body.get("pir_invoked") or 0

            pir_diff = max(0, pir_now - pir_last)
            pir_last = pir_now

            # 严谨的 P95 计算方法
            p95 = 0.0
            if snap["lats"]:
                s_lats = sorted(snap["lats"])
                idx = max(0, min(len(s_lats) - 1, math.ceil(len(s_lats) * 0.95) - 1))
                p95 = s_lats[idx] * 1000

            legit_succ_pct = (snap['legit_succ'] / snap['legit_sent'] * 100) if snap['legit_sent'] else 0.0
            tot_att_sent = snap['rep_sent'] + snap['stale_sent'] + snap['tamp_sent']
            tot_att_l4 = snap['rep_l4'] + snap['stale_l4'] + snap['tamp_l4']
            tot_att_acc = snap['rep_acc'] + snap['stale_acc'] + snap['tamp_acc']

            att_l4_proxy_pct = (tot_att_l4 / tot_att_sent * 100) if tot_att_sent else 0.0
            att_nonacc_pct = ((tot_att_sent - tot_att_acc) / tot_att_sent * 100) if tot_att_sent else 0.0

            record = {
                "timestamp": datetime.now().isoformat(),
                "minute": min_idx,
                "elapsed_sec": elapsed_sec,
                "host_cpu_pct": psutil.cpu_percent(interval=None),
                "host_mem_pct": psutil.virtual_memory().percent,
                "redis_dbsize": self._get_redis_keys(),
                "file_sizes": self._get_file_sizes(),
                "pir_invocations_min": pir_diff,
                "degraded_rounds": snap["degraded_rounds"],
                "verifier_metrics_raw": metrics_raw,
                "derived_metrics": {
                    "legit_success_rate_pct": round(legit_succ_pct, 2),
                    "attack_nonaccepted_rate_pct": round(att_nonacc_pct, 2),
                    "attack_l4_proxy_rate_pct": round(att_l4_proxy_pct, 2),
                    "p95_latency_ms": round(p95, 2)
                },
                "traffic": {
                    "legit": {
                        "req": snap["legit_req"], 
                        "sent": snap["legit_sent"], 
                        "succ": snap["legit_succ"],
                        "l4": snap["legit_l4"], 
                        "conn": snap["legit_conn"], 
                        "err": snap["legit_err"],
                        "l7": snap["legit_l7"],
                        "l7_reasons": snap["legit_l7_reasons"]  # <--- ✅ 铁证落盘！
                    },
                    "replay": {"req": snap["rep_req"], "sent": snap["rep_sent"], "l4": snap["rep_l4"],
                               "err": snap["rep_err"], "l7": snap["rep_l7"], "acc": snap["rep_acc"]},
                    "stale": {"req": snap["stale_req"], "sent": snap["stale_sent"], "l4": snap["stale_l4"],
                              "err": snap["stale_err"], "l7": snap["stale_l7"], "acc": snap["stale_acc"]},
                    "tamper": {"req": snap["tamp_req"], "sent": snap["tamp_sent"], "l4": snap["tamp_l4"],
                               "err": snap["tamp_err"], "l7": snap["tamp_l7"], "acc": snap["tamp_acc"]}
                }
            }

            with open(SOAK_FILE, "a") as f:
                f.write(json.dumps(record) + "\n")

            ledger_mb = record["file_sizes"].get("ledger_mb", 0.0)
            sys.stdout.write(f"\n[{datetime.now().strftime('%H:%M:%S')}] T+{min_idx}m | Legit Succ: {legit_succ_pct:5.1f}% | P95: {p95:6.1f}ms | Redis Keys: {record['redis_dbsize']} | Ledger: {ledger_mb} MB\n")
            
            # 若 Legit 出现战损，立刻打印高亮死因
            if snap["legit_l7"] > 0:
                reasons_str = json.dumps(snap["legit_l7_reasons"], ensure_ascii=False)
                sys.stdout.write(f"    {C_RED}⚠️ [战损警报] 合法请求遭 L7 拦截! 死因: {reasons_str}{C_RESET}\n")
            sys.stdout.flush()

    def run(self):
        print(f"\n{C_CYAN}🌊 [Day 61] 启动 {self.duration_hours} 小时全链路服务态浸泡测试 (End-to-End Soak Test){C_RESET}")
        print("⚠️  学术界定: This configuration evaluates End-to-End Service-State Longevity under continuous light mixed traffic.")
        print("   - Testing scope: Issuer (Admission/Sign), Verifier (L7/State), PIR Engine, Auditor, Redis.")
        print("   - Network scope: Loopback-hosted (127.0.0.1), focusing on internal resource leakage and state drift.")
        print(f"➜ 目标文件: {SOAK_FILE}\n")

        if SOAK_FILE.exists(): SOAK_FILE.unlink()

        metadata = {
            "_type": "metadata",
            "timestamp": datetime.now().isoformat(),
            "duration_hours": self.duration_hours,
            "mode_metadata": {
                "target_scope": "end-to-end service-state stability (Issuer included)",
                "tc_gateway_expected": False,
                "network_path_scope": "loopback-only (not external)"
            },
            "target_ip": self.target_ip,
            "round_interval_sec": self.round_interval_sec,
            "total_rounds": self.total_rounds,
            "batch_mix": {"legit": self.req_legit, "replay": self.req_rep, "stale": self.req_stale,
                          "tamper": self.req_tamp},
            "concurrency": self.concurrency
        }
        with open(SOAK_FILE, "w") as f:
            f.write(json.dumps(metadata) + "\n")

        monitor_thread = threading.Thread(target=self.monitor_worker, daemon=True)
        self.start_time = time.time()
        monitor_thread.start()

        try:
            for i in range(self.total_rounds):
                loop_start = time.time()

                # 进度条
                pct = int((i + 1) / self.total_rounds * 100)
                bar = "█" * (pct // 2) + "-" * (50 - pct // 2)
                sys.stdout.write(f"\r  [浸泡进度] [{bar}] 轮次:{i+1}/{self.total_rounds} ({pct}%) ")
                sys.stdout.flush()

                workload, l, r, s, t, deg = self.build_batch()

                with self.stats_lock:
                    if deg: self.current_stats["degraded_rounds"] += 1
                    self.current_stats["legit_req"] += self.req_legit
                    self.current_stats["rep_req"] += self.req_rep
                    self.current_stats["stale_req"] += self.req_stale
                    self.current_stats["tamp_req"] += self.req_tamp

                asyncio.run(self._fire_batch(workload))

                elapsed = time.time() - loop_start
                if elapsed < self.round_interval_sec:
                    time.sleep(self.round_interval_sec - elapsed)

        except KeyboardInterrupt:
            print(f"\n\n{C_YELLOW}⚠️  测试被手动提前终止！{C_RESET}")
        finally:
            self.stop_event.set()
            monitor_thread.join()
            print(f"\n🎉 浸泡测试结束！时序快照已安全落盘至: {SOAK_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=0.5, help="Soak test duration in hours (default: 0.5)")
    args = parser.parse_args()

    runner = SoakTestRunner(duration_hours=args.hours)
    runner.run()