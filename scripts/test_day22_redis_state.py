# scripts/test_day22_redis_state.py
import sys
import uuid
import time
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from services.verifier.state_manager import get_state_manager
from common.models import TicketState
from common.config import load_config


def test_redis_state_machine():
    print("🚀 开始验收 Day 22: Redis 状态表与查询接口...")
    sm = get_state_manager()
    cfg = load_config()

    # 修正：严格遵守 SN 契约 (256-bit = 64 Hex chars)
    test_sn = uuid.uuid4().hex + uuid.uuid4().hex

    print(f"\n[测试票据 SN]: {test_sn}")

    # 验收点 1：隐式 UNUSED
    state = sm.get_state(test_sn)
    assert state == TicketState.UNUSED, f"❌ 初始状态错误，期望 UNUSED，实际为 {state}"
    print("✅ 验收点 1 通过: Redis Miss == UNUSED (无需 Issuer 预写)")

    # 验收点 2：(Day 23 预热) PENDING 原子锁定
    locked = sm.try_lock(test_sn, lock_ttl_sec=5)
    assert locked is True, "❌ 首次加锁应该成功"
    current_state = sm.get_state(test_sn)
    assert current_state == TicketState.PENDING, "❌ 加锁后状态应为 PENDING"
    print("✅ 验收点 2 通过: PENDING 原子占位成功")

    # 验收点 3：测试真实 Epoch 驱动的 TTL 计算与终态流转
    duration = cfg.get("epoch", {}).get("duration_sec", 3600)
    grace_window = cfg.get("epoch", {}).get("grace_window_sec", 300)
    current_epoch = int(time.time() / duration)

    print(f"   当前逻辑时刻 Epoch: {current_epoch}")

    # 写入真实 epoch_id 观察真实 TTL
    sm.mark_consumed(test_sn, epoch_id=current_epoch)
    final_state = sm.get_state(test_sn)
    assert final_state == TicketState.CONSUMED, "❌ 状态流转失败，期望 CONSUMED"

    # 获取 Redis 里的真实剩余 TTL (用于内部验证)
    real_ttl = sm.r.ttl(sm._get_key(test_sn))
    print(f"   Redis 实际 TTL 剩余: {real_ttl}s (由 Epoch 驱动)")

    # --- 新增：强化断言 ---
    expected_upper = duration + grace_window + 600
    assert real_ttl > 0, "❌ Redis TTL 应为正数"
    assert real_ttl <= expected_upper, f"❌ Redis TTL 异常偏大，超出了理论上限 {expected_upper}s"
    print("✅ 验收点 3 通过: 成功流转终态，且真实 TTL 严格符合 Epoch 时间窗预期")

    # 验收点 4：验证 TTL 过期回退至隐式状态
    # 为了测试物理过期，我们在这里使用 override 强行把刚才那条记录的 TTL 缩短为 2 秒
    sm.mark_consumed(test_sn, epoch_id=current_epoch, ttl_override_sec=2)
    print("⏳ 强制覆盖 TTL 为 2s，等待 3 秒测试物理清理...")
    time.sleep(3)
    expired_state = sm.get_state(test_sn)
    assert expired_state == TicketState.UNUSED, "❌ TTL 未生效，票据未被物理清理"
    print("✅ 验收点 4 通过: TTL 过期后发生 Redis Miss，逻辑状态优雅回归 UNUSED")

    print("\n🎉 Day 22 (Redis 状态表核心语义) 验收全部通过！")


if __name__ == "__main__":
    test_redis_state_machine()