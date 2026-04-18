# services/verifier/state_manager.py
import redis
import logging
import time
from typing import Optional
from common.models import TicketState
from common.config import load_config

logger = logging.getLogger("verifier.state")


class TicketStateManager:
    def __init__(self, host=None, port=None, db=None):
        self.config = load_config()

        # 1. 优先从统一 YAML 读取 Redis 配置 (建议改 5)
        redis_cfg = self.config.get("redis", {})
        host = host or redis_cfg.get("host", "127.0.0.1")
        port = port or redis_cfg.get("port", 6379)
        db = db if db is not None else redis_cfg.get("db", 0)

        # 2. Key 前缀规范化 (必改 2)
        self.prefix = redis_cfg.get("ticket_state_prefix", "ticket")

        # 3. Epoch 配置读取
        epoch_cfg = self.config.get("epoch", {})
        self.epoch_duration = epoch_cfg.get("duration_sec", 3600)
        self.grace_window = epoch_cfg.get("grace_window_sec", 300)

        self.r = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        try:
            self.r.ping()
            logger.info(f"Connected to Redis at {host}:{port}, prefix='{self.prefix}'")
        except redis.ConnectionError as e:
            logger.error(f"Redis connection failed: {e}")
            raise

    def _get_key(self, sn: str) -> str:
        return f"{self.prefix}:{sn}"

    def get_state(self, sn: str) -> TicketState:
        """Redis miss == UNUSED (逻辑默认态)"""
        val = self.r.get(self._get_key(sn))
        if not val:
            return TicketState.UNUSED
        return TicketState(val)

    def try_lock(self, sn: str, lock_ttl_sec: int = 30) -> bool:
        """
        短时占用锁：
        - 用于 UNUSED -> PENDING 的并发保护
        - lock_ttl_sec 是 in-flight 保护 TTL，不等同于 epoch 终态保留 TTL
        """
        return bool(self.r.set(self._get_key(sn), TicketState.PENDING.value, nx=True, ex=lock_ttl_sec))

    def _calculate_ttl(self, epoch_id: Optional[int], ttl_override_sec: Optional[int]) -> int:
        """
        真正的 Epoch 关联 TTL 实现:
        计算从现在到票据所属 Epoch 宽限期结束的剩余秒数。

        # 约定契约：epoch_id 必须等于 floor(now_ts / epoch_duration)
        # 因此 epoch_id 对应纪元的结束时间点精确等于 (epoch_id + 1) * epoch_duration
        """
        if ttl_override_sec is not None:
            return ttl_override_sec

        if epoch_id is None:
            # 回退方案：固定保留时长
            return self.epoch_duration + self.grace_window + 600

        now_ts = int(time.time())
        epoch_end_ts = (epoch_id + 1) * self.epoch_duration
        ttl = epoch_end_ts + self.grace_window + 600 - now_ts
        return max(ttl, 1)

    def mark_consumed(self, sn: str, epoch_id: Optional[int] = None, ttl_override_sec: Optional[int] = None):
        """
        将状态置为 CONSUMED 终态。
        [Day 22 现状]：当前 Redis Value 仅存状态字符串。后续如需 Auditor 对账，再考虑升级为包含 updated_at_ms 等信息的 JSON 结构。
        [使用规范]：正式主流程应严格优先传入 epoch_id；ttl_override_sec 仅供测试/联调场景使用，严禁主线暴露。
        """
        ttl = self._calculate_ttl(epoch_id, ttl_override_sec)
        self.r.set(self._get_key(sn), TicketState.CONSUMED.value, ex=ttl)

    def mark_failed(self, sn: str, epoch_id: Optional[int] = None, ttl_override_sec: Optional[int] = None):
        """
        将状态置为 FAILED 终态。
        [使用规范]：正式主流程应严格优先传入 epoch_id；ttl_override_sec 仅供测试/联调场景使用。
        """
        ttl = self._calculate_ttl(epoch_id, ttl_override_sec)
        self.r.set(self._get_key(sn), TicketState.FAILED.value, ex=ttl)


# 4. 懒初始化单例 (建议改 3)
_state_manager_instance = None


def get_state_manager():
    global _state_manager_instance
    if _state_manager_instance is None:
        _state_manager_instance = TicketStateManager()
    return _state_manager_instance