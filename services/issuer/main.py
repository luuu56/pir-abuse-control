# services/issuer/main.py
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

# 将根目录加入 sys.path
root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.logging_utils import setup_logger
from services.issuer.crypto import crypto_manager

# --- 1. 初始化配置与日志 ---
config = load_config()
logger = setup_logger("issuer", config)

# 读取配置中的端口，默认 8001
issuer_config = config.get("issuer", {})
SERVER_HOST = issuer_config.get("host", "127.0.0.1")
SERVER_PORT = issuer_config.get("port", 8001)

# --- 2. 初始化 FastAPI ---
app = FastAPI(title="PIR Abuse Control - Issuer Service", version="1.0")


# --- 3. 严格 Pydantic 接口模型 ---
class RSAPublicKeyResponse(BaseModel):
    n: str = Field(..., description="RSA Modulus (Hex string, lower case, zero-padded, no '0x')")
    e: str = Field(..., description="RSA Public Exponent (Hex string)")


class ChallengeRequest(BaseModel):
    client_id: str = Field(default="anonymous")


class ChallengeResponse(BaseModel):
    challenge: str
    epoch_id: int
    public_key: RSAPublicKeyResponse  # 替换了之前松散的 dict


class IssueRequest(BaseModel):
    blinded_message: str = Field(..., description="Blinded message (Hex string)")
    admission_proof: str = Field(..., description="Mock proof for Day 8. Must not be empty.")  # 改为必填项


class IssueResponse(BaseModel):
    blinded_signature: str = Field(..., description="Blind signature s' (Hex string, zero-padded, no '0x')")


# --- 4. API 路由 ---
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "issuer"}


@app.post("/api/v1/issuer/challenge", response_model=ChallengeResponse)
def request_challenge(req: ChallengeRequest):
    """阶段一：客户端申请准入挑战及公钥"""
    logger.info(f"Received challenge request from client: {req.client_id}")

    # TODO(day15/day16): 替换为真实的 Epoch 窗口轮转逻辑
    # TODO(day15/day16): 替换为真实的 Admission 挑战生成逻辑
    return ChallengeResponse(
        challenge="dummy_challenge_for_day8",
        epoch_id=1,
        public_key=crypto_manager.get_public_key()
    )


@app.post("/api/v1/issuer/issue", response_model=IssueResponse)
def blind_sign_endpoint(req: IssueRequest):
    """阶段二：验证准入证明，并执行盲签"""
    logger.info("Received issue request. Verifying admission proof...")

    # 1. 验证准入证明 (TODO: 替换为真实的 PoW/VDF 验证逻辑)
    if req.admission_proof != "dummy_proof":
        logger.warning("Admission proof rejected.")
        raise HTTPException(status_code=403, detail="Invalid admission proof")

    # 2. 规范化解析盲化消息
    try:
        hex_str = req.blinded_message.strip().lower()
        if hex_str.startswith("0x"):
            hex_str = hex_str[2:]
        blinded_msg_int = int(hex_str, 16)
    except ValueError:
        logger.error("Failed to parse blinded message as hex.")
        raise HTTPException(status_code=400, detail="Blinded message must be a valid hex string")

    # 3. 核心密码学操作：盲签
    try:
        blind_sig_int = crypto_manager.blind_sign(blinded_msg_int)

        # 统一规范化返回：小写 Hex，无 0x，左补零对其模长 (512字符)
        blind_sig_hex = f"{blind_sig_int:0{crypto_manager.pad_len}x}"

        logger.info("Successfully generated blind signature.")
        return IssueResponse(blinded_signature=blind_sig_hex)

    except ValueError as ve:
        logger.error(f"Validation error during signing: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error during blind signing: {e}")
        raise HTTPException(status_code=500, detail="Internal signing error")


# --- 5. 启动入口 ---
if __name__ == "__main__":
    logger.info(f"Starting Issuer service on {SERVER_HOST}:{SERVER_PORT}...")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)