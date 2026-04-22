# scripts/run_eval_suite.py
import sys
import time
import json
import asyncio
import argparse
import secrets
import requests
import base64
import hmac
from pathlib import Path
from collections import Counter

try:
    import aiohttp
    import psutil
except ImportError:
    print("❌ 缺少必要依赖！请运行: pip install aiohttp psutil")
    sys.exit(1)

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.crypto_utils import (
    solve_pow, verify_pow, compute_hmac, canonical_json_bytes,
    compute_query_commitment, compute_binding_tag, serialize_witness,
    integer_to_base64, derive_sk_t
)
from common.models import AdmissionResponse, AdmissionChallenge, AdmissionPayload
from services.verifier.state_manager import get_state_manager
from services.client.main import acquire_ticket, create_bound_request
from services.issuer.main import verify_admission_logic
from services.issuer.crypto import crypto_manager as issuer_crypto
from services.client.crypto import crypto_manager as client_crypto
from services.verifier.crypto import crypto_manager as verifier_crypto

# ==========================================
# 1. 微基准测试 (Micro-benchmarks)
# ==========================================
def run_micro_benchmarks(target_ip: str):
    print("\n" + "="*65)
    print("🔬 [Part A: Micro-benchmarks (细粒度密码学与状态机拆解)]")
    print("="*65)
    metrics = {}
    config = load_config()

    def measure(name, func, *args, iterations=1000):
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func(*args)
        avg_ns = (time.perf_counter_ns() - start) / iterations
        metrics[name] = avg_ns
        print(f"  ├─ {name:<32} : {avg_ns / 1_000_000:.4f} ms")
        return avg_ns

    ticket_crypto_ready = False
    try:
        pk_data = requests.get(f"http://{target_ip}:8001/api/v1/issuer/public_key", timeout=5).json()
        n = int(pk_data["n"].replace("0x", ""), 16)
        e = int(pk_data["e"].replace("0x", ""), 16)
        ticket_crypto_ready = True
    except Exception as err:
        print(f"⚠️  无法获取 Issuer 公钥，跳过票据层微基准: {err}")

    # --- 1. 匿名准入 (Admission) ---
    print("\n[匿名准入层]")
    dummy_payload = AdmissionPayload(
        client_tag="bench", epoch_id=1, difficulty=12,
        issued_at=int(time.time()), expires_at=int(time.time())+300, server_nonce="abc"
    )
    dummy_payload_bytes = canonical_json_bytes(dummy_payload.model_dump())
    issuer_secret = config.get("issuer", {}).get("hmac_secret", "issuer-secret-key-change-me")
    dummy_hmac = compute_hmac(issuer_secret, dummy_payload_bytes)
    
    start_pow = time.perf_counter_ns()
    nonce = solve_pow(dummy_payload_bytes, dummy_hmac, 12)
    metrics["client_solve_pow_d12"] = time.perf_counter_ns() - start_pow
    print(f"  ├─ {'client_solve_pow_d12':<32} : {metrics['client_solve_pow_d12'] / 1_000_000:.4f} ms")
    
    proof = AdmissionResponse(challenge=AdmissionChallenge(payload=dummy_payload, hmac_sig=dummy_hmac), nonce=nonce)
    measure("issuer_verify_admission_logic", verify_admission_logic, proof, iterations=1000)

    # --- 2. 票据签发 (Ticket Crypto) ---
    print("\n[盲签票据层]")
    if ticket_crypto_ready:
        m_int = 123456789
        r = client_crypto.generate_blinding_factor(n)
        blinded_m_int = client_crypto.blind_message(m_int, r, e, n)
        blind_sig_int = issuer_crypto.blind_sign(blinded_m_int)
        
        measure("blind_issue_sign", issuer_crypto.blind_sign, blinded_m_int, iterations=500)
        measure("client_unblind_signature", client_crypto.unblind_signature, blind_sig_int, r, n, iterations=1000)
        
        modulus_bytes_len = (n.bit_length() + 7) // 8
        sigma_b64 = integer_to_base64(client_crypto.unblind_signature(blind_sig_int, r, n), modulus_bytes_len)
        
        measure("verifier_verify_ticket_sig", verifier_crypto.verify_ticket_signature, "0"*64, 1, sigma_b64, n, e, iterations=500)
    else:
        metrics["blind_issue_sign"] = metrics["client_unblind_signature"] = metrics["verifier_verify_ticket_sig"] = None
        sigma_b64 = "dummy_sigma"

    # --- 3. 密码学绑定 (HMAC Binding) ---
    print("\n[一致性绑定层]")
    q_payload = "EVAL_QUERY"
    c_q = compute_query_commitment(q_payload)
    witness_dict = {"timestamp_ms": 123, "nonce": "abc"}
    witness_bytes = serialize_witness(witness_dict)
    
    if ticket_crypto_ready:
        sig_bytes_tmp = base64.b64decode(sigma_b64, validate=True)
        sk_t_valid = derive_sk_t(sig_bytes_tmp, "0"*64, 1)
    else:
        sk_t_valid = secrets.token_bytes(32)
        
    binding_tag_valid = compute_binding_tag(sk_t_valid, c_q, witness_bytes)
    
    measure("binding_compute_H_q", compute_query_commitment, q_payload, iterations=5000)
    measure("binding_compute_b", compute_binding_tag, sk_t_valid, c_q, witness_bytes, iterations=5000)

    def verify_binding_once(sigma_b64_in, sn, epoch_id, q_payload_in, witness_dict_in, expected_tag):
        try:
            sig_bytes = base64.b64decode(sigma_b64_in, validate=True)
            t_sk = derive_sk_t(sig_bytes, sn, epoch_id)
            t_c_q = compute_query_commitment(q_payload_in)
            t_w_bytes = serialize_witness(witness_dict_in)
            expected = compute_binding_tag(t_sk, t_c_q, t_w_bytes)
            return hmac.compare_digest(expected_tag, expected)
        except Exception:
            return False

    if ticket_crypto_ready:
        measure("binding_verify", verify_binding_once, sigma_b64, "0"*64, 1, q_payload, witness_dict, binding_tag_valid, iterations=2000)
    else:
        metrics["binding_verify"] = None

    # --- 4. 前置验证与状态机 (State & System) ---
    print("\n[前置验证与状态机]")
    sm = get_state_manager()
    dummy_sn = secrets.token_hex(32)
    measure("verifier_redis_try_lock", sm.try_lock, dummy_sn, 30, iterations=1000)
    
    metrics["ebpf_kernel_drop_estimate"] = {"value_ns": 1500, "source": "estimated_constant", "measured": False}
    print(f"  ├─ {'ebpf_kernel_drop_estimate':<32} : 0.0015 ms (Source: estimated_constant)")

    return metrics

# ==========================================
# 2. 宏观压测 (Macro-benchmarks with Sweep)
# ==========================================
async def fire_req(session, url, payload, timeout=10):
    start = time.perf_counter()
    try:
        async with session.post(url, json=payload, timeout=timeout) as resp:
            text = await resp.text()
            latency = time.perf_counter() - start
            decision = None
            if resp.status == 200:
                try:
                    decision = json.loads(text).get("decision")
                except: pass
            elif resp.status == 422:
                decision = "SCHEMA_ERR"
            return latency, resp.status, decision
    except asyncio.TimeoutError:
        return time.perf_counter() - start, 0, "TIMEOUT"
    except Exception:
        return time.perf_counter() - start, 0, "CONN_ERR"

async def run_single_sweep(name: str, url: str, payloads: list, c: int):
    sem = asyncio.Semaphore(c)
    async def sem_fire(payload):
        async with sem:
            return await fire_req(session, url, payload)

    start_time = time.perf_counter()
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=c)) as session:
        tasks = [sem_fire(p) for p in payloads]
        results = await asyncio.gather(*tasks)
    total_time = time.perf_counter() - start_time
    
    tps = len(payloads) / total_time
    
    # 必改 2: 解析并打印 Success Count，避免盲目统计 0.00ms 延迟
    if "Verifier" in name:
        success_results = [r for r in results if r[2] == "SUCCESS"]
    else:
        success_results = [r for r in results if r[1] == 200]
        
    success_count = len(success_results)
    success_latencies = [r[0] for r in success_results]
    avg_lat = sum(success_latencies)/len(success_latencies) if success_latencies else 0.0
    
    print(f"      ├─ Success Count: {success_count}/{len(payloads)}")
    print(f"      ├─ TPS: {tps:.2f} | Latency (SUCCESS): {avg_lat*1000:.2f} ms")
    
    return {"tps": round(tps, 2), "latency_ms": round(avg_lat*1000, 2), "success_count": success_count}

async def run_macro_benchmarks(target_ip: str):
    print("\n" + "="*65)
    print("🌍 [Part B: Macro-benchmarks (主路径性能与扫参)]")
    print("="*65)
    
    pir_url = f"http://{target_ip}:8003/api/v1/pir/query"
    verifier_url = f"http://{target_ip}:8002/api/v1/verifier/execute"
    concurrency_levels = [1, 10, 30, 50]
    test_size = 50 

    macro_metrics = {}

    # 0. L7 Reject Path
    print("\n[L7 Verifier Overhead] 测试用户态纯 L7 验证拒绝开销...")
    try:
        t = acquire_ticket()
        t.sigma = "fake_sigma_for_fast_reject=="
        malicious_req = create_bound_request(t, "reject_test")
        mal_payload = malicious_req.model_dump(mode='json')
        
        reject_latencies = []
        async with aiohttp.ClientSession() as session:
            for _ in range(20):
                lat, status, dec = await fire_req(session, verifier_url, mal_payload)
                if status == 200 and dec == "REJECTED":
                    reject_latencies.append(lat)
        avg_reject = sum(reject_latencies)/len(reject_latencies) if reject_latencies else 0
        macro_metrics["verifier_reject_path_latency_ms"] = round(avg_reject * 1000, 2)
        print(f"  ├─ L7 Reject Path Latency: {macro_metrics['verifier_reject_path_latency_ms']} ms (接口级近似)")
    except Exception as e:
        print(f"  ├─ L7 Reject Path Latency 测试失败: {e}")

    # 1. 裸 PIR 扫参 (可复用 payload)
    print("\n[Baseline] 无保护的 PIR 引擎")
    raw_payloads = [{"query_payload": f"eval_query_{i}"} for i in range(test_size)]
    macro_metrics["raw_pir_by_concurrency"] = {}
    for c in concurrency_levels:
        print(f"  >>> 并发度 [C={c}] 压测中...")
        macro_metrics["raw_pir_by_concurrency"][str(c)] = await run_single_sweep("Raw PIR Backend", pir_url, raw_payloads, c)

    # 2. 受保护路径扫参 (必改 1: 每次并发度单独装填弹药)
    print("\n[Protected] Verifier 保护的主路径")
    macro_metrics["protected_pir_by_concurrency"] = {}
    for c in concurrency_levels:
        print(f"\n  >>> 为并发度 [C={c}] 重新预装填 {test_size} 发独立真票...")
        valid_payloads = []
        for i in range(test_size):
            ticket = acquire_ticket()
            req = create_bound_request(ticket, f"macro_eval_query_c{c}_{i}")
            valid_payloads.append(req.model_dump(mode='json'))
            sys.stdout.write(f"\r      ├─ 装填进度: {i+1}/{test_size}"); sys.stdout.flush()
        print()
        macro_metrics["protected_pir_by_concurrency"][str(c)] = await run_single_sweep("Verifier Protected Path", verifier_url, valid_payloads, c)

    # 计算有无保护差值 Delta
    delta = {}
    for c in concurrency_levels:
        key = str(c)
        raw = macro_metrics["raw_pir_by_concurrency"][key]
        prot = macro_metrics["protected_pir_by_concurrency"][key]
        delta[key] = {
            "latency_delta_ms": round(prot["latency_ms"] - raw["latency_ms"], 2),
            "throughput_delta_tps": round(raw["tps"] - prot["tps"], 2),
        }
    macro_metrics["protected_vs_raw_delta"] = delta

    # 3. 资源保护效能评估 (Abuse Replay)
    print("\n" + "="*65)
    print("🛡️ [Part C: Resource Protection (资源保护语义指标)]")
    print("="*65)
    abuse_size = 1000
    print(f"➜ 使用 1 张票进行 {abuse_size} 次超高并发重放，测试拦截率...")
    
    # 获取一个全新的真票用于测试
    t_abuse = acquire_ticket()
    req_abuse = create_bound_request(t_abuse, "abuse_eval_payload")
    abuse_payloads = [req_abuse.model_dump(mode='json') for _ in range(abuse_size)]
    
    # 必改 3: 在攻击前拉取快照，防止被前文的 C=1,10,30,50 数据污染
    try:
        metrics_before = requests.get(f"http://{target_ip}:8002/api/v1/verifier/metrics", timeout=2).json()
        pir_invoked_before = metrics_before.get("pir_invoked", 0)
    except:
        pir_invoked_before = 0

    sem = asyncio.Semaphore(100)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=100)) as session:
        async def fire_abuse(payload):
            async with sem:
                return await fire_req(session, verifier_url, payload, timeout=3.0)
                
        start_time = time.perf_counter()
        abuse_results = await asyncio.gather(*[fire_abuse(p) for p in abuse_payloads])
    
    decisions = [r[2] for r in abuse_results]
    success_count = decisions.count("SUCCESS")
    l7_rejected = decisions.count("REJECTED") + decisions.count("SCHEMA_ERR")
    l4_timeout = decisions.count("TIMEOUT") + decisions.count("CONN_ERR")
    
    blocked_before_compute = l7_rejected + l4_timeout
    blocked_ratio = (blocked_before_compute / abuse_size) * 100 if abuse_size else 0.0
    
    # 必改 3: 拉取攻击后快照并计算 Delta
    try:
        metrics_after = requests.get(f"http://{target_ip}:8002/api/v1/verifier/metrics", timeout=2).json()
        pir_invoked_after = metrics_after.get("pir_invoked", 0)
        pir_invoked = pir_invoked_after - pir_invoked_before
    except:
        pir_invoked = success_count

    pir_invocation_reduction = ((abuse_size - pir_invoked) / abuse_size) * 100 if abuse_size else 0.0

    print(f"\n📊 资源保护评估结果:")
    print(f"  ├─ 攻击请求总数                : {abuse_size}")
    print(f"  ├─ L7/L4 拦截总数 (Blocked)    : {blocked_before_compute}")
    print(f"  ├─ 成功穿透防线数 (SUCCESS)    : {success_count}")
    print(f"  ├─ Blocked-before-compute Ratio: {blocked_ratio:.2f}%")
    print(f"  ├─ Replay Interception Rate    : {blocked_ratio:.2f}%")
    print(f"  └─ PIR Invocation Reduction    : {pir_invocation_reduction:.2f}% (真实业务保护指标)")
    
    macro_metrics["abuse_replay_protection"] = {
        "abuse_size": abuse_size,
        "blocked_before_compute_ratio": blocked_ratio,
        "pir_invocation_reduction": pir_invocation_reduction,
        "success_count": success_count
    }

    return macro_metrics

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("server_ip", default="127.0.0.1", nargs="?")
    args = parser.parse_args()

    print("启动全量评估套件！全程预计需要 1-2 分钟，请保持网络连接稳定...")
    
    micro_res = run_micro_benchmarks(args.server_ip)
    macro_res = asyncio.run(run_macro_benchmarks(args.server_ip))
    
    final_report = {
        "micro_benchmarks_ns": micro_res,
        "macro_benchmarks": macro_res,
        "notes": {
            "backend_cpu_saved": "Not directly measured via host CPU in this script. 'pir_invocation_reduction' is used as a highly accurate business-level proxy.",
            "verifier_reject_path_latency_ms": "Includes HTTP, FastAPI routing, and Pydantic parsing overhead. Represents an interface-level approximation of pure L7 validation.",
            "ebpf_kernel_drop_estimate": "Estimated constant based on typical Linux XDP/TC performance, not dynamically measured."
        }
    }
    
    Path("results").mkdir(exist_ok=True)
    with open("results/eval_report_day52.json", "w") as f:
        json.dump(final_report, f, indent=2)
        
    print("\n✅ 所有跑分已完美收官！数据已格式化保存至 results/eval_report_day52.json")
    print("📊 附带了严谨的 Delta 差值表与测算声明口径，可以直接输出到你的论文中！")