# scripts/test_day45_malicious_verifier.py
import sys
import time
import requests
import secrets
from pathlib import Path

# 确保能加载 common 包
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.models import TicketState, Decision, AuditRecord
from services.verifier.state_manager import TicketStateManager
from common.crypto_utils import compute_query_commitment

class MaliciousVerifierTester:
    def __init__(self, target_ip=None):
        self.config = load_config()
        self.auditor_cfg = self.config.get("auditor", {})
        
        # 环境决断逻辑：优先使用命令行传入的 IP，否则使用 YAML
        auditor_host = target_ip if target_ip else self.auditor_cfg.get('host', '127.0.0.1')
        self.auditor_url = f"http://{auditor_host}:{self.auditor_cfg.get('port', 8004)}"
        
        redis_cfg = self.config.get("redis", {})
        redis_host = target_ip if target_ip else redis_cfg.get('host', '127.0.0.1')
        redis_port = redis_cfg.get('port', 6379)
        
        print("="*60)
        print("⚠️ 运行环境与目标检查 ⚠️")
        print(f"➜ Auditor 目标: {self.auditor_url}")
        print(f"➜ Redis   目标: {redis_host}:{redis_port}")
        print("请确保你当前运行此脚本的环境，能够直连上述 Redis！")
        print("="*60 + "\n")

        # 直连 Redis 注入毒药
        self.state_manager = TicketStateManager(host=redis_host, port=redis_port)
        self.r = self.state_manager.r
        
    def log_test(self, name, result, details=""):
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"[{status}] {name}")
        if details: print(f"    Detail: {details}")

    def run_scenario_a_ghost_consumption(self):
        """
        场景 A：幽灵核销 (Ghost Consumption) - 【Day 45 主验收核心】
        """
        print("--- 正在运行场景 A (Day 45 核心)：幽灵核销 (外部对账检查) ---")
        # 必须使用合法的 64 字符 hex 作为 SN
        test_sn = secrets.token_hex(32)
        
        # 1. 模拟恶意操作：修改 Redis，不发审计日志
        self.state_manager.mark_consumed(test_sn, epoch_id=1)
        print(f"已在 Redis 中恶意将 SN {test_sn[:8]}... 设为 CONSUMED")

        # 2. 外部对账检查：查 Auditor 的 trace 接口
        try:
            response = requests.get(f"{self.auditor_url}/api/v1/auditor/trace/{test_sn}", timeout=5)
            redis_state = self.r.get(self.state_manager._get_key(test_sn))
            
            # 判断逻辑：Redis 是消费态，但 Auditor 根本没有这个 SN 的踪迹 (404)
            success = (response.status_code == 404 and redis_state == TicketState.CONSUMED.value)
            self.log_test(
                "外部对账发现幽灵核销", 
                success, 
                f"Redis状态={redis_state}, Auditor接口返回={response.status_code}, Body={response.text.strip()}"
            )
        except Exception as e:
            self.log_test("外部对账请求异常", False, str(e))

    def run_scenario_b_commitment_tampering(self):
        """
        场景 B：承诺篡改 (Commitment Tampering) - 【Day 46 提前预演】
        """
        print("\n--- 正在运行场景 B (Day 46 预演)：承诺篡改 (一致性字段校验) ---")
        # 必须使用合法的 64 字符 hex 作为 SN
        test_sn = secrets.token_hex(32)
        real_cq = compute_query_commitment("index_42")
        fake_cq = compute_query_commitment("index_999")

        audit_record = AuditRecord(
            request_id=f"req_{test_sn[:8]}",
            sn=test_sn,
            query_commitment=fake_cq,
            binding_tag="fake_binding_tag",
            epoch_id=1,
            decision=Decision.SUCCESS,
            timestamp_ms=int(time.time() * 1000),
            prev_hash="stub",
            entry_mac="stub"
        )
        audit_payload = audit_record.model_dump(mode='json')
        
        print(f"尝试向 Auditor 写入篡改后的承诺: {fake_cq[:10]}...")
        try:
            post_resp = requests.post(f"{self.auditor_url}/api/v1/auditor/report", json=audit_payload, timeout=5)
            print(f"  > 写入阶段 Auditor 返回: HTTP {post_resp.status_code}, Body: {post_resp.text.strip()}")
            
            # 成功判定 1：前置拦截防线生效
            if post_resp.status_code != 200:
                self.log_test(
                    "发现并拦截篡改 (Day 46 预演)", 
                    True, 
                    f"防线前置生效：写入阶段被 Auditor 拒绝"
                )
                return

            # 如果写入成功，走追溯比对逻辑
            query_params = {"expected_cq": real_cq}
            response = requests.get(f"{self.auditor_url}/api/v1/auditor/trace/{test_sn}", params=query_params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                cq_consistent = data.get("cq_consistent")
                
                # 成功判定 2：事后追溯防线生效
                self.log_test(
                    "通过 trace 接口发现一致性异常 (Day 46 预演)", 
                    cq_consistent is False, 
                    f"伪造记录成功入账，但 trace 对比发现篡改, cq_consistent={cq_consistent}"
                )
            else:
                self.log_test("trace 查询异常", False, f"状态码: {response.status_code}, Body={response.text.strip()}")

        except Exception as e:
            self.log_test("请求 Auditor 发生异常", False, str(e))

if __name__ == "__main__":
    target_env_ip = sys.argv[1] if len(sys.argv) > 1 else None
    tester = MaliciousVerifierTester(target_env_ip)
    
    try:
        tester.run_scenario_a_ghost_consumption()
        tester.run_scenario_b_commitment_tampering()
    except Exception as e:
        print(f"测试执行中发生顶层异常: {e}")