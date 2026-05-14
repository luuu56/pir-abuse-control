# services/issuer/main.py
import sys
import time
import uuid
import hashlib
import hmac
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn
import redis

root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.logging_utils import setup_logger
from common.crypto_utils import (
    canonical_json_bytes,
    compute_hmac,
    verify_pow,
    get_current_epoch_id,
    is_epoch_valid
)
from common.models import (
    AdmissionPayload,
    AdmissionChallenge,
    AdmissionResponse,
    ChallengeRequest,
    IssueRequest,
    IssueResponse
)
from services.issuer.crypto import crypto_manager

config = load_config()
logger = setup_logger("issuer", config)

issuer_config = config.get("issuer", {})
SERVER_HOST = issuer_config.get("host", "127.0.0.1")
SERVER_PORT = issuer_config.get("port", 8001)

HMAC_SECRET = issuer_config.get("hmac_secret", "issuer-secret-key-change-me")
POW_DIFFICULTY = issuer_config.get("difficulty_bits", 16)
CHALLENGE_TTL = issuer_config.get("challenge_ttl_sec", 300)
REDIS_PREFIX = issuer_config.get("redis_prefix", "admission:challenge")

epoch_cfg = config.get("epoch", {})
EPOCH_DURATION = epoch_cfg.get("duration_sec", 3600)
GRACE_WINDOW = epoch_cfg.get("grace_window_sec", 300)

redis_cfg = config.get("redis", {})
redis_client = redis.Redis(
    host=redis_cfg.get("host", "127.0.0.1"),
    port=redis_cfg.get("port", 6379),
    db=redis_cfg.get("db", 0),
    password=redis_cfg.get("password"),
    decode_responses=True
)


class RSAPublicKeyResponse(BaseModel):
    n: str = Field(..., description="RSA Modulus (Hex string, lower case, zero-padded, no '0x')")
    e: str = Field(..., description="RSA Public Exponent (Hex string)")

app = FastAPI(title="PIR Abuse Control - Issuer Service", version="1.1")

def verify_admission_logic(proof: AdmissionResponse) -> tuple[bool, str, Optional[dict]]:
    try:
        payload_dict = proof.challenge.payload.model_dump()
        payload_bytes = canonical_json_bytes(payload_dict)

        expected_sig = compute_hmac(HMAC_SECRET, payload_bytes)
        if not hmac.compare_digest(expected_sig, proof.challenge.hmac_sig):
            return False, "Challenge signature mismatch", None

        if int(time.time()) > proof.challenge.payload.expires_at:
            return False, "Challenge expired", None

        if not verify_pow(
                payload_bytes,
                proof.challenge.hmac_sig,
                proof.nonce,
                proof.challenge.payload.difficulty
        ):
            return False, "Insufficient work (PoW verification failed)", None

        return True, "", payload_dict

    except Exception:
        logger.exception("Admission verification encountered an internal error")
        return False, "Invalid admission proof format or internal error", None

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "issuer", "redis": redis_client.ping()}

@app.get("/api/v1/issuer/public_key", response_model=RSAPublicKeyResponse)
async def get_public_key():
    return crypto_manager.get_public_key()

@app.post("/api/v1/issuer/challenge", response_model=AdmissionChallenge)
async def request_challenge(req: ChallengeRequest):
    now = int(time.time())
    current_epoch = get_current_epoch_id(EPOCH_DURATION)
    payload = AdmissionPayload(
        client_tag=req.client_tag,
        epoch_id=current_epoch,
        difficulty=POW_DIFFICULTY,
        issued_at=now,
        expires_at=now + CHALLENGE_TTL,
        server_nonce=uuid.uuid4().hex
    )

    payload_bytes = canonical_json_bytes(payload.model_dump())
    sig = compute_hmac(HMAC_SECRET, payload_bytes)

    logger.info(f"Challenge issued for tag: {req.client_tag}, difficulty: {POW_DIFFICULTY}, epoch: {current_epoch}")
    return AdmissionChallenge(payload=payload, hmac_sig=sig)

@app.post("/api/v1/issuer/verify_admission")
async def verify_admission_endpoint(proof: AdmissionResponse):
    ok, reason, _ = verify_admission_logic(proof)
    if not ok:
        raise HTTPException(status_code=403, detail=reason)
    return {"ok": True, "message": "Admission proof is valid"}

@app.post("/api/v1/issuer/issue", response_model=IssueResponse)
async def blind_sign_endpoint(req: IssueRequest):
    try:
        # [TRACE 1] 进入 /issue
        client_tag = req.admission_proof.challenge.payload.client_tag if req.admission_proof else "N/A"
        epoch_id = req.admission_proof.challenge.payload.epoch_id if req.admission_proof else "N/A"
        blinded_len = len(req.blinded_message) if req.blinded_message else 0
        logger.info(f"[TRACE] 收到 issue 请求 | tag: {client_tag} | epoch: {epoch_id} | blinded_message len: {blinded_len}")

        ablation_cfg = config.get("ablation", {})
        disable_admission = ablation_cfg.get("disable_admission", False)

        if not disable_admission:
            ticket_epoch = req.admission_proof.challenge.payload.epoch_id
            if not is_epoch_valid(ticket_epoch, int(time.time()), EPOCH_DURATION, GRACE_WINDOW):
                logger.warning(f"Refusing to sign: Epoch {ticket_epoch} is invalid.")
                raise HTTPException(status_code=403, detail="The requested epoch has expired.")

            # [TRACE 2] admission 校验前
            logger.info("[TRACE] 开始 verify_admission")
            ok, reason, payload_dict = verify_admission_logic(req.admission_proof)
            if not ok:
                logger.warning(f"Admission rejected: {reason}")
                raise HTTPException(status_code=403, detail=reason)
            # [TRACE 3] admission 校验后
            logger.info("[TRACE] verify_admission passed")

            payload_bytes = canonical_json_bytes(payload_dict)
            challenge_fingerprint = hashlib.sha256(
                payload_bytes + bytes.fromhex(req.admission_proof.challenge.hmac_sig)
            ).hexdigest()

            key = f"{REDIS_PREFIX}:{challenge_fingerprint}"
            ttl = max(1, (req.admission_proof.challenge.payload.expires_at + GRACE_WINDOW) - int(time.time()))

            if not redis_client.set(key, "USED", nx=True, ex=ttl):
                logger.warning(f"Replay detected or challenge reused: {challenge_fingerprint}")
                raise HTTPException(status_code=403, detail="Challenge already consumed or replayed")
        else:
            logger.warning("🚨 [ABLATION] Admission Control bypassed! Issuing ticket blindly.")

        # 处理 hex 参数
        hex_str = req.blinded_message.strip().lower()
        if hex_str.startswith("0x"):
            hex_str = hex_str[2:]
        blinded_msg_int = int(hex_str, 16)

        # [TRACE 4] blind sign 前
        logger.info("[TRACE] starting blind sign")
        blind_sig_int = crypto_manager.blind_sign(blinded_msg_int)
        blind_sig_hex = f"{blind_sig_int:0{crypto_manager.pad_len_hex}x}"
        
        # [TRACE 5] blind sign 后
        logger.info("[TRACE] blind sign success")
        return IssueResponse(blinded_signature=blind_sig_hex)

    # HTTPException 直接抛出，不当做未知异常
    except HTTPException:
        raise
    except ValueError:
        logger.exception("[TRACE] 参数转换报错")
        raise HTTPException(status_code=400, detail="Blinded message must be a valid hex string")
    except Exception as e:
        # [TRACE 6] 异常兜底，全栈追踪！
        logger.exception(f"[TRACE] /issue 触发致命崩溃，抛出未捕获异常: {e}")
        raise HTTPException(status_code=500, detail="Internal processing error")

if __name__ == "__main__":
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)