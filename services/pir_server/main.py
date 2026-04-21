# services/pir_server/main.py
import sys
import asyncio
import hashlib
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.logging_utils import setup_logger
from services.pir_server.engine_adapter import (
    call_external_pir_engine, EngineTimeoutError,
    EngineProcessError, EngineProtocolError,
    EngineResponseError, EngineNotFoundError
)

config = load_config()
logger = setup_logger("pir_server", config)
pir_cfg = config.get("pir_server", {})

ENGINE_MODE = pir_cfg.get("engine_mode", "stub")
STUB_LATENCY = pir_cfg.get("stub_latency_sec", 1.0)

sub_cfg = pir_cfg.get("subprocess", {})
ENGINE_CMD = sub_cfg.get("engine_cmd", ["python", "scripts/mock_external_pir.py"])
ENGINE_TIMEOUT = sub_cfg.get("engine_timeout_sec", 15.0)
WORKING_DIR = sub_cfg.get("working_dir", "")

# [Day 31 契约]：必须与 Go 侧 NUM_ENTRIES 保持绝对一致
DB_NUM_ENTRIES = 1024

def map_query_to_index(query_payload: str, num_entries: int) -> int:
    hash_bytes = hashlib.sha256(query_payload.encode('utf-8')).digest()
    hash_int = int.from_bytes(hash_bytes, byteorder='big')
    return hash_int % num_entries

app = FastAPI(title="PIR Abuse Control - PIR Server Adapter")

class PIRQueryRequest(BaseModel):
    query_payload: str

@app.post("/api/v1/pir/query")
async def execute_pir_query(req: PIRQueryRequest):
    logger.info(f"Received query [{req.query_payload[:15]}...]. Mode: {ENGINE_MODE}")

    # 联动 1：计算映射
    pir_index = map_query_to_index(req.query_payload, DB_NUM_ENTRIES)

    if ENGINE_MODE == "stub":
        await asyncio.sleep(STUB_LATENCY)
        if req.query_payload == "trigger_failure_test":
            raise HTTPException(status_code=500, detail="Simulated PIR backend crash")
        return {
            "data": f"stub_pir_result_for_{req.query_payload[:10]}",
            "mapped_index": pir_index,
            "recovered_val": 0
        }

    elif ENGINE_MODE == "subprocess":
        try:
            # 联动 2：传递 pir_index 并接收 3 个返回值
            result, recovered_val, meta = await call_external_pir_engine(
                ENGINE_CMD, ENGINE_TIMEOUT, req.query_payload, pir_index, WORKING_DIR
            )

            # 打印 engine_meta，不浪费宝贵的分析数据
            logger.info(f"External PIR engine executed successfully. Meta: {meta}")

            # 基础响应结构（没有 proof）
            response_dict = {
                "data": result,
                "mapped_index": pir_index,
                "recovered_val": recovered_val
            }

            # [Day 47 补全] 仅当客户端需要 VPIR/APIR 风格证明时，才附加 Optional 字段
            # 绑定要素：索引 | 恢复值 | 原始结果串
            if "apir_compat" in req.query_payload:
                proof_material = f"{pir_index}|{recovered_val}|{result}"
                response_dict["apir_proof"] = f"pir_proof_{hashlib.sha256(proof_material.encode()).hexdigest()[:24]}"

            return response_dict

        except EngineTimeoutError as e:
            logger.error(f"[Timeout] {e}")
            raise HTTPException(status_code=504, detail="Gateway Timeout")
        except EngineProtocolError as e:
            logger.error(f"[Protocol Error] {e}")
            raise HTTPException(status_code=502, detail="Bad Gateway")
        except EngineNotFoundError as e:
            logger.error(f"[Missing Engine] {e}")
            raise HTTPException(status_code=503, detail="Service Unavailable")
        except EngineProcessError as e:
            logger.error(f"[Process Crash] {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")
        except EngineResponseError as e:
            logger.error(f"[Engine Logic Error] {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")
        except Exception as e:
            logger.error(f"[Unknown Bridge Error] {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

if __name__ == "__main__":
    uvicorn.run(app, host=pir_cfg.get("host", "127.0.0.1"), port=pir_cfg.get("port", 8003))