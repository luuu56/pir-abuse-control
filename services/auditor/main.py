# services/auditor/main.py
import sys
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

app = FastAPI(title="PIR Abuse Control - Auditor Service")

@app.post("/api/v1/auditor/report")
async def receive_audit_report(record: AuditRecord):
    # 目前仅做日志接收，后续 Day 14+ 落入数据库或特定日志文件
    logger.info(f"Received Audit Record for SN: {record.sn[:16]}...")
    logger.info(f"  -> Decision: {record.decision.value}, Reason: {record.reason}")
    logger.info(f"  -> c_q: {record.query_commitment[:16]}..., b: {record.binding_tag[:16]}...")
    return {"status": "recorded"}

if __name__ == "__main__":
    uvicorn.run(app, host=auditor_cfg.get("host", "127.0.0.1"), port=auditor_cfg.get("port", 8004))