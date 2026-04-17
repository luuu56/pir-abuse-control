# services/pir_server/main.py
import sys
import asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.logging_utils import setup_logger

config = load_config()
logger = setup_logger("pir_server", config)
pir_cfg = config.get("pir_server", {})

# 从配置中读取模拟耗时，默认 1.0 秒
STUB_LATENCY_SEC = pir_cfg.get("stub_latency_sec", 1.0)

app = FastAPI(title="PIR Abuse Control - PIR Server Adapter (Stub)")


class PIRQueryRequest(BaseModel):
    """
    【Stub 协议声明】
    当前仅为 Python 控制层到 PIR 适配层的临时通信协议。
    后续对接真实 Go SimplePIR 时，可能演进为包含 query_id, execution_metadata 等的复杂结构。
    """
    query_payload: str


@app.post("/api/v1/pir/query")
async def execute_pir_query(req: PIRQueryRequest):
    logger.info(f"Received PIR query payload: {req.query_payload[:20]}...")

    # 使用配置驱动的模拟耗时
    await asyncio.sleep(STUB_LATENCY_SEC)

    if req.query_payload == "trigger_failure_test":
        logger.error("Simulated crash triggered by payload!")
        raise HTTPException(status_code=500, detail="Simulated PIR backend crash")

    dummy_result = f"simplepir_go_mock_result_for_{req.query_payload[:8]}"
    logger.info(f"PIR execution completed successfully after {STUB_LATENCY_SEC}s.")
    return {"status": "success", "data": dummy_result}


if __name__ == "__main__":
    uvicorn.run(app, host=pir_cfg.get("host", "127.0.0.1"), port=pir_cfg.get("port", 8003))