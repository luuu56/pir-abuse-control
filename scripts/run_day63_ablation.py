# scripts/run_day63_ablation.py
import sys
import time
import json
import asyncio
import math
import requests
from pathlib import Path

try:
    import aiohttp
    import yaml
except ImportError:
    print("❌ 缺少必要依赖！请运行: pip install aiohttp pyyaml")
    sys.exit(1)

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from services.client.main import acquire_ticket, create_bound_request

C_CYAN = '\033[96m'
C_GREEN = '\033[92m'
C_RED = '\033[91m'
C_YELLOW = '\033[93m'
C_RESET = '\033[0m'

TARGET_IP = "127.0.0.1"
VERIFIER_METRICS_URL = f"http://{TARGET_IP}:8002/api/v1/verifier/metrics"
VERIFIER_URL = f"http://{TARGET_IP}:8002/api/v1/verifier/execute"
YAML_PATH = root_path / "configs" / "common" / "base.yaml"

CONCURRENCY_FLOOD = 50
HONEST_COUNT = 10

def update_yaml_ablation(disable_binding=False, disable_consume_lock=False, ebpf_expected=True):
    """动态修改配置并显式提示环境清理要求"""
    try:
        with open(YAML_PATH, 'r') as f:
            config = yaml.safe_load(f)
        
        if "ablation" not in config:
            config["ablation"] = {}
            
        config["ablation"]["disable_binding"] = disable_binding
        config["ablation"]["disable_consume_lock"] = disable_consume_lock
        
        with open(YAML_PATH, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
            
        print(f"\n{C_YELLOW}🔧 [配置变更]: Binding={not disable_binding}, StateLock={not disable_consume_lock}{C_RESET}")
        print(f"{C_YELLOW}🛡️ [eBPF 预期状态]: {'需开启 tc_gateway.py' if ebpf_expected else '需关闭 tc_gateway.py'}{C_RESET}")
        
        print(f"\n{C_RED}👉 请按要求执行以下环境清理操作以确保物理隔离：\n"
              f"   1. 执行 `redis-cli flushdb` 清理状态残留\n"
              f"   2. 重启 tc_gateway.py (若当前配置要求开启)\n"
              f"   3. 重启 Verifier 服务进程\n"
              f"   4. 确保当前测试机 IP 未处于上一轮 eBPF 的封禁 TTL 内\n"
              f"确认环境纯净且就绪后，按 Enter 开始本轮测试...{C_RESET}")
        input()
    except Exception as e:
        print(f"❌ 修改 YAML 失败: {e}")
        sys.exit(1)

def get_verifier_metrics():
    try:
        body = requests.get(VERIFIER_METRICS_URL, timeout=2).json()
        return body.get("metrics", body)
    except Exception:
        return {
            "total_requests": 0,
            "blocked_before_pir": 0,
            "pir_invoked": 0,
            "pir_invoked_total": 0
        }

def pir_count(m):
    return m.get("pir_invoked_total") or m.get("pir_invoked") or 0

async def fire_req(session, payload):
    start_time = time.perf_counter()
    try:
        async with session.post(VERIFIER_URL, json=payload, timeout=5.0) as resp:
            latency = (time.perf_counter() - start_time) * 1000
            try:
                resp_json = await resp.json()
                return "L7_OK", resp_json.get("decision"), latency
            except:
                return "L7_ERR_JSON", "UNKNOWN", latency
    except asyncio.TimeoutError:
        return "L4_STYLE_TIMEOUT", "TIMEOUT", (time.perf_counter() - start_time) * 1000
    except aiohttp.ClientError:
        return "L4_STYLE_CONN_ERR", "CONN_ERR", (time.perf_counter() - start_time) * 1000
    except Exception as e:
        return "ERROR", str(e), 0

async def run_ablation_scenario(name: str, attack_type: str, ebpf_expected: bool):
    print(f"\n{C_CYAN}▶ Scenario: {name} ({attack_type.upper()}){C_RESET}")
    
    m_start = get_verifier_metrics()
    
    results = {
        "scenario": name, 
        "attack_type": attack_type,
        "isolation_note": "w/o State Lock disables eBPF to expose verifier-state vulnerability" if name == "w/o State Lock" else "",
        "honest_success": 0, "honest_latencies": [],
        "attack_success": 0, "l7_reject": 0, "l4_drop": 0, 
        "setup_pir_hits": 0, "attack_pir_hits": 0
    }

    # ==========================
    # 阶段 1: Honest Baseline
    # ==========================
    async with aiohttp.ClientSession() as session:
        for _ in range(HONEST_COUNT):
            try:
                t = acquire_ticket()
                req = create_bound_request(t, f"honest_{time.time()}")
                status, decision, lat = await fire_req(session, req.model_dump(mode='json'))
                if decision == "SUCCESS":
                    results["honest_success"] += 1
                    results["honest_latencies"].append(lat)
            except: pass

    m_after_honest = get_verifier_metrics()

    # ==========================
    # 阶段 2: 攻击 Setup 
    # ==========================
    async with aiohttp.ClientSession() as session:
        t_mal = acquire_ticket()
        req_mal = create_bound_request(t_mal, "attack_payload")
        payload = req_mal.model_dump(mode='json')

        if attack_type == "replay":
            print("  ➜ [Setup] 核销母票并触发 L4 Block...")
            await fire_req(session, payload) 
            await fire_req(session, payload) 
            print("  ➜ [Wait] 等待 1.5s 让 eBPF 规则生效...")
            await asyncio.sleep(1.5)         
        elif attack_type == "tamper":
            payload["query_payload"] = "TAMPERED_MALICIOUS_QUERY"

    m_setup = get_verifier_metrics()
    results["setup_pir_hits"] = pir_count(m_setup) - pir_count(m_after_honest)

    # ==========================
    # 阶段 3: Flood Attack 洪峰
    # ==========================
    print(f"  ➜ [Flood] 注入 {CONCURRENCY_FLOOD} 发并发攻击...")
    async with aiohttp.ClientSession() as session:
        tasks = [fire_req(session, payload) for _ in range(CONCURRENCY_FLOOD)]
        responses = await asyncio.gather(*tasks)
        
        for status, decision, _ in responses:
            if status == "L7_OK":
                if decision == "SUCCESS": results["attack_success"] += 1
                elif decision == "REJECTED": results["l7_reject"] += 1
            elif "L4_STYLE" in status:
                results["l4_drop"] += 1

    m_final = get_verifier_metrics()
    results["attack_pir_hits"] = pir_count(m_final) - pir_count(m_setup)
    
    # === 统计计算 ===
    if results["honest_latencies"]:
        s = sorted(results["honest_latencies"])
        results["p95_ms"] = s[max(0, min(len(s)-1, math.ceil(len(s)*0.95)-1))]
    else: results["p95_ms"] = -1

    results["attack_success_rate_pct"] = (results["attack_success"] / CONCURRENCY_FLOOD) * 100
    results["l7_reject_rate_pct"] = (results["l7_reject"] / CONCURRENCY_FLOOD) * 100
    results["l4_drop_rate_pct"] = (results["l4_drop"] / CONCURRENCY_FLOOD) * 100
    results["honest_success_rate_pct"] = (results["honest_success"] / HONEST_COUNT) * 100

    return results

async def main():
    with open(YAML_PATH, "r") as f: original_yaml = f.read()
    all_results = []
    
    # 定义执行矩阵，自动绑定 Ablation Flags
    scenarios = [
        {"name": "Baseline (Tamper)", "type": "tamper", "bind": False, "state": False, "ebpf": True},
        {"name": "Baseline (Replay)", "type": "replay", "bind": False, "state": False, "ebpf": True},
        {"name": "w/o Crypto Binding", "type": "tamper", "bind": True, "state": False, "ebpf": False},
        {"name": "w/o State Lock", "type": "replay", "bind": False, "state": True, "ebpf": False},
        {"name": "w/o eBPF Fast Path", "type": "replay", "bind": False, "state": False, "ebpf": False},
    ]

    try:
        for s in scenarios:
            print(f"\n{C_YELLOW}[配置变更] 准备执行: {s['name']}{C_RESET}")
            update_yaml_ablation(disable_binding=s["bind"], disable_consume_lock=s["state"], ebpf_expected=s["ebpf"])
            
            res = await run_ablation_scenario(s["name"], s["type"], s["ebpf"])
            
            # 【核心补充】写入硬核的审计 Flags
            res["ablation_flags"] = {
                "disable_binding": s["bind"],
                "disable_consume_lock": s["state"],
                "tc_gateway_expected": s["ebpf"]
            }
            all_results.append(res)

    finally:
        print(f"\n{C_GREEN}🧹 正在物理恢复原始 base.yaml 配置...{C_RESET}")
        with open(YAML_PATH, "w") as f: f.write(original_yaml)

    # 最终结果落盘
    out_dir = root_path / "results" / "ablation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "verifier_side_ablation.json"
    
    with open(out_file, "w") as f:
        json.dump({
            "metadata": {
                "target_ip": TARGET_IP,
                "concurrency_flood": CONCURRENCY_FLOOD,
                "honest_count": HONEST_COUNT,
                "note": "L4 Drop is a client-observed L4-style timeout/connection proxy. Setup PIR hits represent honest ticket consumption prior to flood.",
                "manual_restart_required": True
            },
            "results": all_results
        }, f, indent=4)

    # 打印 OSDI 级表格
    print("\n" + "=" * 115)
    print(f"{C_GREEN}🏆 Table 3: Verifier-side Defenses Ablation Study (N_flood={CONCURRENCY_FLOOD}){C_RESET}")
    print(f"{'Configuration':<25} | {'Workload':<8} | {'Accepted':<10} | {'PIR Hits':<10} | {'L7 Rej':<8} | {'L4 Drop*':<10} | {'P95 (ms)'}")
    print("-" * 115)
    for r in all_results:
        acc_str = f"{r['attack_success_rate_pct']:.1f}%"
        p95 = f"{r['p95_ms']:.1f}" if r['p95_ms'] != -1 else "TIMEOUT"
        print(f"{r['scenario']:<25} | {r['attack_type']:<8} | {acc_str:<10} | {r['attack_pir_hits']:<10} | {r['l7_reject']:<8} | {r['l4_drop']:<10} | {p95}")
    print("=" * 115)
    print("* L4 Drop indicates L4-style drop/timeout proxy observed at client-side.")
    print(f"📁 详细学术证据已落盘至: {out_file}")

if __name__ == "__main__":
    asyncio.run(main())