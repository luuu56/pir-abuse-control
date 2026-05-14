# scripts/run_day62_microbenchmarks.py
import sys
import time
import json
import statistics
import math
import hashlib
import os
import datetime
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

C_CYAN = '\033[96m'
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RESET = '\033[0m'

ITERATIONS_POW = 2000

def summarize(latencies):
    s = sorted(latencies)
    def pct(p):
        idx = max(0, min(len(s) - 1, math.ceil(len(s) * p) - 1))
        return s[idx]
    return {
        "avg_us": statistics.mean(s),
        "median_us": statistics.median(s),
        "p95_us": pct(0.95),
        "p99_us": pct(0.99),
        "min_us": s[0],
        "max_us": s[-1],
        "std_us": statistics.pstdev(s),
        "iterations": len(s),
        "unit": "microseconds"
    }

def run_microbenchmarks():
    print(f"\n{C_CYAN}⏱️  [Day 62-E] 原语开销评估: PoW 概率分布与历史 JSON 整合{C_RESET}")
    
    input_file = root_path / "results" / "microbenchmarks" / "microbenchmarks_primitives.json"
    results = {}
    if input_file.exists():
        print(f"  [读取] 找到之前的测试记录: {input_file.name}")
        # 【细节优化 2】：加入 encoding="utf-8" 保证多平台兼容
        with open(input_file, 'r', encoding="utf-8") as f:
            results = json.load(f)
    else:
        print(f"  {C_YELLOW}[警告] 未找到原始记录，将只生成 PoW 数据{C_RESET}")

    results.setdefault("metadata", {})
    results["metadata"]["iterations_pow"] = ITERATIONS_POW
    results["metadata"]["pow_difficulty"] = "8-bit prefix, sha256 hex startswith('00')"
    results["metadata"]["day62_timestamp"] = datetime.datetime.now().isoformat()
    
    # 【细节优化 3】：更精准的 Measurement Scope 描述
    results["metadata"]["measurement_scope_day62"] = (
        "PoW solve is measured as client-side admission cost; "
        "other primitives are inherited from in-process cryptographic "
        "and state-machine microbenchmarks. HTTP, serialization, and PIR backend are excluded."
    )

    print("  [计算] 正在进行 PoW (8-bit difficulty) 测试及 Hash Trials 统计...")
    pow_lats = []
    pow_trials = []
    
    for i in range(ITERATIONS_POW):
        challenge = os.urandom(16) + i.to_bytes(8, "big")
        start = time.perf_counter()
        nonce = 0
        while True:
            h = hashlib.sha256(challenge + nonce.to_bytes(8, 'big')).hexdigest()
            if h.startswith('00'): break
            nonce += 1
            
        pow_lats.append((time.perf_counter() - start) * 1_000_000)
        # 【细节优化 1】：保存每次求解需要的 Hash 尝试次数
        pow_trials.append(nonce + 1)
    
    results["pow_solve_us"] = summarize(pow_lats)
    # 将 Trials 分布加入结果
    results["pow_solve_us"]["avg_hash_trials"] = statistics.mean(pow_trials)
    results["pow_solve_us"]["median_hash_trials"] = statistics.median(pow_trials)
    
    sorted_trials = sorted(pow_trials)
    results["pow_solve_us"]["p95_hash_trials"] = sorted_trials[max(0, math.ceil(len(sorted_trials) * 0.95) - 1)]
    results["pow_solve_us"]["p99_hash_trials"] = sorted_trials[max(0, math.ceil(len(sorted_trials) * 0.99) - 1)]

    out_dir = root_path / "results" / "microbenchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "microbenchmarks_primitives_final.json"
    
    # 【细节优化 2】：加入 encoding="utf-8" 保证持久化不乱码
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    display_names = {
        "pow_solve_us": "PoW solve",
        "blind_issue_sign_us": "Blind issue",
        "unblind_us": "Unblind",
        "ticket_verify_us": "Signature verify",
        "binding_generate_us": "Binding generation",
        "binding_verify_us": "Binding verify",
        "atomic_reservation_success_us": "Redis SETNX success",
        "atomic_reservation_reject_us": "Redis SETNX reject"
    }

    keys_order = [
        "pow_solve_us",
        "blind_issue_sign_us",
        "unblind_us",
        "ticket_verify_us",
        "binding_generate_us",
        "binding_verify_us",
        "atomic_reservation_success_us",
        "atomic_reservation_reject_us"
    ]

    print("\n" + "=" * 100)
    print(f"{C_GREEN}🏆 原语微基准完成！结果简报 (单位: 微秒 μs){C_RESET}")
    print(f"{'Primitive Metric':<30} | {'Median (μs)':<12} | {'P95 (μs)':<12} | {'P99 (μs)':<12} | {'Avg Hash Trials':<15}")
    print("-" * 100)
    
    for k in keys_order:
        if k in results:
            d = results[k]
            name = display_names.get(k, k)
            trials_str = f"{d.get('avg_hash_trials', 'N/A'):<15.1f}" if k == "pow_solve_us" else f"{'N/A':<15}"
            print(f"{name:<30} | {d['median_us']:<12.2f} | {d['p95_us']:<12.2f} | {d['p99_us']:<12.2f} | {trials_str}")
    
    print("=" * 100)
    print(f"📁 最终论文原语开销表已落盘至: {out_file}")

if __name__ == "__main__":
    run_microbenchmarks()