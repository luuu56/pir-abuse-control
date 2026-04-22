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
ablation_cfg = config.get("ablation", {}) # 加载消融配置

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
        socket.inet_aton(client_ip)
        allow_localhost_block = config.get("ebpf", {}).get("allow_localhost_block", False)
        if client_ip in ["127.0.0.1", "localhost"] and not allow_localhost_block:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(f"BLOCK {client_ip} {duration_sec}".encode('utf-8'), ("127.0.0.1", 9002))
    except Exception: pass

async def dispatch_audit_log(record_dict: dict):
    async with httpx.AsyncClient() as client:
        try: await client.post(AUDITOR_URL, json=record_dict, timeout=2.0)
        except Exception: pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    fetch_issuer_public_key()
    yield

app = FastAPI(title="PIR Abuse Control - Verifier", lifespan=lifespan)

verifier_metrics = {"total_requests": 0, "blocked_before_pir": 0, "pir_invoked": 0}

@app.get("/api/v1/verifier/metrics")
async def get_metrics():
    return verifier_metrics

async def call_pir_server(query_payload: str) -> tuple[bool, str, Optional[int], Optional[int], Optional[str]]:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(PIR_SERVER_URL, json={"query_payload": query_payload}, timeout=20.0)
            if resp.status_code == 200:
                body = resp.json()
                return True, body.get("data"), body.get("mapped_index"), body.get("recovered_val"), body.get("apir_proof")
            return False, resp.text, None, None, None
    except Exception as e: return False, str(e), None, None, None

def _run_precondition_check(req: RequestInstance, sm) -> PIRResponse | None:
    if req.ticket is None:
        return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED, reason="Missing Ticket")

    # 消融开关: 关闭 Epoch
    if not ablation_cfg.get("disable_epoch", False):
        if not is_epoch_valid(req.ticket.epoch_id, int(time.time()), EPOCH_DURATION, GRACE_WINDOW):
            return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED, reason="Ticket expired.")

    # 消融开关: 关闭并发状态锁 (重放检测前置判断)
    if not ablation_cfg.get("disable_consume_lock", False):
        current_state = sm.get_state(req.ticket.sn)
        if current_state != TicketState.UNUSED:
            return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=current_state, reason="Ticket consumed")

    return None

def _run_crypto_verification(req: RequestInstance, expected_c_q: str) -> PIRResponse | None:
    if issuer_public_key["n"] is None: fetch_issuer_public_key()
    
    # 签名本身有效性必须验证，这代表它是"真正的票据"，消融的是绑定关系
    is_valid_sig = crypto_manager.verify_ticket_signature(
        sn_hex=req.ticket.sn, epoch_id=req.ticket.epoch_id, sigma_b64=req.ticket.sigma,
        n=issuer_public_key["n"], e=issuer_public_key["e"]
    )
    if not is_valid_sig:
        return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED, reason="Invalid Sig")

    # 消融开关: 关闭 Binding
    if not ablation_cfg.get("disable_binding", False):
        if req.witness is None or req.binding_tag is None:
            return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED, reason="Missing Binding")
        try:
            sigma_bytes = base64.b64decode(req.ticket.sigma, validate=True)
            expected_sk_t = derive_sk_t(sigma_bytes, req.ticket.sn, req.ticket.epoch_id)
            witness_bytes = serialize_witness(req.witness.model_dump())
            expected_binding_tag = compute_binding_tag(expected_sk_t, expected_c_q, witness_bytes)
            if not hmac.compare_digest(req.binding_tag, expected_binding_tag):
                return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED, reason="Binding Check Failed")
        except Exception:
            return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.UNUSED, reason="Invalid Binding Material")

    return None

@app.post("/api/v1/verifier/execute", response_model=PIRResponse)
async def execute_query(req: RequestInstance, request: Request, background_tasks: BackgroundTasks):
    sm = get_state_manager()
    verifier_metrics["total_requests"] += 1
    disable_consume_lock = ablation_cfg.get("disable_consume_lock", False)

    pre_err = _run_precondition_check(req, sm)
    if pre_err:
        verifier_metrics["blocked_before_pir"] += 1
        if pre_err.ticket_state == TicketState.CONSUMED and not disable_consume_lock:
            dispatch_l4_block_signal(request.client.host if request.client else "unknown", 10)
        return pre_err

    expected_c_q = compute_query_commitment(req.query_payload)
    crypto_err = _run_crypto_verification(req, expected_c_q)
    if crypto_err:
        verifier_metrics["blocked_before_pir"] += 1
        return crypto_err

    # 消融开关: 不执行原子加锁
    if not disable_consume_lock:
        if not sm.try_lock(req.ticket.sn, lock_ttl_sec=30):
            verifier_metrics["blocked_before_pir"] += 1
            return PIRResponse(request_id=req.request_id, decision=Decision.REJECTED, ticket_state=TicketState.PENDING, reason="Concurrent collision")

    verifier_metrics["pir_invoked"] += 1
    success, payload_or_error, mapped_index, recovered_val, apir_proof = await call_pir_server(req.query_payload)

    if success:
        if mapped_index is None or recovered_val is None:
            if not disable_consume_lock: get_state_manager().mark_failed(req.ticket.sn, epoch_id=req.ticket.epoch_id)
            decision, reason, final_data = Decision.REJECTED, "Malformed PIR response", None
        else:
            if not disable_consume_lock: get_state_manager().mark_consumed(req.ticket.sn, epoch_id=req.ticket.epoch_id)
            decision, reason = Decision.SUCCESS, "PIR execution completed"
            final_data = PIRResultPayload(result_string=payload_or_error, mapped_index=mapped_index, recovered_val=recovered_val, apir_proof=apir_proof)
    else:
        if not disable_consume_lock: get_state_manager().mark_failed(req.ticket.sn, epoch_id=req.ticket.epoch_id)
        decision, reason, final_data = Decision.REJECTED, f"PIR failed: {payload_or_error}", None

    # 后置状态收口
    final_state = TicketState.UNUSED if disable_consume_lock else (TicketState.CONSUMED if success else TicketState.FAILED)

    background_tasks.add_task(dispatch_audit_log, {
        "request_id": req.request_id, "sn": req.ticket.sn, "query_commitment": expected_c_q,
        "binding_tag": req.binding_tag, "epoch_id": req.ticket.epoch_id, "decision": decision.value,
        "reason": reason, "timestamp_ms": int(time.time() * 1000), "prev_hash": "stub", "entry_mac": "stub"
    })

    return PIRResponse(request_id=req.request_id, decision=decision, ticket_state=final_state, reason=reason, data=final_data)

if __name__ == "__main__":
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)