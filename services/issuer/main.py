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
import redis  # 确保环境已安装 redis 库

# 将根目录加入 sys.path
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

# --- 1. 初始化配置与日志 ---
config = load_config()
logger = setup_logger("issuer", config)

# 读取配置
issuer_config = config.get("issuer", {})
SERVER_HOST = issuer_config.get("host", "127.0.0.1")
SERVER_PORT = issuer_config.get("port", 8001)

# Admission 相关配置
HMAC_SECRET = issuer_config.get("hmac_secret", "issuer-secret-key-change-me")
POW_DIFFICULTY = issuer_config.get("difficulty_bits", 16)
CHALLENGE_TTL = issuer_config.get("challenge_ttl_sec", 300)
REDIS_PREFIX = issuer_config.get("redis_prefix", "admission:challenge")

# 提取 Epoch 统一配置块
epoch_cfg = config.get("epoch", {})
EPOCH_DURATION = epoch_cfg.get("duration_sec", 3600)
GRACE_WINDOW = epoch_cfg.get("grace_window_sec", 300)

# Redis 初始化 (用于 Challenge 烧毁/防重放)
redis_cfg = config.get("redis", {})
redis_client = redis.Redis(
    host=redis_cfg.get("host", "127.0.0.1"),
    port=redis_cfg.get("port", 6379),
    db=redis_cfg.get("db", 0),
    decode_responses=True
)

# --- 2. 初始化 FastAPI ---
class RSAPublicKeyResponse(BaseModel):
    n: str = Field(..., description="RSA Modulus (Hex string, lower case, zero-padded, no '0x')")
    e: str = Field(..., description="RSA Public Exponent (Hex string)")

app = FastAPI(title="PIR Abuse Control - Issuer Service", version="1.1")


# --- 3. 核心业务逻辑 (Reusable Verification Logic) ---

def verify_admission_logic(proof: AdmissionResponse) -> tuple[bool, str, Optional[dict]]:
    """
    核心准入校验逻辑。
    返回: (是否通过, 错误原因, 载荷字典)
    """
    try:
        payload_dict = proof.challenge.payload.model_dump()
        payload_bytes = canonical_json_bytes(payload_dict)

        # 1. 常量时间比较 HMAC (防时序攻击)
        expected_sig = compute_hmac(HMAC_SECRET, payload_bytes)
        if not hmac.compare_digest(expected_sig, proof.challenge.hmac_sig):
            return False, "Challenge signature mismatch", None

        # 2. 过期校验
        if int(time.time()) > proof.challenge.payload.expires_at:
            return False, "Challenge expired", None

        # 3. Epoch ID 最小存根校验 (替换掉原来的写死1的校验，转由 is_epoch_valid 统一负责)
        # 此处我们允许 /issue 里使用最新统一逻辑验证，详见 issue_ticket

        # 4. PoW 校验
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


# --- 4. API 路由 ---

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "issuer", "redis": redis_client.ping()}

@app.get("/api/v1/issuer/public_key", response_model=RSAPublicKeyResponse)
async def get_public_key():
    """获取 Issuer 动态生成的 RSA 公钥 (Client/Verifier 统一从这里拉取)"""
    return crypto_manager.get_public_key()


@app.post("/api/v1/issuer/challenge", response_model=AdmissionChallenge)
async def request_challenge(req: ChallengeRequest):
    """
    阶段一：下发 HMAC 认证的挑战载荷。
    client_tag 由客户端自报，用于短时上下文标识。
    """
    now = int(time.time())
    current_epoch = get_current_epoch_id(EPOCH_DURATION)
    payload = AdmissionPayload(
        client_tag=req.client_tag,
        epoch_id=current_epoch,  # 动态纪元
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
    """
    Day 16 验收接口：仅验证证明有效性，不执行 Redis 烧毁。
    用于测试和调试。
    """
    ok, reason, _ = verify_admission_logic(proof)
    if not ok:
        raise HTTPException(status_code=403, detail=reason)
    return {"ok": True, "message": "Admission proof is valid"}


@app.post("/api/v1/issuer/issue", response_model=IssueResponse)
async def blind_sign_endpoint(req: IssueRequest):
    """
    阶段二：三重校验 (HMAC/Expiry/PoW) + Epoch 时效校验 + Redis 烧毁 + RSA 盲签。
    """
    # 0. Epoch 有效性前置检查 (Day 18 补齐，使用对齐后的配置)
    ticket_epoch = req.admission_proof.challenge.payload.epoch_id
    if not is_epoch_valid(ticket_epoch, int(time.time()), EPOCH_DURATION, GRACE_WINDOW):
        logger.warning(f"Refusing to sign: Epoch {ticket_epoch} is invalid (outside duration + grace).")
        raise HTTPException(
            status_code=403,
            detail="The requested epoch has expired. Please re-apply for a fresh challenge."
        )

    # 1. 逻辑校验
    ok, reason, payload_dict = verify_admission_logic(req.admission_proof)
    if not ok:
        logger.warning(f"Admission rejected: {reason}")
        raise HTTPException(status_code=403, detail=reason)

    # 2. Redis 烧毁语义 (Anti-Replay)
    payload_bytes = canonical_json_bytes(payload_dict)
    challenge_fingerprint = hashlib.sha256(
        payload_bytes + bytes.fromhex(req.admission_proof.challenge.hmac_sig)
    ).hexdigest()

    key = f"{REDIS_PREFIX}:{challenge_fingerprint}"
    ttl = max(1, (req.admission_proof.challenge.payload.expires_at + GRACE_WINDOW) - int(time.time()))

    # 原子占位，若已存在则说明是重放或已使用
    if not redis_client.set(key, "USED", nx=True, ex=ttl):
        logger.warning(f"Replay detected or challenge reused: {challenge_fingerprint}")
        raise HTTPException(status_code=403, detail="Challenge already consumed or replayed")

    # 3. 规范化解析盲化消息
    try:
        hex_str = req.blinded_message.strip().lower()
        if hex_str.startswith("0x"):
            hex_str = hex_str[2:]
        blinded_msg_int = int(hex_str, 16)
    except ValueError:
        raise HTTPException(status_code=400, detail="Blinded message must be a valid hex string")

    # 4. 执行 RSA 盲签
    try:
        blind_sig_int = crypto_manager.blind_sign(blinded_msg_int)
        blind_sig_hex = f"{blind_sig_int:0{crypto_manager.pad_len_hex}x}"

        logger.info(f"Ticket issued for tag: {req.admission_proof.challenge.payload.client_tag}, epoch: {ticket_epoch}")
        return IssueResponse(blinded_signature=blind_sig_hex)

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Internal signing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal processing error")


if __name__ == "__main__":
    logger.info(f"Starting Issuer (Day 18) on {SERVER_HOST}:{SERVER_PORT}...")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)