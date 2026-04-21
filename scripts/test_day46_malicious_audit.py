# scripts/test_day46_malicious_audit.py
import sys
import time
import json
import hmac
import hashlib
import shutil
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


class MaliciousAuditTester:
    def __init__(self, target_ip=None):
        self.config = load_config()
        self.auditor_cfg = self.config.get("auditor", {})

        auditor_host = target_ip if target_ip else self.auditor_cfg.get('host', '127.0.0.1')
        self.auditor_url = f"http://{auditor_host}:{self.auditor_cfg.get('port', 8004)}"

        redis_cfg = self.config.get("redis", {})
        redis_host = target_ip if target_ip else redis_cfg.get('host', '127.0.0.1')
        self.state_manager = TicketStateManager(host=redis_host, port=6379)
        self.r = self.state_manager.r

        ledger_rel_path = self.auditor_cfg.get("ledger_path", "logs/audit_ledger.jsonl")
        self.ledger_path = root_path / ledger_rel_path
        self.audit_secret_key = self.auditor_cfg.get("hmac_secret", "day25_default_key").encode("utf-8")

        print("=" * 60)
        print("🛡️ Day 46: 审计链防伪造与一致性交叉验收 (终版) 🛡️")
        print(f"➜ 审计契约对齐: Day 25 HMAC 链式契约")
        print(f"➜ 目标环境: {self.auditor_url}")
        print("=" * 60 + "\n")

    def log_test(self, name, result, details=""):
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"[{status}] {name}")
        if details: print(f"    Detail: {details}")

    def run_scenario_c_cross_source_conflict(self):
        """
        场景 C：跨证据不一致发现 (在线伪造/错误关联)
        1. 状态矛盾：Redis (真相) 是 CONSUMED，但账本被伪造为 FAILED。
        2. 载荷矛盾：利用 expected_cq 发现账本关联了错误的承诺。
        只需发现任意一种最小一致性问题，即算防御生效。
        """
        print("--- 正在运行场景 C：跨证据源矛盾对账 (Redis vs Auditor) ---")
        test_sn = secrets.token_hex(32)
        real_query = "legit_query_payload_v1"
        fake_query = "malicious_injected_payload_v1"

        real_cq = compute_query_commitment(real_query)
        fake_cq = compute_query_commitment(fake_query)

        # 1. 设置执行真相 (Redis)
        self.state_manager.mark_consumed(test_sn, epoch_id=1)

        # 2. 上报伪造审计 (Decision 伪造成 FAILED, c_q 伪造成 fake_cq)
        audit_record = AuditRecord(
            request_id=f"req_{test_sn[:8]}",
            sn=test_sn,
            query_commitment=fake_cq,
            binding_tag="binding_tag_v1",
            epoch_id=1,
            decision=Decision.FAILED,
            timestamp_ms=int(time.time() * 1000),
            prev_hash="stub",
            entry_mac="stub"
        )
        try:
            resp = requests.post(f"{self.auditor_url}/api/v1/auditor/report",
                                 json=audit_record.model_dump(mode='json'), timeout=5)
            resp.raise_for_status()

            # 3. 跨证据对账：调 trace 并带上真实的 expected_cq
            trace_resp = requests.get(f"{self.auditor_url}/api/v1/auditor/trace/{test_sn}",
                                      params={"expected_cq": real_cq}, timeout=5)
            trace_resp.raise_for_status()  # 关键修复 1：防止静默吸收 HTTP 错误
            trace_data = trace_resp.json()
            record = trace_data.get("record", {})

            # 关键修复 2：显式解码 Redis 返回值
            redis_state = self.r.get(self.state_manager._get_key(test_sn))
            if isinstance(redis_state, bytes):
                redis_state = redis_state.decode("utf-8")

            # 判定 A: 状态矛盾
            state_conflict = (
                        redis_state == TicketState.CONSUMED.value and record.get("decision") == Decision.FAILED.value)

            # 判定 B: 载荷矛盾
            cq_inconsistent = (trace_data.get("cq_consistent") is False)

            # 建议 A 落实：任意一项不一致，均算成功发现“最小一致性问题”
            success = state_conflict or cq_inconsistent
            self.log_test("发现跨源最小一致性问题", success,
                          f"状态矛盾发现={state_conflict}, 载荷矛盾发现={cq_inconsistent}")

        except Exception as e:
            self.log_test("场景 C 执行异常", False, str(e))

    def run_scenario_d_ledger_tampering(self):
        """
        场景 D：离线账本篡改发现 (链式完整性校验)
        直接修改磁盘文件中的 query_commitment，验证 Day 25 契约的 HMAC 链能否识别篡改。
        """
        print("\n--- 正在运行场景 D：离线账本篡改与 HMAC 链完整性校验 ---")

        # 1. 产生一条基准记录
        test_sn = secrets.token_hex(32)
        cq = compute_query_commitment("integrity_test_v1")
        valid_record = AuditRecord(
            request_id=f"req_{test_sn[:8]}",
            sn=test_sn,
            query_commitment=cq,
            binding_tag="binding_v1",
            epoch_id=1,
            decision=Decision.SUCCESS,
            timestamp_ms=int(time.time() * 1000),
            prev_hash="stub",
            entry_mac="stub"
        )

        # 关键修复 3：拆分请求和状态校验，方便排障
        resp = requests.post(f"{self.auditor_url}/api/v1/auditor/report",
                             json=valid_record.model_dump(mode='json'), timeout=5)
        resp.raise_for_status()

        # 2. 模拟篡改：在副本上操作
        tampered_path = self.ledger_path.with_name("audit_ledger_tampered.jsonl")
        shutil.copyfile(self.ledger_path, tampered_path)

        with open(tampered_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if lines:
            try:
                found_idx = -1
                for i in range(len(lines) - 1, -1, -1):
                    if test_sn in lines[i]:
                        found_idx = i
                        break

                if found_idx == -1:
                    self.log_test("定位记录失败", False, "未能找到刚插入的 SN 记录")
                    return

                record = json.loads(lines[found_idx])

                # 建议 B 落实：篡改 query_commitment，严丝合缝贴合 Day 46 题面
                fake_cq = compute_query_commitment("tampered_query_payload_v2")
                record["query_commitment"] = fake_cq
                lines[found_idx] = json.dumps(record) + "\n"

                with open(tampered_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)

                # 3. 密码学验证：使用对齐 Day 25 的验证器
                is_intact = self._verify_integrity_day25(tampered_path)
                self.log_test("发现离线账本链断裂 (c_q 被篡改)", not is_intact, "契约级 HMAC 校验失败，篡改被识破")

            except Exception as e:
                self.log_test("模拟篡改过程出错", False, str(e))

    def _verify_integrity_day25(self, path: Path) -> bool:
        """
        验证器：
        1. 严格对齐契约: sn|query_commitment|decision|timestamp_ms|prev_hash
        2. 校验链式关系: 当前记录的 prev_hash == 上一条记录的 entry_mac
        """
        last_entry_mac = "0" * 64
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                record = json.loads(line)

                # A. 链式关系校验
                if record.get("prev_hash") != last_entry_mac:
                    return False

                # B. 内容完整性校验
                msg = f"{record['sn']}|{record['query_commitment']}|{record['decision']}|{record['timestamp_ms']}|{record['prev_hash']}"
                calculated_mac = hmac.new(self.audit_secret_key, msg.encode('utf-8'), hashlib.sha256).hexdigest()

                if calculated_mac != record.get('entry_mac'):
                    return False

                last_entry_mac = calculated_mac
        return True


if __name__ == "__main__":
    target_ip = sys.argv[1] if len(sys.argv) > 1 else None
    tester = MaliciousAuditTester(target_ip)

    try:
        tester.run_scenario_c_cross_source_conflict()
        tester.run_scenario_d_ledger_tampering()
    except Exception as e:
        print(f"执行异常: {e}")