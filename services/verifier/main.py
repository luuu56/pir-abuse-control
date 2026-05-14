# services/verifier/main.py
import sys
import os
import base64
import requests
import time
import httpx
import hmac
import socket
from typing import Any, Optional
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
import uvicorn

try:
    import redis
except ImportError:  # Redis is strongly recommended for multi-worker metrics.
    redis = None

root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.logging_utils import setup_logger
from common.models import RequestInstance, PIRResponse, Decision, TicketState, PIRResultPayload
from services.verifier.crypto import crypto_manager
from services.verifier.state_manager import get_state_manager
from common.crypto_utils import (
    derive_sk_t, compute_query_commitment,
    serialize_witness, compute_binding_tag,
    is_epoch_valid
)

config = load_config()
logger = setup_logger("verifier", config)
ablation_cfg = config.get("ablation", {})  # 加载消融配置

verifier_cfg = config.get("verifier", {})
SERVER_HOST = verifier_cfg.get("host", "127.0.0.1")
SERVER_PORT = verifier_cfg.get("port", 8002)
ISSUER_URL = f"http://{config.get('issuer', {}).get('host', '127.0.0.1')}:{config.get('issuer', {}).get('port', 8001)}/api/v1/issuer"
PIR_SERVER_URL = f"http://{config.get('pir_server', {}).get('host', '127.0.0.1')}:{config.get('pir_server', {}).get('port', 8003)}/api/v1/pir/query"
AUDITOR_URL = f"http://{config.get('auditor', {}).get('host', '127.0.0.1')}:{config.get('auditor', {}).get('port', 8004)}/api/v1/auditor/report"

epoch_cfg = config.get("epoch", {})
EPOCH_DURATION = epoch_cfg.get("duration_sec", 3600)
GRACE_WINDOW = epoch_cfg.get("grace_window_sec", 300)

issuer_public_key = {"n": None, "e": None}

# -----------------------------------------------------------------------------
# Multi-worker-safe verifier metrics
# -----------------------------------------------------------------------------
# Uvicorn workers are separate OS processes. A normal Python dictionary such as
# {"pir_invoked": ...} is therefore per-worker and cannot represent global
# totals. We keep Redis-backed counters here so /metrics remains meaningful when
# the verifier is started with workers=4. If Redis is temporarily unavailable,
# the service falls back to per-process in-memory counters and marks the metrics
# backend accordingly.
METRIC_NAMES = ("total_requests", "blocked_before_pir", "pir_invoked")
_metrics_fallback = {name: 0 for name in METRIC_NAMES}
_metrics_redis = None
_metrics_backend = "memory"


def _get_redis_cfg() -> dict:
    # Be permissive about config section names because different versions of the
    # prototype have used different labels for the same Redis service.
    return (
            config.get("redis", {})
            or config.get("state_store", {})
            or config.get("redemption_store", {})
            or {}
    )


def _init_metrics_redis_client():
    global _metrics_backend
    if redis is None:
        logger.warning("[metrics] redis package is not installed; using per-worker memory metrics.")
        _metrics_backend = "memory_no_redis_package"
        return None

    redis_cfg = _get_redis_cfg()
    host = os.getenv("REDIS_HOST", redis_cfg.get("host", "127.0.0.1"))
    port = int(os.getenv("REDIS_PORT", redis_cfg.get("port", 6379)))
    db = int(os.getenv("REDIS_DB", redis_cfg.get("db", 0)))
    username = os.getenv("REDIS_USERNAME", redis_cfg.get("username", None))
    password = os.getenv("REDIS_PASSWORD", redis_cfg.get("password", None))

    try:
        client = redis.Redis(
            host=host,
            port=port,
            db=db,
            username=username,
            password=password,
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
        client.ping()
        _metrics_backend = "redis"
        logger.info(f"[metrics] using Redis-backed verifier metrics at {host}:{port}/{db}")
        return client
    except Exception as e:
        _metrics_backend = "memory_redis_unavailable"
        logger.error(
            f"[metrics] Redis unavailable for verifier metrics; falling back to per-worker memory metrics: {e}")
        return None


def _metric_prefix() -> str:
    redis_cfg = _get_redis_cfg()
    return str(redis_cfg.get("metrics_prefix", "verifier_metrics"))


def _metric_key(name: str) -> str:
    return f"{_metric_prefix()}:{name}"


def metrics_incr(name: str, amount: int = 1) -> int:
    if name not in METRIC_NAMES:
        raise ValueError(f"unknown verifier metric: {name}")

    if _metrics_redis is not None:
        try:
            return int(_metrics_redis.incrby(_metric_key(name), amount))
        except Exception as e:
            logger.error(f"[metrics] Redis INCR failed for {name}; using process-local fallback: {e}")

    _metrics_fallback[name] = int(_metrics_fallback.get(name, 0)) + amount
    return _metrics_fallback[name]


def metrics_snapshot() -> dict:
    values = {}

    if _metrics_redis is not None:
        try:
            raw_values = _metrics_redis.mget([_metric_key(name) for name in METRIC_NAMES])
            values = {
                name: int(value) if value is not None else 0
                for name, value in zip(METRIC_NAMES, raw_values)
            }
        except Exception as e:
            logger.error(f"[metrics] Redis MGET failed; using process-local fallback snapshot: {e}")
            values = dict(_metrics_fallback)
    else:
        values = dict(_metrics_fallback)

    # Keep backward compatibility with the evaluation script, which checks either
    # pir_invoked_total or pir_invoked.
    values["pir_invoked_total"] = values.get("pir_invoked", 0)
    values["metrics_backend"] = _metrics_backend
    values["worker_pid"] = os.getpid()
    return values


def metrics_reset() -> dict:
    if _metrics_redis is not None:
        try:
            _metrics_redis.delete(*[_metric_key(name) for name in METRIC_NAMES])
        except Exception as e:
            logger.error(f"[metrics] Redis DELETE failed during reset: {e}")

    for name in METRIC_NAMES:
        _metrics_fallback[name] = 0

    return metrics_snapshot()


_metrics_redis = _init_metrics_redis_client()


def fetch_issuer_public_key():
    try:
        resp = requests.get(f"{ISSUER_URL}/public_key", timeout=5)
        resp.raise_for_status()
        pub_key = resp.json()
        issuer_public_key["n"] = int(pub_key["n"].replace("0x", ""), 16)
        issuer_public_key["e"] = int(pub_key["e"].replace("0x", ""), 16)
    except Exception as e:
        logger.error(f"Critical: Failed to fetch public key: {e}")


def dispatch_l4_block_signal(client_ip: str, duration_sec: int = 10):
    try:
        logger.info(f"[TRACE] Preparing derived L4 block for ip={client_ip} ttl={duration_sec}")

        # [修复 1]：剥离 Uvicorn 附带的 IPv6 映射前缀
        if client_ip.startswith("::ffff:"):
            client_ip = client_ip.replace("::ffff:", "")

        socket.inet_aton(client_ip)
        allow_localhost_block = config.get("ebpf", {}).get("allow_localhost_block", False)

        if client_ip in ["127.0.0.1", "localhost"] and not allow_localhost_block:
            logger.warning(
                f"[TRACE] Derived L4 block aborted: Localhost detected ({client_ip}) without allow_localhost_block: true")
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(f"BLOCK {client_ip} {duration_sec}".encode('utf-8'), ("127.0.0.1", 9002))
        logger.info(f"[TRACE] derived L4 block dispatched successfully to {client_ip}")

    except Exception as e:
        # [修复 2]：绝不允许静默吞没！把真正的报错炸出来！
        logger.error(f"[TRACE] derived L4 block dispatch failed: {e}")


async def dispatch_audit_log(record_dict: dict):
    async with httpx.AsyncClient() as client:
        try:
            await client.post(AUDITOR_URL, json=record_dict, timeout=2.0)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    fetch_issuer_public_key()
    yield


app = FastAPI(title="PIR Abuse Control - Verifier", lifespan=lifespan)


@app.get("/api/v1/verifier/metrics")
async def get_metrics():
    return metrics_snapshot()


@app.post("/api/v1/verifier/metrics/reset")
async def reset_metrics():
    return metrics_reset()


async def call_pir_server(
        query_payload: str,
        eval_run_id: Optional[str] = None,
        eval_point_id: Optional[str] = None,
        eval_request_type: Optional[str] = None,
) -> tuple[bool, str, Optional[int], Optional[int], Optional[str]]:
    """Call the PIR backend.

    The eval_* fields are evaluation-only metadata used to record backend
    invocation ground truth. They are not used by verifier security logic.
    """
    try:
        pir_request = {"query_payload": query_payload}
        if eval_run_id:
            pir_request["eval_run_id"] = eval_run_id
        if eval_point_id:
            pir_request["eval_point_id"] = eval_point_id
        if eval_request_type:
            pir_request["eval_request_type"] = eval_request_type

        async with httpx.AsyncClient() as client:
            resp = await client.post(PIR_SERVER_URL, json=pir_request, timeout=20.0)
            if resp.status_code == 200:
                body = resp.json()
                return True, body.get("data"), body.get("mapped_index"), body.get("recovered_val"), body.get(
                    "apir_proof")
            return False, resp.text, None, None, None
    except Exception as e:
        return False, str(e), None, None, None


def _run_precondition_check(req: RequestInstance, sm) -> PIRResponse | None:
    if req.ticket is None:
        return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED,
                           reason="Missing Ticket")

    # 消融开关: 关闭 Epoch
    if not ablation_cfg.get("disable_epoch", False):
        if not is_epoch_valid(req.ticket.epoch_id, int(time.time()), EPOCH_DURATION, GRACE_WINDOW):
            return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED,
                               reason="Ticket expired.")

    # 消融开关: 关闭并发状态锁 (重放检测前置判断)
    if not ablation_cfg.get("disable_consume_lock", False):
        current_state = sm.get_state(req.ticket.sn)
        if current_state != TicketState.UNUSED:
            return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=current_state,
                               reason="Ticket consumed")

    return None


def _run_crypto_verification(req: RequestInstance, expected_c_q: str) -> PIRResponse | None:
    if issuer_public_key["n"] is None: fetch_issuer_public_key()

    # 签名本身有效性必须验证，这代表它是"真正的票据"，消融的是绑定关系
    is_valid_sig = crypto_manager.verify_ticket_signature(
        sn_hex=req.ticket.sn, epoch_id=req.ticket.epoch_id, sigma_b64=req.ticket.sigma,
        n=issuer_public_key["n"], e=issuer_public_key["e"]
    )
    if not is_valid_sig:
        return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED,
                           reason="Invalid Sig")

    # 消融开关: 关闭 Binding
    if not ablation_cfg.get("disable_binding", False):
        if req.witness is None or req.binding_tag is None:
            return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED,
                               reason="Missing Binding")
        try:
            sigma_bytes = base64.b64decode(req.ticket.sigma, validate=True)
            expected_sk_t = derive_sk_t(sigma_bytes, req.ticket.sn, req.ticket.epoch_id)
            witness_bytes = serialize_witness(req.witness.model_dump())
            expected_binding_tag = compute_binding_tag(expected_sk_t, expected_c_q, witness_bytes)
            if not hmac.compare_digest(req.binding_tag, expected_binding_tag):
                return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED,
                                   ticket_state=TicketState.UNUSED, reason="Binding Check Failed")
        except Exception:
            return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED,
                               reason="Invalid Binding Material")

    return None


@app.post("/api/v1/verifier/execute", response_model=PIRResponse)
async def execute_query(req: RequestInstance, request: Request, background_tasks: BackgroundTasks):
    sm = get_state_manager()
    metrics_incr("total_requests")

    # 动态获取配置
    disable_consume_lock = ablation_cfg.get("disable_consume_lock", False)
    ebpf_ttl = config.get("ebpf", {}).get("derived_block_ttl_sec", 10)

    pre_err = _run_precondition_check(req, sm)
    if pre_err:
        metrics_incr("blocked_before_pir")
        # 【修复 1】：无论是 CONSUMED 还是 PENDING，只要被重放防线拦下，立刻拉黑！
        if pre_err.ticket_state in [TicketState.CONSUMED, TicketState.PENDING] and not disable_consume_lock:
            client_ip = request.client.host if request.client else "unknown"
            logger.info(f"[TRACE] replay detected (state={pre_err.ticket_state}), triggering L4 block for {client_ip}")
            dispatch_l4_block_signal(client_ip, ebpf_ttl)
        else:
            logger.info(
                f"[TRACE] pre_condition failed but NOT a replay (state={pre_err.ticket_state}). Skipping L4 block.")
        return pre_err

    expected_c_q = compute_query_commitment(req.query_payload)
    crypto_err = _run_crypto_verification(req, expected_c_q)
    if crypto_err:
        metrics_incr("blocked_before_pir")
        return crypto_err

    # 消融开关: 不执行原子加锁
    if not disable_consume_lock:
        if not sm.try_lock(req.ticket.sn, lock_ttl_sec=30):
            metrics_incr("blocked_before_pir")
            client_ip = request.client.host if request.client else "unknown"
            logger.info(f"[TRACE] Concurrent collision detected, triggering L4 block for {client_ip}")
            dispatch_l4_block_signal(client_ip, ebpf_ttl)
            return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.PENDING,
                               reason="Concurrent collision")

    metrics_incr("pir_invoked")
    success, payload_or_error, mapped_index, recovered_val, apir_proof = await call_pir_server(
        req.query_payload,
        eval_run_id=req.eval_run_id,
        eval_point_id=req.eval_point_id,
        eval_request_type=req.eval_request_type,
    )

    if success:
        if mapped_index is None or recovered_val is None:
            if not disable_consume_lock: get_state_manager().mark_failed(req.ticket.sn, epoch_id=req.ticket.epoch_id)
            decision, reason, final_data = Decision.REJECTED, "Malformed PIR response", None
        else:
            if not disable_consume_lock: get_state_manager().mark_consumed(req.ticket.sn, epoch_id=req.ticket.epoch_id)
            decision, reason = Decision.SUCCESS, "PIR execution completed"
            final_data = PIRResultPayload(result_string=payload_or_error, mapped_index=mapped_index,
                                          recovered_val=recovered_val, apir_proof=apir_proof)
    else:
        if not disable_consume_lock: get_state_manager().mark_failed(req.ticket.sn, epoch_id=req.ticket.epoch_id)
        decision, reason, final_data = Decision.REJECTED, f"PIR failed: {payload_or_error}", None

    # 后置状态收口
    final_state = TicketState.UNUSED if disable_consume_lock else (
        TicketState.CONSUMED if success else TicketState.FAILED)

    background_tasks.add_task(dispatch_audit_log, {
        "request_id": req.request_id, "sn": req.ticket.sn, "query_commitment": expected_c_q,
        "binding_tag": req.binding_tag, "epoch_id": req.ticket.epoch_id, "decision": decision.value,
        "reason": reason, "timestamp_ms": int(time.time() * 1000), "prev_hash": "stub", "entry_mac": "stub"
    })

    return PIRResponse(request_id=req.request_id, decision=decision, ticket_state=final_state, reason=reason,
                       data=final_data)


if __name__ == "__main__":
    # In multi-worker mode, pass the module path string instead of the app object.
    # Start from the project root so "services.verifier.main:app" can be imported.
    uvicorn.run(
        "services.verifier.main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        workers=int(verifier_cfg.get("workers", 4)),
        log_level="info",
    )