# common/crypto_utils.py
import hashlib
import hmac
import json
from typing import Dict, Any


def encode_ticket_message(sn_hex: str, epoch_id: int) -> int:
    """【统一编码契约】将 SN 与 EpochID 拼接"""
    if len(sn_hex) != 64:
        raise ValueError(f"Invalid SN length: expected 64, got {len(sn_hex)}")
    try:
        int(sn_hex, 16)
    except ValueError:
        raise ValueError("SN must be a valid hex string")
    if not (0 <= epoch_id <= 0xffffffff):
        raise ValueError(f"EpochID {epoch_id} out of 32-bit range")

    epoch_hex = f"{epoch_id:08x}"
    encoded_hex = sn_hex + epoch_hex
    return int(encoded_hex, 16)


def derive_sk_t(sigma_bytes: bytes, sn_hex: str, epoch_id: int) -> bytes:
    """
    派生票据密钥 sk_t = SHA256(sigma || sn || epoch_id)
    【工程约束】:
    - sigma_bytes 必须是严格左补零对齐模长的定长字节串 (Day 9 约定)。
    - 严禁在此处执行任何 strip() 操作。
    """
    sn_bytes = bytes.fromhex(sn_hex)
    epoch_bytes = epoch_id.to_bytes(4, byteorder='big')

    h = hashlib.sha256()
    h.update(sigma_bytes)
    h.update(sn_bytes)
    h.update(epoch_bytes)
    return h.digest()


def compute_query_commitment(query_payload: str) -> str:
    """
    计算载荷承诺 c_q = SHA256(q)
    """
    return hashlib.sha256(query_payload.encode('utf-8')).hexdigest()


def serialize_witness(witness_dict: Dict[str, Any]) -> bytes:
    """
    【规范化序列化】将 witness 转换为规范字节串参与 HMAC。
    使用紧凑格式、排序 Key 以保证跨语言/跨端一致性。
    """
    return json.dumps(witness_dict, sort_keys=True, separators=(',', ':')).encode('utf-8')


def compute_binding_tag(sk_t: bytes, c_q_hex: str, witness_bytes: bytes) -> str:
    """
    计算绑定标签 b = HMAC_SHA256(sk_t, c_q || w)
    """
    msg = c_q_hex.encode('utf-8') + witness_bytes
    mac = hmac.new(sk_t, msg, hashlib.sha256)
    return mac.hexdigest()