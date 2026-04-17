# services/verifier/main.py
import sys
import requests
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
import uvicorn

root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.logging_utils import setup_logger
from common.models import RequestInstance, PIRResponse, Decision
from services.verifier.crypto import crypto_manager

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


# 使用 FastAPI 推荐的 lifespan 替代废弃的 on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    fetch_issuer_public_key()
    yield


app = FastAPI(title="PIR Abuse Control - Verifier Service", version="1.0", lifespan=lifespan)


@app.post("/api/v1/verifier/execute", response_model=PIRResponse)
def execute_query(req: RequestInstance):
    logger.info(f"Received request {req.request_id} for SN: {req.ticket.sn[:16]}...")

    if issuer_public_key["n"] is None:
        fetch_issuer_public_key()
        if issuer_public_key["n"] is None:
            raise HTTPException(status_code=503, detail="Issuer PK not available")

    # 1. 验证票据签名 (之前这块不小心被注释覆盖了！)
    is_valid_sig = crypto_manager.verify_ticket_signature(
        sn_hex=req.ticket.sn,
        epoch_id=req.ticket.epoch_id,
        sigma_b64=req.ticket.sigma,
        n=issuer_public_key["n"],
        e=issuer_public_key["e"]
    )

    # 验签失败拦截
    if not is_valid_sig:
        logger.warning(f"Request {req.request_id} REJECTED: Invalid RSA Signature")
        return PIRResponse(
            request_id=req.request_id,
            decision=Decision.REJECTED,
            reason="Invalid Ticket Signature"
        )

    # 验签通过的显式日志
    logger.info(f"Request {req.request_id} passed RSA signature verification.")

    return PIRResponse(
        request_id=req.request_id,
        decision=Decision.SUCCESS,
        reason="[Day 10 Stub] Sig-Check passed; bypass Binding/PIR",
        data="dummy_pir_result_for_testing"
    )


if __name__ == "__main__":
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)