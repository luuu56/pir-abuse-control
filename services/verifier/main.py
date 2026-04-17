# services/verifier/main.py
import sys
import base64
import requests
import time
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
    serialize_witness, compute_binding_tag
)

config = load_config()
logger = setup_logger("verifier", config)

verifier_cfg = config.get("verifier", {})
SERVER_HOST = verifier_cfg.get("host", "127.0.0.1")
SERVER_PORT = verifier_cfg.get("port", 8002)

issuer_cfg = config.get("issuer", {})
ISSUER_URL = f"http://{issuer_cfg.get('host', '127.0.0.1')}:{issuer_cfg.get('port', 8001)}/api/v1/issuer"

# 缓存公钥（当前为单进程原型缓存）
issuer_public_key = {"n": None, "e": None}


def fetch_issuer_public_key():
    logger.info("Fetching public key from Issuer...")
    try:
        resp = requests.post(f"{ISSUER_URL}/challenge", json={"client_id": "verifier_init"}, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        if "public_key" not in data:
            raise RuntimeError("Issuer response missing 'public_key'")
        pub_key = data["public_key"]
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


@app.post("/api/v1/verifier/execute", response_model=PIRResponse)
def execute_query(req: RequestInstance):
    logger.info(f"Received request {req.request_id} for SN: {req.ticket.sn[:16]}...")

    # --- 0. 检查当前状态 (拦截非 UNUSED 状态的票据) ---
    current_state = state_manager.get_state(req.ticket.sn)
    if current_state in (TicketState.CONSUMED, TicketState.PENDING, TicketState.FAILED):
        logger.warning(f"Request {req.request_id} REJECTED: Ticket is {current_state.value}")
        return PIRResponse(
            request_id=req.request_id, decision=Decision.REJECTED,
            ticket_state=current_state, reason=f"Ticket already {current_state.value}"
        )

    # --- 1. 获取公钥与验证票据签名 ---
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

    # --- 2. 验证绑定 (Binding Consistency Check) ---
    if req.witness is None:
        return PIRResponse(
            request_id=req.request_id, decision=Decision.REJECTED,
            ticket_state=TicketState.UNUSED, reason="Missing Request Witness"
        )

    try:
        sigma_bytes = base64.b64decode(req.ticket.sigma, validate=True)
        expected_sk_t = derive_sk_t(sigma_bytes, req.ticket.sn, req.ticket.epoch_id)
        expected_c_q = compute_query_commitment(req.query_payload)
        witness_bytes = serialize_witness(req.witness.model_dump())
        expected_binding_tag = compute_binding_tag(expected_sk_t, expected_c_q, witness_bytes)

        if req.binding_tag != expected_binding_tag:
            return PIRResponse(
                request_id=req.request_id, decision=Decision.REJECTED,
                ticket_state=TicketState.UNUSED, reason="Binding Consistency Check Failed"
            )
    except Exception as e:
        logger.error(f"Error during binding verification: {e}")
        return PIRResponse(
            request_id=req.request_id, decision=Decision.REJECTED,
            ticket_state=TicketState.UNUSED, reason="Internal Error during Binding Verification"
        )

    # --- 3. 原子锁定为 PENDING (防双花) ---
    if not state_manager.try_lock(req.ticket.sn, lock_ttl_sec=30):
        logger.warning(f"Request {req.request_id} REJECTED: Failed to lock ticket (Concurrency attack?)")
        return PIRResponse(
            request_id=req.request_id, decision=Decision.REJECTED,
            ticket_state=TicketState.PENDING, reason="Concurrent ticket usage detected"
        )
    logger.info(f"Ticket {req.ticket.sn[:16]} state transition: UNUSED -> PENDING")

    # --- 4. 模拟 PIR 执行 ---
    try:
        # # TODO (Day 13): 这里将调用真正的 PIR 引擎
        # time.sleep(0.5)  # 模拟耗时
        # pir_result = "dummy_pir_result_for_testing"

        # 为了测试 FAILED 路径，我们给 execute_query 加一个小后门：如果 query_payload 是特定的触发词，就抛出异常。
        # 模拟执行耗时，方便我们在测试脚本中捕捉 PENDING 状态
        time.sleep(1.0)

        # 【新增：故障模拟触发器】
        if req.query_payload == "trigger_failure_test":
            raise RuntimeError("Simulated PIR backend crash")

        pir_result = "dummy_pir_result_for_testing"
        # --- 5a. 执行成功 -> CONSUMED ---
        state_manager.mark_consumed(req.ticket.sn)
        logger.info(f"Ticket {req.ticket.sn[:16]} state transition: PENDING -> CONSUMED")
        return PIRResponse(
            request_id=req.request_id, decision=Decision.SUCCESS,
            ticket_state=TicketState.CONSUMED, reason="PIR execution completed", data=pir_result
        )
    except Exception as e:
        # --- 5b. 执行异常 -> FAILED (票据严格烧毁) ---
        logger.error(f"PIR Execution failed: {e}")
        state_manager.mark_failed(req.ticket.sn)
        logger.info(f"Ticket {req.ticket.sn[:16]} state transition: PENDING -> FAILED")
        return PIRResponse(
            request_id=req.request_id, decision=Decision.REJECTED,
            ticket_state=TicketState.FAILED, reason="PIR execution failed, ticket burned"
        )


if __name__ == "__main__":
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)