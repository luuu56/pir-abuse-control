# scripts/test_day51_ablation.py
import sys
import time
import json
import asyncio
import argparse
import requests
from pathlib import Path

try:
    import aiohttp
except ImportError:
    print("❌ 缺少必要依赖！请运行: pip install aiohttp")
    sys.exit(1)

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from services.client.main import acquire_ticket, create_bound_request

def test_admission_ablation(target_ip: str):
    """
    攻击 1：准入机制消融测试
    """
    issuer_url = f"http://{target_ip}:8001/api/v1/issuer/issue"
    print("\n" + "="*60)
    print("⚔️  [攻击测试 1] 准入控制 (Admission) 旁路攻击 ⚔️")
    print("➜ 尝试：使用无效 PoW 和伪造 HMAC 构造虚假 proof 申请发票...")
    
    malicious_req = {
        "admission_proof": {
            "challenge": {
                "payload": {
                    "client_tag": "hacker_bot",
                    "epoch_id": 999999,
                    "difficulty": 16,
                    "issued_at": int(time.time()),
                    "expires_at": int(time.time()) + 300,
                    "server_nonce": "fake_nonce"
                },
                "hmac_sig": "00000000000000000000000000000000" # 错误签名
            },
            "nonce": "0" # 没有做 PoW
        },
        "blinded_message": "0x123456789abcdef"
    }
    
    try:
        resp = requests.post(issuer_url, json=malicious_req, timeout=5)
        if resp.status_code == 200 and "blinded_signature" in resp.json():
            print("💥 [防线被穿透] 攻击成功！关闭 admission 后，Issuer 不再验证 challenge HMAC / PoW / burn semantics，伪造 proof 亦可签票！(disable_admission=true)")
        else:
            print("🛡️ [防线生效] 攻击失败！Issuer 成功拦截了非法请求。")
            print(f"   拦截详情: HTTP {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"请求异常: {e}")

def test_binding_ablation(target_ip: str):
    """
    攻击 2：密码学绑定消融测试
    """
    verifier_url = f"http://{target_ip}:8002/api/v1/verifier/execute"
    print("\n" + "="*60)
    print("⚔️  [攻击测试 2] 密码学绑定 (HMAC Binding) 篡改攻击 ⚔️")
    
    try:
        print("➜ 步骤 1: 申请真实票据，并合法绑定查询载荷 [SAFE_QUERY]...")
        ticket = acquire_ticket()
        req = create_bound_request(ticket, "SAFE_QUERY")
        
        print("➜ 步骤 2: 充当中间人，强行将请求篡改为 [MUNBOUND_MALICIOUS_QUERY...")
        malicious_req = req.model_dump(mode='json')
        malicious_req["query_payload"] = "UNBOUND_MALICIOUS_QUERY"
        
        resp = requests.post(verifier_url, json=malicious_req, timeout=5)
        
        if resp.status_code == 200:
            decision = resp.json().get("decision")
            if decision == "SUCCESS":
                print("💥 [防线被穿透] 攻击成功！Verifier 执行了被篡改的恶意载荷！(disable_binding=true)")
            else:
                reason = resp.json().get("reason", "Unknown")
                print(f"🛡️ [防线生效] 攻击失败！Verifier 识别出绑定异常。拦截原因: {reason}")
        else:
            print(f"🛡️ [异常拦截] HTTP {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"请求异常: {e}")

async def fire_concurrent_req(session, url, payload):
    async with session.post(url, json=payload, timeout=5) as resp:
        text = await resp.text()
        try:
            body = json.loads(text)
            return resp.status, body.get("decision")
        except Exception:
            return resp.status, None

async def test_consume_ablation(target_ip: str, concurrency: int = 15):
    """
    攻击 3：状态机与原子核销消融测试
    """
    verifier_url = f"http://{target_ip}:8002/api/v1/verifier/execute"
    print("\n" + "="*60)
    print(f"⚔️  [攻击测试 3] 并发重放与状态机 (Consume) 旁路攻击 ⚔️")
    print(f"➜ 尝试：持 1 张真票，瞬间发起 {concurrency} 次并发请求...")
    
    try:
        ticket = acquire_ticket()
        req = create_bound_request(ticket, "REPLAY_TEST_PAYLOAD")
        payload = req.model_dump(mode='json')
        
        async with aiohttp.ClientSession() as session:
            tasks = [fire_concurrent_req(session, verifier_url, payload) for _ in range(concurrency)]
            results = await asyncio.gather(*tasks)
            
        success_count = sum(1 for status, decision in results if status == 200 and decision == "SUCCESS")
        
        if success_count > 1:
            print(f"💥 [防线被穿透] 攻击成功！有 {success_count} 个请求成功执行。关闭 consume 后，状态机消费语义整体被旁路，导致恶意流量无限白嫖！(disable_consume_lock=true)")
        elif success_count == 1:
            print(f"🛡️ [防线生效] 攻击失败！仅有 1 个请求透传，其余 {concurrency - 1} 个请求均被状态机与并发锁准确挡回。")
        else:
            print(f"🛡️ [异常拦截] 没有任何请求成功，可能被前面的测试污染了状态。")
            
    except Exception as e:
        print(f"请求异常: {e}")

def test_epoch_ablation(target_ip: str):
    """
    攻击 4：纪元过期消融测试
    原理：申请合法票据，不作任何篡改，等待其自然跨越 Epoch 边界后发起请求。
    """
    verifier_url = f"http://{target_ip}:8002/api/v1/verifier/execute"
    print("\n" + "="*60)
    print("⚔️  [攻击测试 4] 纪元过期 (Epoch) 旁路攻击 ⚔️")
    print("➜ 尝试：获取真实票据后，故意等待纪元自然过期，测试旧票囤积攻击...")
    
    try:
        print("   [1/3] 正在向 Issuer 申请合法真票并绑定载荷...")
        ticket = acquire_ticket()
        req = create_bound_request(ticket, "EPOCH_EXPIRED_PAYLOAD")
        
        # 强制沉睡 11 秒，确保在 duration=5 的配置下绝对跨过 Epoch 边界
        wait_time = 11
        print(f"   [2/3] 正在沉睡 {wait_time} 秒，让票据自然老化过期...")
        time.sleep(wait_time)
        
        print("   [3/3] 时间到！发射过期真票...")
        resp = requests.post(verifier_url, json=req.model_dump(mode='json'), timeout=5)
        
        if resp.status_code == 200:
            decision = resp.json().get("decision")
            if decision == "SUCCESS":
                print("💥 [防线被穿透] 攻击成功！Verifier 接受了已自然过期的合法旧票。旧票长期囤积攻击生效！(disable_epoch=true)")
            else:
                reason = resp.json().get("reason", "Unknown")
                print(f"🛡️ [防线生效] 攻击失败！Verifier 成功识别并拒绝了旧票。拦截原因: {reason}")
        else:
            print(f"🛡️ [异常拦截] HTTP {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"请求异常: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Day 51 Ablation Study Tester")
    parser.add_argument("server_ip", help="Target server IP address")
    parser.add_argument("--attack", choices=["admission", "binding", "replay", "epoch", "all"], default="all",
                        help="Specific attack to run")
    args = parser.parse_args()
    
    print("\n" + "!"*60)
    print("🚨 Day 51: 架构消融评估实验 (Ablation Study) 🚨")
    print("⚠️  声明 1: 请确保在 base.yaml 中一次只开启一个 disable_* 开关，并运行对应的单项攻击。")
    print("⚠️  声明 2: Day 51 的目标是逐项精准消融，不建议使用多开关混合结果来推导结论。")
    if args.attack == "all":
        print("⚠️  警告 3: 当前使用的是 '--attack all' 模式！此模式仅供快速连通性联调，不应用于正式消融结论留档！")
    print("!"*60)
    
    if args.attack in ["admission", "all"]:
        test_admission_ablation(args.server_ip)
    
    if args.attack in ["binding", "all"]:
        test_binding_ablation(args.server_ip)
        
    if args.attack in ["replay", "all"]:
        asyncio.run(test_consume_ablation(args.server_ip))
        
    if args.attack in ["epoch", "all"]:
        test_epoch_ablation(args.server_ip)
        
    print("\n" + "="*60)
    print("🏁 消融实验执行完毕。")