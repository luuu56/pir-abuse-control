# services/client/main.py
import sys
import base64
import requests
import logging
import time
import uuid
from pathlib import Path
from common.models import RequestContext, RequestInstance
from common.crypto_utils import (
    derive_sk_t, compute_query_commitment,
    serialize_witness, compute_binding_tag,
    integer_to_base64  # <--- 新增导入
)

# 将根目录加入 sys.path
root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.logging_utils import setup_logger
from common.models import Ticket
from services.client.crypto import crypto_manager

config = load_config()
logger = setup_logger("client", config)

# --- 常量抽取 ---
issuer_cfg = config.get("issuer", {})
ISSUER_URL = f"http://{issuer_cfg.get('host', '127.0.0.1')}:{issuer_cfg.get('port', 8001)}/api/v1/issuer"

client_cfg = config.get("client", {})
CLIENT_ID = client_cfg.get("client_id", "client_test_01")
REQUEST_TIMEOUT_SEC = client_cfg.get("timeout", 5)


def acquire_ticket() -> Ticket:
    logger.info("=== Starting Ticket Acquisition Flow ===")

    # 1. 申请 Challenge 与 公钥
    logger.info(f"1. Requesting challenge and public key for client: {CLIENT_ID}...")
    resp = requests.post(f"{ISSUER_URL}/challenge", json={"client_id": CLIENT_ID}, timeout=REQUEST_TIMEOUT_SEC)
    resp.raise_for_status()
    challenge_data = resp.json()

    if "epoch_id" not in challenge_data or "public_key" not in challenge_data:
        raise RuntimeError("Issuer challenge response missing 'epoch_id' or 'public_key'")
    if "n" not in challenge_data["public_key"] or "e" not in challenge_data["public_key"]:
        raise RuntimeError("Issuer public key missing 'n' or 'e'")

    epoch_id = challenge_data["epoch_id"]
    n_hex_raw = challenge_data["public_key"]["n"].lower()
    n_hex = n_hex_raw[2:] if n_hex_raw.startswith("0x") else n_hex_raw

    # 增加偶数长度保护（保险丝），确保后续 bytes.fromhex 不报错
    pad_len = len(n_hex)
    if pad_len % 2 != 0:
        pad_len += 1

    n = int(n_hex, 16)

    e_hex_raw = challenge_data["public_key"]["e"].lower()
    e_hex = e_hex_raw[2:] if e_hex_raw.startswith("0x") else e_hex_raw
    e = int(e_hex, 16)

    # 2. 生成 SN 并盲化
    logger.info("2. Blinding message...")
    sn_hex = crypto_manager.generate_sn()
    m_int = crypto_manager.encode_message(sn_hex, epoch_id)

    r = crypto_manager.generate_blinding_factor(n)
    blinded_m_int = crypto_manager.blind_message(m_int, r, e, n)
    blinded_m_hex = f"{blinded_m_int:0{pad_len}x}"

    # 3. 提交盲签请求
    logger.info("3. Submitting to Issuer...")
    issue_resp = requests.post(
        f"{ISSUER_URL}/issue",
        json={"blinded_message": blinded_m_hex, "admission_proof": "dummy_proof"},
        timeout=REQUEST_TIMEOUT_SEC
    )
    issue_resp.raise_for_status()
    issue_data = issue_resp.json()

    if "blinded_signature" not in issue_data:
        raise RuntimeError("Issuer issue response missing 'blinded_signature'")

    # 签名 Hex 规范化处理
    blinded_sig_hex_raw = issue_data["blinded_signature"].lower()
    blinded_sig_hex = blinded_sig_hex_raw[2:] if blinded_sig_hex_raw.startswith("0x") else blinded_sig_hex_raw

    # 4. 去盲与本地验签
    logger.info("4. Unblinding...")
    blinded_sig_int = int(blinded_sig_hex, 16)
    unblinded_sig_int = crypto_manager.unblind_signature(blinded_sig_int, r, n)

    if pow(unblinded_sig_int, e, n) != m_int:
        logger.critical("LOCAL VERIFICATION FAILED: Unblinded signature is invalid!")
        raise RuntimeError("Cryptographic integrity check failed during unblinding")
    logger.info("Local verification passed: Signature is valid.")

    modulus_bytes_len = (n.bit_length() + 7) // 8
    sigma_b64 = integer_to_base64(unblinded_sig_int, modulus_bytes_len)

    # 5. 组装 Ticket
    ticket = Ticket(sn=sn_hex, sigma=sigma_b64, epoch_id=epoch_id)
    logger.info("=== Ticket Successfully Acquired! ===")
    return ticket


def create_bound_request(ticket: Ticket, query_payload: str) -> RequestInstance:
    """
    Day 11: 将票据与载荷进行密码学绑定
    """
    logger.info("=== Starting Ticket Binding Process ===")

    # 1. 还原 sigma 字节串
    sigma_bytes = base64.b64decode(ticket.sigma)

    # 2. 派生 sk_t
    sk_t = derive_sk_t(sigma_bytes, ticket.sn, ticket.epoch_id)

    # 3. 计算载荷承诺 c_q
    c_q_hex = compute_query_commitment(query_payload)

    # 4. 构建并序列化 witness
    witness = RequestContext(
        timestamp_ms=int(time.time() * 1000),
        nonce=str(uuid.uuid4()),
        client_state_digest="client_day11_state"
    )
    witness_bytes = serialize_witness(witness.model_dump())

    # 5. 计算 HMAC 绑定标签 b
    binding_tag = compute_binding_tag(sk_t, c_q_hex, witness_bytes)

    # 6. 组装 RequestInstance
    req = RequestInstance(
        request_id=str(uuid.uuid4()),
        query_payload=query_payload,
        ticket=ticket,
        binding_tag=binding_tag,
        witness=witness
    )
    logger.info(f"Binding successful. Binding Tag: {binding_tag[:16]}...")
    return req

if __name__ == "__main__":
    try:
        t = acquire_ticket()
        req = create_bound_request(t, "day11_real_pir_query")
        print("\n--- Final Bound RequestInstance ---")
        print(req.model_dump_json(indent=2))
    except Exception as err:
        logger.error(f"Flow failed: {err}")