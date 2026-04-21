# services/verifier/main.py
import sys
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

root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.logging_utils import setup_logger
# 引入了 PIRResultPayload 强类型模型
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

# 配置提取
verifier_cfg = config.get("verifier", {})
SERVER_HOST = verifier_cfg.get("host", "127.0.0.1")
SERVER_PORT = verifier_cfg.get("port", 8002)
ISSUER_URL = f"http://{config.get('issuer', {}).get('host', '127.0.0.1')}:{config.get('issuer', {}).get('port', 8001)}/api/v1/issuer"
PIR_SERVER_URL = f"http://{config.get('pir_server', {}).get('host', '127.0.0.1')}:{config.get('pir_server', {}).get('port', 8003)}/api/v1/pir/query"  # 修正了 endpoint 以对齐 pir_server
AUDITOR_URL = f"http://{config.get('auditor', {}).get('host', '127.0.0.1')}:{config.get('auditor', {}).get('port', 8004)}/api/v1/auditor/report"

# Epoch 逻辑参数
epoch_cfg = config.get("epoch", {})
EPOCH_DURATION = epoch_cfg.get("duration_sec", 3600)
GRACE_WINDOW = epoch_cfg.get("grace_window_sec", 300)

issuer_public_key = {"n": None, "e": None}


def fetch_issuer_public_key():
    logger.info("Fetching public key from Issuer...")
    try:
        resp = requests.get(f"{ISSUER_URL}/public_key", timeout=5)
        resp.raise_for_status()
        pub_key = resp.json()

        def parse_hex(val: str):
            return val[2:] if val.lower().startswith("0x") else val

        issuer_public_key["n"] = int(parse_hex(pub_key["n"]), 16)
        issuer_public_key["e"] = int(parse_hex(pub_key["e"]), 16)
        logger.info("Successfully cached Issuer public key.")
    except Exception as e:
        logger.error(f"Critical: Failed to fetch public key: {e}")
        issuer_public_key.update({"n": None, "e": None})


# --- Day 40 新增：派生 L4 封禁信号 ---
def dispatch_l4_block_signal(client_ip: str, duration_sec: int = 10):
    """派生 L4 封禁信号，不改变 Redis 业务决策"""
    try:
        # 收口校验：仅处理 IPv4，遇到 IPv6 / unknown / invalid 直接跳过
        socket.inet_aton(client_ip) 
        if client_ip in ["127.0.0.1", "localhost"]:
            return
            
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        msg = f"BLOCK {client_ip} {duration_sec}".encode('utf-8')
        sock.sendto(msg, ("127.0.0.1", 9002))
        logger.info(f"Derived L4 block signal dispatched for IP {client_ip}")
    except Exception:
        # 非 IPv4 或 UDP 发送失败不影响主流程
        pass


async def dispatch_audit_log(record_dict: dict):
    """异步投递审计日志"""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(AUDITOR_URL, json=record_dict, timeout=2.0)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"⚠️ Auditor report failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    fetch_issuer_public_key()
    yield


app = FastAPI(title="PIR Abuse Control - Verifier", lifespan=lifespan)

# --- Day 33 新增：轻量级内存监控指标 ---
verifier_metrics = {
    "total_requests": 0,
    "blocked_before_pir": 0,
    "pir_invoked": 0  # 语义：已穿越前置盾牌，真正开始调用底层 PIR 计算的请求数
}


@app.get("/api/v1/verifier/metrics")
async def get_metrics():
    """实时统计被拦截的恶意请求比例"""
    total = verifier_metrics["total_requests"]
    blocked = verifier_metrics["blocked_before_pir"]
    ratio = (blocked / total * 100) if total > 0 else 0.0
    return {
        "total_requests": total,
        "pir_invoked": verifier_metrics["pir_invoked"],
        "blocked_before_pir": blocked,
        "block_ratio_percent": round(ratio, 2)
    }


@app.get("/api/v1/verifier/ticket_state/{sn}")
async def query_ticket_state(sn: str):
    sn = sn.lower()
    if not (len(sn) == 64 and all(c in "0123456789abcdef" for c in sn)):
        raise HTTPException(status_code=400, detail="Invalid SN format: must be 64-char hex")
    state = get_state_manager().get_state(sn)
    return {"sn": sn, "ticket_state": state.value}


async def call_pir_server(query_payload: str) -> tuple[bool, str, Optional[int], Optional[int]]:
    """
    Day 32 升级：从 PIR Server 获取结构化结果并透传
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                PIR_SERVER_URL,
                json={"query_payload": query_payload},
                timeout=20.0
            )
            if resp.status_code == 200:
                body = resp.json()
                data = body.get("data")
                mapped_index = body.get("mapped_index")
                recovered_val = body.get("recovered_val")

                logger.info(f"PIR Server returned SUCCESS. Index: {mapped_index}")
                return True, data, mapped_index, recovered_val
            else:
                logger.error(f"PIR Server Error: {resp.status_code} - {resp.text}")
                return False, resp.text, None, None
    except Exception as e:
        logger.error(f"PIR Bridge Exception: {e}")
        return False, str(e), None, None


# ---------------------------------------------------------
# 重构阶段 1: 前置规则引擎 (Rule Engine)
# ---------------------------------------------------------
def _run_precondition_check(req: RequestInstance, sm) -> PIRResponse | None:
    if req.ticket is None:
        return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED,
                           reason="Missing Ticket in request")

    if not is_epoch_valid(req.ticket.epoch_id, int(time.time()), EPOCH_DURATION, GRACE_WINDOW):
        return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED,
                           reason=f"Ticket epoch {req.ticket.epoch_id} has expired.")

    current_state = sm.get_state(req.ticket.sn)
    if current_state != TicketState.UNUSED:
        return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=current_state,
                           reason=f"Ticket already {current_state.value}")

    return None


# ---------------------------------------------------------
# 重构阶段 2: 密码学验证层 (Crypto Layer)
# ---------------------------------------------------------
def _run_crypto_verification(req: RequestInstance, expected_c_q: str) -> PIRResponse | None:
    if issuer_public_key["n"] is None:
        fetch_issuer_public_key()
        if issuer_public_key["n"] is None:
            raise HTTPException(status_code=503, detail="Issuer PK not available")

    is_valid_sig = crypto_manager.verify_ticket_signature(
        sn_hex=req.ticket.sn, epoch_id=req.ticket.epoch_id, sigma_b64=req.ticket.sigma,
        n=issuer_public_key["n"], e=issuer_public_key["e"]
    )
    if not is_valid_sig:
        return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED,
                           reason="Invalid Ticket Signature")

    if req.witness is None:
        return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED,
                           reason="Missing Request Witness")
    if req.binding_tag is None:
        return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED,
                           reason="Missing Binding Tag")

    try:
        sigma_bytes = base64.b64decode(req.ticket.sigma, validate=True)
        expected_sk_t = derive_sk_t(sigma_bytes, req.ticket.sn, req.ticket.epoch_id)
        witness_bytes = serialize_witness(req.witness.model_dump())
        expected_binding_tag = compute_binding_tag(expected_sk_t, expected_c_q, witness_bytes)

        if not hmac.compare_digest(req.binding_tag, expected_binding_tag):
            return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED,
                               reason="Binding Consistency Check Failed")
    except Exception as e:
        logger.warning(f"Binding computation error: {e}")
        return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED,
                           reason="Invalid Binding Material")

    return None


# ---------------------------------------------------------
# 主业务编排 (Orchestration)
# ---------------------------------------------------------
# 【Day 40】添加了 request: Request 参数，用于提取真实的客户端 IP
@app.post("/api/v1/verifier/execute", response_model=PIRResponse)
async def execute_query(req: RequestInstance, request: Request, background_tasks: BackgroundTasks):
    logger.info(f"Received request {req.request_id}...")
    sm = get_state_manager()

    verifier_metrics["total_requests"] += 1

    # Step 1: 运行前置规则
    pre_err = _run_precondition_check(req, sm)
    if pre_err:
        logger.warning(f"Request {req.request_id} REJECTED: {pre_err.reason}")
        verifier_metrics["blocked_before_pir"] += 1
        
        # 【Day 40 核心】：明确命中 CONSUMED 状态的重放攻击，派生一个 L4 Fast-Path 封禁指令
        if pre_err.ticket_state == TicketState.CONSUMED:
            client_ip = request.client.host if request.client else "unknown"
            logger.warning(f"Replay detected. Deriving short-term L4 block for source: {client_ip}")
            dispatch_l4_block_signal(client_ip, duration_sec=10)
            
        return pre_err

    # Step 2: 准备承诺并运行密码学校验
    expected_c_q = compute_query_commitment(req.query_payload)
    crypto_err = _run_crypto_verification(req, expected_c_q)
    if crypto_err:
        logger.warning(f"Request {req.request_id} REJECTED: {crypto_err.reason}")
        verifier_metrics["blocked_before_pir"] += 1
        return crypto_err

    # Step 3: 原子加锁 (PENDING)
    if not sm.try_lock(req.ticket.sn, lock_ttl_sec=30):
        logger.warning(f"Request {req.request_id} REJECTED: Concurrent/Pending Collision")
        verifier_metrics["blocked_before_pir"] += 1
        return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.PENDING,
                           reason="Concurrent ticket usage detected")

    logger.info(f"Ticket {req.ticket.sn[:16]} state transition: UNUSED -> PENDING")

    # ==================== [Day 33 探针：严密监视进入 PIR 的请求] ====================
    verifier_metrics["pir_invoked"] += 1
    logger.info(
        f"🚀 [PIR_START] Req:{req.request_id[:8]} | Invoking heavy SimplePIR backend for SN: {req.ticket.sn[:8]}...")

    # Step 4: 执行后端 PIR 服务
    success, payload_or_error, mapped_index, recovered_val = await call_pir_server(req.query_payload)

    logger.info(f"🏁 [PIR_END] Req:{req.request_id[:8]} | SimplePIR backend execution finished. Success: {success}")
    # ==============================================================================

    # Step 5: 状态收敛与强类型数据组装 (Day 35 最终防御版)
    if success:
        if mapped_index is None or recovered_val is None:
            get_state_manager().mark_failed(req.ticket.sn, epoch_id=req.ticket.epoch_id)
            decision = Decision.REJECTED
            reason = "PIR execution failed, ticket burned. Error: malformed PIR response"
            final_data = None
            logger.error(f"PIR Protocol Breach: Success returned but indices are None for SN: {req.ticket.sn[:8]}")
        else:
            get_state_manager().mark_consumed(req.ticket.sn, epoch_id=req.ticket.epoch_id)
            decision = Decision.SUCCESS
            reason = "PIR execution completed"

            final_data = PIRResultPayload(
                result_string=payload_or_error,
                mapped_index=mapped_index,
                recovered_val=recovered_val
            )
    else:
        get_state_manager().mark_failed(req.ticket.sn, epoch_id=req.ticket.epoch_id)
        decision = Decision.REJECTED
        reason = f"PIR execution failed, ticket burned. Error: {payload_or_error}"
        final_data = None

    # Step 6: 审计投递
    audit_payload = {
        "request_id": req.request_id,
        "sn": req.ticket.sn,
        "query_commitment": expected_c_q,
        "binding_tag": req.binding_tag,
        "epoch_id": req.ticket.epoch_id,
        "decision": decision.value,
        "reason": reason,
        "timestamp_ms": int(time.time() * 1000),
        "prev_hash": "stub",
        "entry_mac": "stub"
    }
    background_tasks.add_task(dispatch_audit_log, audit_payload)

    return PIRResponse(
        request_id=req.request_id,
        decision=decision,
        ticket_state=TicketState.CONSUMED if success else TicketState.FAILED,
        reason=reason,
        data=final_data
    )


if __name__ == "__main__":
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)