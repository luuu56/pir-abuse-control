# scripts/aggregate_day57_dbscale.py
import json
import csv
from pathlib import Path

def main():
    root_path = Path(__file__).resolve().parent.parent
    results_dir = root_path / "results" / "dbscale"
    agg_dir = results_dir / "aggregated"
    agg_dir.mkdir(exist_ok=True, parents=True)

    sizes = [1, 2, 4, 8]

    # ==========================================
    # 1. 聚合主路径并发性能 (Legit Sweep)
    # ==========================================
    perf_csv = agg_dir / "dbscale_by_concurrency.csv"
    with open(perf_csv, "w", newline="") as f:
        writer = csv.writer(f)
        # 提取中位数 TPS 和 Latency
        writer.writerow(["DB_Size_GB", "Mode", "Concurrency", "Success_TPS", "Avg_Latency_ms"])

        for size in sizes:
            for mode_dir, mode_name in [("raw", "raw"), ("l7_only", "l7_only"), ("full", "full")]:
                json_path = results_dir / mode_dir / f"db_{size}gb_{mode_dir}.json"
                if json_path.exists():
                    try:
                        with open(json_path, "r") as jf:
                            data = json.load(jf)
                            sweep_data = data.get("sweep_data", {})
                            for c_str, metrics in sweep_data.items():
                                writer.writerow([
                                    size,
                                    mode_name,
                                    c_str,
                                    metrics.get("success_tps", 0),
                                    metrics.get("avg_latency_ms", 0)
                                ])
                    except Exception as e:
                        print(f"解析 {json_path} 时出错: {e}")

    # ==========================================
    # 2. 聚合防御拦截率与纵深拆解 (Attack Replay)
    # ==========================================
    prot_csv = agg_dir / "dbscale_protection.csv"
    with open(prot_csv, "w", newline="") as f:
        writer = csv.writer(f)
        # 【升级】追加 L7 和 L4 的具体拦截数量，为论文图表提供子弹！
        writer.writerow([
            "DB_Size_GB",
            "Mode",
            "Total_Attack_Reqs",
            "Success_Penetrated",
            "L7_Blocked",
            "L4_Blocked",
            "PIR_Invocation_Reduction_Pct",
            "Reduction_Metric_Type"
        ])

        for size in sizes:
            for mode_dir, mode_name in [("attack", "l7_only"), ("attack", "full")]:
                # 寻找对应的 replay 文件
                json_path = results_dir / "attack" / f"db_{size}gb_{mode_name}_replay.json"
                if json_path.exists():
                    try:
                        with open(json_path, "r") as jf:
                            data = json.load(jf)
                            writer.writerow([
                                size,
                                mode_name,
                                data.get("attack_requests", 0),
                                data.get("success_count", 0),
                                data.get("l7_rejected_count", 0),
                                data.get("l4_blocked_count", 0),
                                data.get("pir_invocation_reduction_pct", 0),
                                data.get("reduction_metric_type", "unknown")
                            ])
                    except Exception as e:
                        print(f"解析 {json_path} 时出错: {e}")

    print(f"✅ 聚合完成！数据已保存至: {agg_dir}")
    print(f"  ➜ 性能文件: {perf_csv.name}")
    print(f"  ➜ 防御文件: {prot_csv.name}")

if __name__ == "__main__":
    main()