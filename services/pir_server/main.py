# services/pir_server/main.py
import sys
import asyncio
import hashlib
import re
import os
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import uvicorn

try:
    import redis
except ImportError:
    redis = None

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

# =========================================================================
# [Day 57.1 补丁]：提取规模与计算仿真惩罚
# =========================================================================
dataset_path = pir_cfg.get("dataset_path", "data/pir/db_1gb.bin")
match = re.search(r'db_(\d+)gb', dataset_path)
db_size_gb = int(match.group(1)) if match else 1

# 基础延迟 100ms，每 GB 增加 200ms
EMULATED_DELAY_SEC = 0.1 + (db_size_gb * 0.2)
ENABLE_SCALING_DELAY = pir_cfg.get("enable_emulated_scaling_delay", True)

logger.info(f"🚀 PIR Server 启动 | Dataset: {dataset_path} | Size: {db_size_gb}GB | Emulated Delay: {EMULATED_DELAY_SEC}s | Delay Enabled: {ENABLE_SCALING_DELAY}")
# =========================================================================

DB_NUM_ENTRIES = 1024

def map_query_to_index(query_payload: str, num_entries: int) -> int:
    hash_bytes = hashlib.sha256(query_payload.encode('utf-8')).digest()
    hash_int = int.from_bytes(hash_bytes, byteorder='big')
    return hash_int % num_entries

app = FastAPI(title="PIR Abuse Control - PIR Server Adapter")

class PIRQueryRequest(BaseModel):
    query_payload: str

    # Evaluation-only metadata forwarded by the verifier. These fields are only
    # used to record backend-invocation ground truth and never affect PIR logic.
    eval_run_id: Optional[str] = None
    eval_point_id: Optional[str] = None
    eval_request_type: Optional[str] = None


# -----------------------------------------------------------------------------
# Evaluation-only backend invocation ground truth
# -----------------------------------------------------------------------------
EVAL_PREFIX = str(pir_cfg.get("eval_metrics_prefix", "pir_eval"))
_eval_fallback_lock = threading.Lock()
_eval_fallback: Dict[str, int] = {}
_eval_redis = None
_eval_backend = "memory"


def _get_redis_cfg() -> dict:
    return config.get("redis", {}) or {}


def _init_eval_redis_client():
    global _eval_backend
    if redis is None:
        logger.warning("[eval] redis package is not installed; using process-local PIR eval counters.")
        _eval_backend = "memory_no_redis_package"
        return None
    redis_cfg = _get_redis_cfg()
    host = os.getenv("REDIS_HOST", redis_cfg.get("host", "127.0.0.1"))
    port = int(os.getenv("REDIS_PORT", redis_cfg.get("port", 6379)))
    db = int(os.getenv("REDIS_DB", redis_cfg.get("db", 0)))
    username = os.getenv("REDIS_USERNAME", redis_cfg.get("username", None))
    password = os.getenv("REDIS_PASSWORD", redis_cfg.get("password", None))
    try:
        client = redis.Redis(
            host=host, port=port, db=db, username=username, password=password,
            decode_responses=True, socket_connect_timeout=1.0, socket_timeout=1.0,
        )
        client.ping()
        _eval_backend = "redis"
        logger.info(f"[eval] using Redis-backed PIR eval counters at {host}:{port}/{db}")
        return client
    except Exception as e:
        _eval_backend = "memory_redis_unavailable"
        logger.error(f"[eval] Redis unavailable for PIR eval counters; using fallback: {e}")
        return None


def _safe_metric_part(value: Optional[str], default: str) -> str:
    value = (value or default).strip()
    value = re.sub(r"[^A-Za-z0-9_.:-]", "_", value)
    return value[:160] if value else default


def _eval_key(run_id: str, point_id: str, request_type: str) -> str:
    return f"{EVAL_PREFIX}:{_safe_metric_part(run_id, 'unlabeled_run')}:{_safe_metric_part(point_id, 'unlabeled_point')}:backend_invoked:{_safe_metric_part(request_type, 'unknown')}"


def _record_backend_invocation(run_id: Optional[str], point_id: Optional[str], request_type: Optional[str]) -> None:
    if not run_id and not point_id and not request_type:
        return
    key = _eval_key(run_id or "unlabeled_run", point_id or "unlabeled_point", request_type or "unknown")
    if _eval_redis is not None:
        try:
            _eval_redis.incrby(key, 1)
            return
        except Exception as e:
            logger.error(f"[eval] Redis INCR failed for {key}; using fallback: {e}")
    with _eval_fallback_lock:
        _eval_fallback[key] = int(_eval_fallback.get(key, 0)) + 1


def _parse_eval_key(key: str) -> Optional[dict]:
    # Format: prefix:run_id:point_id:backend_invoked:type
    prefix = f"{EVAL_PREFIX}:"
    if not key.startswith(prefix):
        return None
    rest = key[len(prefix):]
    marker = ":backend_invoked:"
    if marker not in rest:
        return None
    left, request_type = rest.rsplit(marker, 1)
    if ":" not in left:
        return None
    run_id, point_id = left.split(":", 1)
    return {"run_id": run_id, "point_id": point_id, "request_type": request_type}


def _eval_scan(pattern: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    if _eval_redis is not None:
        try:
            for key in _eval_redis.scan_iter(match=pattern, count=500):
                try:
                    out[str(key)] = int(_eval_redis.get(key) or 0)
                except Exception:
                    out[str(key)] = 0
            return out
        except Exception as e:
            logger.error(f"[eval] Redis SCAN failed for {pattern}; using fallback: {e}")
    with _eval_fallback_lock:
        for key, value in _eval_fallback.items():
            if re.fullmatch(pattern.replace("*", ".*"), key):
                out[key] = int(value)
    return out


def _eval_metrics_snapshot(run_id: Optional[str] = None, point_id: Optional[str] = None) -> dict:
    run = _safe_metric_part(run_id, "*") if run_id else "*"
    point = _safe_metric_part(point_id, "*") if point_id else "*"
    pattern = f"{EVAL_PREFIX}:{run}:{point}:backend_invoked:*"
    raw = _eval_scan(pattern)
    by_type: Dict[str, int] = {}
    by_point: Dict[str, Dict[str, int]] = {}
    total = 0
    for key, value in raw.items():
        parsed = _parse_eval_key(key)
        if not parsed:
            continue
        req_type = parsed["request_type"]
        p_id = parsed["point_id"]
        by_type[req_type] = by_type.get(req_type, 0) + int(value)
        by_point.setdefault(p_id, {})[req_type] = by_point.setdefault(p_id, {}).get(req_type, 0) + int(value)
        total += int(value)
    return {
        "ok": True,
        "backend": _eval_backend,
        "prefix": EVAL_PREFIX,
        "run_id_filter": run_id,
        "point_id_filter": point_id,
        "total_backend_invocations": total,
        "by_type": by_type,
        "by_point": by_point,
        "raw_key_count": len(raw),
    }


def _eval_metrics_reset(run_id: Optional[str] = None, point_id: Optional[str] = None) -> dict:
    run = _safe_metric_part(run_id, "*") if run_id else "*"
    point = _safe_metric_part(point_id, "*") if point_id else "*"
    pattern = f"{EVAL_PREFIX}:{run}:{point}:backend_invoked:*"
    deleted = 0
    if _eval_redis is not None:
        try:
            keys = list(_eval_redis.scan_iter(match=pattern, count=500))
            if keys:
                deleted = int(_eval_redis.delete(*keys))
            return {"ok": True, "backend": _eval_backend, "deleted": deleted, "pattern": pattern}
        except Exception as e:
            logger.error(f"[eval] Redis reset failed for {pattern}; using fallback: {e}")
    with _eval_fallback_lock:
        keys = [k for k in _eval_fallback if re.fullmatch(pattern.replace("*", ".*"), k)]
        for k in keys:
            _eval_fallback.pop(k, None)
        deleted = len(keys)
    return {"ok": True, "backend": _eval_backend, "deleted": deleted, "pattern": pattern}


_eval_redis = _init_eval_redis_client()


@app.get("/api/v1/pir/eval_metrics")
async def get_eval_metrics(run_id: Optional[str] = Query(None), point_id: Optional[str] = Query(None)):
    return _eval_metrics_snapshot(run_id=run_id, point_id=point_id)


@app.post("/api/v1/pir/eval_metrics/reset")
async def reset_eval_metrics(run_id: Optional[str] = Query(None), point_id: Optional[str] = Query(None)):
    return _eval_metrics_reset(run_id=run_id, point_id=point_id)


@app.post("/api/v1/pir/query")
async def execute_pir_query(req: PIRQueryRequest):
    logger.info(f"Received query [{req.query_payload[:15]}...]. Mode: {ENGINE_MODE}")

    # This is the ground-truth point: if this function runs, the request has
    # crossed the verifier boundary and entered the PIR backend service.
    _record_backend_invocation(req.eval_run_id, req.eval_point_id, req.eval_request_type)

    pir_index = map_query_to_index(req.query_payload, DB_NUM_ENTRIES)

    # 仅在开启开关时进行规模延迟惩罚（保护真实 Subprocess 路径）
    if ENABLE_SCALING_DELAY:
        await asyncio.sleep(EMULATED_DELAY_SEC)

    response_meta = {
        "dataset_path": dataset_path,
        "dataset_size_gb": db_size_gb,
        "emulated_backend_delay_ms": EMULATED_DELAY_SEC * 1000,
        "query_type_received": req.query_payload[:32]  # 截断防脏日志
    }

    if ENGINE_MODE == "stub":
        if req.query_payload == "trigger_failure_test":
            raise HTTPException(status_code=500, detail="Simulated PIR backend crash")
        return {
            "data": f"stub_pir_result_for_{req.query_payload[:10]}",
            "mapped_index": pir_index,
            "recovered_val": 0,
            "meta": response_meta
        }

    elif ENGINE_MODE == "subprocess":
        try:
            result, recovered_val, ext_meta = await call_external_pir_engine(
                ENGINE_CMD, ENGINE_TIMEOUT, req.query_payload, pir_index, WORKING_DIR
            )

            logger.info(f"External PIR engine executed successfully. Meta: {ext_meta}")
            if isinstance(ext_meta, dict):
                response_meta.update(ext_meta)

            response_dict = {
                "data": result,
                "mapped_index": pir_index,
                "recovered_val": recovered_val,
                "meta": response_meta
            }

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