# services/verifier/state_manager.py
import redis
import logging
from common.models import TicketState

logger = logging.getLogger("verifier.state")

class TicketStateManager:
    def __init__(self, host='127.0.0.1', port=6379, db=0):
        self.r = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        try:
            self.r.ping()
            logger.info(f"Successfully connected to Redis at {host}:{port}")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def get_state(self, sn: str) -> TicketState:
        """查询票据当前状态"""
        val = self.r.get(f"ticket:{sn}")
        if not val:
            return TicketState.UNUSED
        return TicketState(val)

    def try_lock(self, sn: str, lock_ttl_sec: int = 30) -> bool:
        """
        【原子防并发】尝试将票据置为 PENDING 状态。
        """
        is_locked = self.r.set(f"ticket:{sn}", TicketState.PENDING.value, nx=True, ex=lock_ttl_sec)
        return bool(is_locked)

    def mark_consumed(self, sn: str, epoch_ttl_sec: int = 86400):
        """【成功终态】执行成功，标记为 CONSUMED"""
        self.r.set(f"ticket:{sn}", TicketState.CONSUMED.value, ex=epoch_ttl_sec)

    def mark_failed(self, sn: str, epoch_ttl_sec: int = 86400):
        """【异常终态】执行失败，标记为 FAILED (票据烧毁，禁止重试)"""
        self.r.set(f"ticket:{sn}", TicketState.FAILED.value, ex=epoch_ttl_sec)

state_manager = TicketStateManager()