# scripts/test_day23_concurrency.py
import sys
import uuid
import threading
import concurrent.futures
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from services.verifier.state_manager import get_state_manager
from common.models import TicketState


def attempt_lock(sm, sn, barrier):
    """模拟单个处理线程尝试获取票据锁，使用 Barrier 保证统一起跑"""
    barrier.wait()  # 所有线程在此阻塞，直到全部就位后瞬间释放
    return sm.try_lock(sn, lock_ttl_sec=30)


def test_atomic_concurrency():
    print("🚀 开始验收 Day 23: 原子核销与防并发重放...")
    sm = get_state_manager()

    # 构造一个合法的 64-hex SN
    test_sn = uuid.uuid4().hex + uuid.uuid4().hex
    concurrency_level = 50  # 50 个并发请求同时涌入

    # 修改 2: 显式清理，确保环境零污染
    sm.r.delete(sm._get_key(test_sn))

    # 修改 1: 使用 Barrier 发令枪机制
    barrier = threading.Barrier(concurrency_level)
    success_count = 0
    fail_count = 0

    print(f"\n[攻击目标 SN]: {test_sn[:16]}...")
    print(f"🔥 发起 {concurrency_level} 个并发线程，等待就绪后瞬间统一起跑...")

    # 使用线程池制造瞬间高并发
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency_level) as executor:
        # 提交所有任务
        futures = [executor.submit(attempt_lock, sm, test_sn, barrier) for _ in range(concurrency_level)]

        # 收集结果
        for future in concurrent.futures.as_completed(futures):
            if future.result() is True:
                success_count += 1
            else:
                fail_count += 1

    print("\n📊 并发攻击结果统计:")
    print(f"  ✅ 成功获取锁 (进入 PIR 主线): {success_count} 次")
    print(f"  ❌ 触发原子拦截 (被 Verifier 弹回): {fail_count} 次")

    # 核心验收断言
    assert success_count == 1, f"🚨 严重安全漏洞：有 {success_count} 个并发请求穿透了防线！"
    assert fail_count == concurrency_level - 1, "🚨 拦截数量不匹配！"

    # 修改 3: 补充最终状态落点断言
    final_state = sm.get_state(test_sn)
    print(f"  📌 最终票据状态: {final_state.value}")
    assert final_state == TicketState.PENDING, f"🚨 状态落点错误，期望 PENDING，实际为 {final_state}"
    print("✅ 状态落点断言通过: 最终状态稳定为 PENDING")

    print("\n🎉 Day 23 验收全部通过！Redis SETNX 原子锁在并发洪流中坚不可摧！")


if __name__ == "__main__":
    test_atomic_concurrency()