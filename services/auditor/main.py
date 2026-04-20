# services/auditor/main.py
import sys
import json
import hmac
import hashlib
import threading
from typing import Optional
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
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
            valid_lines = [line.strip() for line in f if line.strip()]
            if valid_lines:
                try:
                    last_record = json.loads(valid_lines[-1])
                    current_prev_hash = last_record.get("entry_mac", "0" * 64)
                    logger.info(f"Ledger state restored. Resuming from MAC: {current_prev_hash[:16]}...")
                except Exception as e:
                    logger.error(f"Failed to parse last ledger entry: {e}")


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


@app.get("/api/v1/auditor/trace/{sn}")
async def trace_audit_record(sn: str, expected_cq: Optional[str] = None):
    """
    Day 26: 审计日志单条追溯接口。
    显式返回当前记录的链上下文字段（prev_hash / entry_mac），
    用于最小追溯与后续完整性校验。
    """
    sn = sn.lower()
    is_hex_sn = len(sn) == 64 and all(c in "0123456789abcdef" for c in sn)
    if not is_hex_sn:
        raise HTTPException(status_code=400, detail="Invalid SN format: must be 64-char hex")

    if expected_cq is not None:
        cq = expected_cq.lower()
        is_hex = len(cq) == 64 and all(c in "0123456789abcdef" for c in cq)
        if not is_hex:
            raise HTTPException(status_code=400, detail="Invalid expected_cq format: must be 64-char hex")
        expected_cq = cq

    if not LEDGER_PATH.exists():
        raise HTTPException(status_code=404, detail="Ledger file not found")

    found_record = None
    line_number = 0

    with open(LEDGER_PATH, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if not line.strip(): continue
            try:
                record = json.loads(line)
                if record.get("sn") == sn:
                    found_record = record
                    line_number = idx + 1
                    # 当前原型阶段默认一张票据最终只对应一条主审计记录，故找到即停。
                    # 若后续需要支持多事件追踪，再扩展为返回记录列表。
                    break
            except json.JSONDecodeError:
                continue

    if not found_record:
        raise HTTPException(status_code=404, detail=f"Audit record for SN {sn} not found")

    response = {
        "sn": sn,
        "ledger_line": line_number,
        "record": found_record,
        "chain_context": {
            "prev_hash": found_record.get("prev_hash"),
            "entry_mac": found_record.get("entry_mac")
        }
    }

    if expected_cq is not None:
        is_consistent = (found_record.get("query_commitment") == expected_cq)
        response["cq_consistent"] = is_consistent

    return response


if __name__ == "__main__":
    uvicorn.run(app, host=auditor_cfg.get("host", "127.0.0.1"), port=auditor_cfg.get("port", 8004))