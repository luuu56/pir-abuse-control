import hashlib
import hmac
import json
import base64
from typing import Dict, Any, Optional


def encode_ticket_message(sn_hex: str, epoch_id: int) -> int:
    """【统一编码契约】m = SN(32 bytes) || EpochID(4 bytes, big-endian)"""
    try:
        sn_bytes = bytes.fromhex(sn_hex)
    except ValueError:
        raise ValueError("SN must be a valid hex string")

    if len(sn_bytes) != 32:
        raise ValueError(f"Invalid SN length: expected 32 bytes, got {len(sn_bytes)}")

    if not (0 <= epoch_id <= 0xffffffff):
        raise ValueError(f"EpochID {epoch_id} out of 32-bit range")

    epoch_bytes = epoch_id.to_bytes(4, byteorder="big")
    return int.from_bytes(sn_bytes + epoch_bytes, byteorder="big")


def integer_to_base64(val: int, modulus_bytes_len: int) -> str:
    """将大整数（如盲签名）转换为严格定长字节串的 Base64"""
    b = val.to_bytes(modulus_bytes_len, byteorder='big')
    return base64.b64encode(b).decode('utf-8')


def base64_to_integer(b64_str: str, expected_bytes_len: int) -> int:
    """从 Base64 还原大整数，并强制校验字节长度是否等于预期模长"""
    try:
        b = base64.b64decode(b64_str, validate=True)
    except Exception as e:
        raise ValueError(f"Invalid Base64 format: {e}")

    if len(b) != expected_bytes_len:
        raise ValueError(f"Decoded signature length {len(b)} bytes does not match expected {expected_bytes_len} bytes")

    return int.from_bytes(b, byteorder='big')


def derive_sk_t(sigma_bytes: bytes, sn_hex: str, epoch_id: int, expected_sigma_len: Optional[int] = None) -> bytes:
    """
    派生票据密钥 sk_t = SHA256(sigma || sn || epoch_id)
    【工程约束】:
    - sigma_bytes 必须是严格左补零对齐模长的定长字节串。
    - 严禁在此处执行任何 strip() 操作。
    """
    if expected_sigma_len is not None and len(sigma_bytes) != expected_sigma_len:
        raise ValueError(f"sigma_bytes length must be exactly {expected_sigma_len} bytes, got {len(sigma_bytes)}")

    sn_bytes = bytes.fromhex(sn_hex)
    epoch_bytes = epoch_id.to_bytes(4, byteorder='big')

    h = hashlib.sha256()
    h.update(sigma_bytes)
    h.update(sn_bytes)
    h.update(epoch_bytes)
    return h.digest()


def compute_query_commitment(query_payload: str) -> str:
    """计算载荷承诺 c_q = SHA256(q)"""
    return hashlib.sha256(query_payload.encode('utf-8')).hexdigest()


def serialize_witness(witness_dict: Dict[str, Any]) -> bytes:
    """
    【规范化序列化】将 witness 转换为规范字节串参与 HMAC。
    拒绝包含无法 JSON 序列化的自定义对象或 bytes。
    """
    try:
        return json.dumps(
            witness_dict,
            sort_keys=True,
            separators=(",", ":")
        ).encode("utf-8")
    except TypeError as e:
        raise ValueError(f"Witness contains non-JSON-serializable fields: {e}")


def compute_binding_tag(sk_t: bytes, c_q_hex: str, witness_bytes: bytes) -> str:
    """计算绑定标签 b = HMAC_SHA256(sk_t, c_q || w)"""
    if len(c_q_hex) != 64:
        raise ValueError(f"c_q_hex must be a 64-char SHA256 hex string, got length {len(c_q_hex)}")
    try:
        int(c_q_hex, 16)
    except ValueError:
        raise ValueError("c_q_hex must be valid hex")

    msg = c_q_hex.encode("utf-8") + witness_bytes
    mac = hmac.new(sk_t, msg, hashlib.sha256)
    return mac.hexdigest()