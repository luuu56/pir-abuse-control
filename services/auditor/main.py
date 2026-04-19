# services/auditor/main.py
import sys
import json
import hmac
import hashlib
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
import uvicorn

root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.logging_utils import setup_logger
from common.models import AuditRecord

config = load_config()
logger = setup_logger("auditor", config)
auditor_cfg = config.get("auditor", {})

LEDGER_PATH = Path(auditor_cfg.get("ledger_path", "logs/audit_ledger.jsonl"))
AUDIT_SECRET_KEY = auditor_cfg.get("hmac_secret", "day25_default_key").encode("utf-8")

ledger_lock = threading.Lock()
current_prev_hash = "0" * 64


def _initialize_ledger_state():
    """启动时读取账本最后一行非空记录，恢复 prev_hash 状态"""
    global current_prev_hash
    if LEDGER_PATH.exists():
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            # 必补 2: 过滤掉文件末尾可能的空行，只取真正有内容的行
            valid_lines = [line.strip() for line in f if line.strip()]
            if valid_lines:
                try:
                    last_record = json.loads(valid_lines[-1])
                    current_prev_hash = last_record.get("entry_mac", "0" * 64)
                    logger.info(f"Ledger state restored. Resuming from MAC: {current_prev_hash[:16]}...")
                except Exception as e:
                    logger.error(f"Failed to parse last ledger entry: {e}")


# 必补 1: 将初始化放入 FastAPI 官方推荐的 lifespan 生命周期中
@asynccontextmanager
async def lifespan(app: FastAPI):
    _initialize_ledger_state()
    yield


app = FastAPI(title="PIR Abuse Control - Auditor Service", lifespan=lifespan)


@app.post("/api/v1/auditor/report")
async def receive_audit_report(record: AuditRecord):
    global current_prev_hash

    with ledger_lock:
        record.prev_hash = current_prev_hash

        # Day 25 第一版 MAC payload 契约：
        # sn | query_commitment | decision | timestamp_ms | prev_hash
        # 后续如需扩展字段，必须同步更新验证脚本
        payload = f"{record.sn}|{record.query_commitment}|{record.decision.value}|{record.timestamp_ms}|{record.prev_hash}"

        record.entry_mac = hmac.new(
            AUDIT_SECRET_KEY,
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        current_prev_hash = record.entry_mac

        LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LEDGER_PATH, "a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

    logger.info(f"📥 Audit Appended | SN: {record.sn[:8]}... | MAC: {record.entry_mac[:16]}...")
    return {"status": "recorded"}


if __name__ == "__main__":
    # 不再在此处调用 _initialize_ledger_state()，已全权交由 lifespan 管理
    uvicorn.run(app, host=auditor_cfg.get("host", "127.0.0.1"), port=auditor_cfg.get("port", 8004))