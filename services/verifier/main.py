# services/verifier/main.py
import sys
import base64
import requests
import time
import httpx
import hmac
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
import uvicorn

root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.logging_utils import setup_logger
from common.models import RequestInstance, PIRResponse, Decision, TicketState
from services.verifier.crypto import crypto_manager
from services.verifier.state_manager import state_manager
from common.crypto_utils import (
    derive_sk_t, compute_query_commitment,
    serialize_witness, compute_binding_tag,
    is_epoch_valid
)

config = load_config()
logger = setup_logger("verifier", config)

verifier_cfg = config.get("verifier", {})
SERVER_HOST = verifier_cfg.get("host", "127.0.0.1")
SERVER_PORT = verifier_cfg.get("port", 8002)

issuer_cfg = config.get("issuer", {})
ISSUER_URL = f"http://{issuer_cfg.get('host', '127.0.0.1')}:{issuer_cfg.get('port', 8001)}/api/v1/issuer"

# 提取 PIR Server 配置
pir_cfg = config.get("pir_server", {})
PIR_SERVER_URL = f"http://{pir_cfg.get('host', '127.0.0.1')}:{pir_cfg.get('port', 8003)}/api/v1/pir"

# 提取 Epoch 统一配置块
epoch_cfg = config.get("epoch", {})
EPOCH_DURATION = epoch_cfg.get("duration_sec", 3600)
GRACE_WINDOW = epoch_cfg.get("grace_window_sec", 300)

# 缓存公钥（当前为单进程原型缓存）
issuer_public_key = {"n": None, "e": None}


def fetch_issuer_public_key():
    logger.info("Fetching public key from Issuer...")
    try:
        # 新逻辑：直接拉取纯净的公钥
        resp = requests.get(f"{ISSUER_URL}/public_key", timeout=5)
        resp.raise_for_status()
        pub_key = resp.json()

        if "n" not in pub_key or "e" not in pub_key:
            raise RuntimeError("Public key structure invalid (missing n or e)")

        def parse_hex(val: str):
            v = val.lower()
            return v[2:] if v.startswith("0x") else v

        issuer_public_key["n"] = int(parse_hex(pub_key["n"]), 16)
        issuer_public_key["e"] = int(parse_hex(pub_key["e"]), 16)
        logger.info("Successfully cached Issuer public key.")
    except Exception as e:
        logger.error(f"Critical: Failed to fetch public key: {e}")
        # 失败时清空旧缓存，防止脑裂
        issuer_public_key["n"] = None
        issuer_public_key["e"] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    fetch_issuer_public_key()
    yield


app = FastAPI(title="PIR Abuse Control - Verifier Service", version="1.0", lifespan=lifespan)


# --- 独立封装的网络桥接层 ---
async def call_pir_server(query_payload: str) -> tuple[bool, str]:
    """
    独立封装的网络桥接层，避免 execute_query 过度臃肿。
    返回 (is_success, data_or_error_msg)
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{PIR_SERVER_URL}/query",
                json={"query_payload": query_payload},
                timeout=15.0
            )
            resp.raise_for_status()
            return True, resp.json().get("data", "no_data")
    except httpx.TimeoutException:
        logger.error("PIR Server connection or read timed out.")
        return False, "timeout"
    except httpx.HTTPStatusError as e:
        logger.error(f"PIR Server returned HTTP error: {e.response.status_code}")
        return False, f"http_error_{e.response.status_code}"
    except httpx.RequestError as e:
        logger.error(f"PIR Server request failed (connection refused/aborted): {e}")
        return False, "connection_error"
    except Exception as e:
        logger.error(f"Unexpected error calling PIR Server: {e}")
        return False, "unknown_error"


@app.post("/api/v1/verifier/execute", response_model=PIRResponse)
async def execute_query(req: RequestInstance):
    # 修正日志打印：此时不能保证 ticket 存在，避免抛出 AttributeError
    logger.info(f"Received request {req.request_id}...")

    # --- 0a. 缺失票据拦截 (Day 21 新增) ---
    if req.ticket is None:
        logger.warning(f"Request {req.request_id} REJECTED: Missing Ticket")
        return PIRResponse(
            request_id=req.request_id, decision=Decision.REJECTED,
            ticket_state=TicketState.UNUSED, reason="Missing Ticket in request"
        )

    # 确认有票据后，补充打印 SN 信息
    logger.info(f"Processing request {req.request_id} for SN: {req.ticket.sn[:16]}...")

    # --- 0b. 纪元时间窗检查 (Day 18: 前置快拒绝) ---
    if not is_epoch_valid(req.ticket.epoch_id, int(time.time()), EPOCH_DURATION, GRACE_WINDOW):
        logger.warning(f"Fast-rejecting expired ticket epoch: {req.ticket.epoch_id}")
        return PIRResponse(
            request_id=req.request_id,
            decision=Decision.REJECTED,
            ticket_state=TicketState.UNUSED,
            reason=f"Ticket epoch {req.ticket.epoch_id} has expired."
        )

    # --- 1. 检查当前状态 (拦截非 UNUSED 状态的票据) ---
    current_state = state_manager.get_state(req.ticket.sn)
    if current_state in (TicketState.CONSUMED, TicketState.PENDING, TicketState.FAILED):
        logger.warning(f"Request {req.request_id} REJECTED: Ticket is {current_state.value}")
        return PIRResponse(
            request_id=req.request_id, decision=Decision.REJECTED,
            ticket_state=current_state, reason=f"Ticket already {current_state.value}"
        )

    # --- 2. 获取公钥与验证票据签名 ---
    if issuer_public_key["n"] is None:
        fetch_issuer_public_key()
        if issuer_public_key["n"] is None:
            raise HTTPException(status_code=503, detail="Issuer PK not available")

    is_valid_sig = crypto_manager.verify_ticket_signature(
        sn_hex=req.ticket.sn,
        epoch_id=req.ticket.epoch_id,
        sigma_b64=req.ticket.sigma,
        n=issuer_public_key["n"],
        e=issuer_public_key["e"]
    )

    if not is_valid_sig:
        return PIRResponse(
            request_id=req.request_id, decision=Decision.REJECTED,
            ticket_state=TicketState.UNUSED, reason="Invalid Ticket Signature"
        )

    # --- 3. 验证绑定 (Binding Consistency Check) ---
    if req.witness is None:
        return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED,
                           reason="Missing Request Witness")

    if req.binding_tag is None:
        return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED,
                           reason="Missing Binding Tag")

    # 优化可读性：将 expected_c_q 提至外部，避免后续 Audit Stub 引用悬空
    expected_c_q = compute_query_commitment(req.query_payload)

    try:
        sigma_bytes = base64.b64decode(req.ticket.sigma, validate=True)
        expected_sk_t = derive_sk_t(sigma_bytes, req.ticket.sn, req.ticket.epoch_id)
        witness_bytes = serialize_witness(req.witness.model_dump())
        expected_binding_tag = compute_binding_tag(expected_sk_t, expected_c_q, witness_bytes)

        # 引入常量时间比较，防时序攻击
        if not hmac.compare_digest(req.binding_tag, expected_binding_tag):
            return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED,
                               ticket_state=TicketState.UNUSED, reason="Binding Consistency Check Failed")

    except Exception as e:
        # 异常兜底：非法 base64、缺失字段等导致计算崩溃，统一返回拒绝，不炸 500
        logger.warning(f"Binding verification error: {e}")
        return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED,
                           ticket_state=TicketState.UNUSED, reason="Invalid Binding Material")

    # --- 4. 原子锁定为 PENDING (防双花) ---
    if not state_manager.try_lock(req.ticket.sn, lock_ttl_sec=30):
        logger.warning(f"Request {req.request_id} REJECTED: Failed to lock ticket (Concurrency attack?)")
        return PIRResponse(
            request_id=req.request_id, decision=Decision.REJECTED,
            ticket_state=TicketState.PENDING, reason="Concurrent ticket usage detected"
        )
    logger.info(f"Ticket {req.ticket.sn[:16]} state transition: UNUSED -> PENDING")

    # --- 5. 通过 HTTP 转发至 PIR Server (网络桥接) ---
    is_success, pir_result_or_err = await call_pir_server(req.query_payload)

    if is_success:
        # --- 6a. 执行成功 -> CONSUMED ---
        state_manager.mark_consumed(req.ticket.sn)
        final_decision = Decision.SUCCESS
        final_state = TicketState.CONSUMED
        reason_msg = "PIR execution completed"
        pir_data = pir_result_or_err
        logger.info(f"Ticket {req.ticket.sn[:16]} state transition: PENDING -> CONSUMED")
    else:
        # --- 6b. 执行异常或超时 -> FAILED (票据严格烧毁) ---
        state_manager.mark_failed(req.ticket.sn)
        final_decision = Decision.REJECTED
        final_state = TicketState.FAILED
        # 坚决不透传底层错误给用户，兼容 Day 12 脚本
        reason_msg = "PIR execution failed, ticket burned"
        pir_data = None
        # 但在日志中记录精细化错误分类，方便后续排障
        logger.error(f"PIR Execution failed due to [{pir_result_or_err}]. Ticket {req.ticket.sn[:16]} burned (FAILED).")

    # --- 7. 审计留痕 (当前为本地组装与日志存根，下阶段接后台投递) ---
    audit_record_stub = {
        "request_id": req.request_id,
        "sn": req.ticket.sn,
        "query_commitment": expected_c_q,
        "binding_tag": req.binding_tag,
        "epoch_id": req.ticket.epoch_id,
        "decision": final_decision.value,
        "reason": reason_msg,
        "timestamp_ms": int(time.time() * 1000)
    }
    logger.info(
        f"[Audit Stub] Would report to Auditor: SN={audit_record_stub['sn'][:16]}..., Decision={audit_record_stub['decision']}")

    return PIRResponse(
        request_id=req.request_id, decision=final_decision,
        ticket_state=final_state, reason=reason_msg, data=pir_data
    )


if __name__ == "__main__":
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)