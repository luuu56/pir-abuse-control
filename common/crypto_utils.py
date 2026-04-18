# common/crypto_utils.py
import hashlib
import hmac
import json
import base64
import time
import re
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
    if not isinstance(query_payload, str) or not query_payload:
        raise ValueError("query_payload must be a non-empty string")
    return hashlib.sha256(query_payload.encode("utf-8")).hexdigest()

def compute_binding_tag(sk_t: bytes, c_q_hex: str, witness_bytes: bytes) -> str:
    """计算绑定标签 b = HMAC_SHA256(sk_t, c_q || w)"""
    if not isinstance(sk_t, bytes) or len(sk_t) == 0:
        raise ValueError("sk_t must be non-empty bytes")

    if not isinstance(c_q_hex, str) or not re.fullmatch(r"[0-9a-f]{64}", c_q_hex):
        raise ValueError("c_q_hex must be a 64-char lowercase hex SHA256 digest")

    if not isinstance(witness_bytes, bytes) or len(witness_bytes) == 0:
        raise ValueError("witness_bytes must be non-empty bytes")

    msg = c_q_hex.encode("utf-8") + witness_bytes
    mac = hmac.new(sk_t, msg, hashlib.sha256)
    return mac.hexdigest()


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


# --- Day 16: 准入原语相关的密码学实现 ---

def canonical_json_bytes(obj: dict) -> bytes:
    """【硬性契约】规范化 JSON 序列化，确保跨服务 HMAC 一致性"""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False
    ).encode("utf-8")


def compute_hmac(key: str, data: bytes) -> str:
    """计算 HMAC-SHA256 并返回 Hex 字符串"""
    return hmac.new(key.encode("utf-8"), data, hashlib.sha256).hexdigest()


def verify_pow(payload_bytes: bytes, hmac_sig_hex: str, nonce: int, difficulty_bits: int) -> bool:
    """验证工作量证明，包含严格边界检查"""
    if not (1 <= difficulty_bits <= 256):
        raise ValueError(f"Invalid difficulty bits: {difficulty_bits}")
    if not (0 <= nonce < 2 ** 64):
        raise ValueError("Nonce out of uint64 range")

    h = hashlib.sha256()
    h.update(payload_bytes)
    h.update(bytes.fromhex(hmac_sig_hex))
    h.update(nonce.to_bytes(8, byteorder="big"))

    hash_int = int.from_bytes(h.digest(), byteorder="big")
    return (hash_int >> (256 - difficulty_bits)) == 0


def solve_pow(payload_bytes: bytes, hmac_sig_hex: str, difficulty_bits: int) -> int:
    """求解器，包含对称的边界检查与安全熔断"""
    if not (1 <= difficulty_bits <= 256):
        raise ValueError(f"Invalid difficulty bits: {difficulty_bits}")

    prefix = payload_bytes + bytes.fromhex(hmac_sig_hex)
    target_shift = 256 - difficulty_bits

    # 防止死循环溢出，限制在 uint64 空间内穷举
    for nonce in range(2 ** 64):
        h = hashlib.sha256()
        h.update(prefix)
        h.update(nonce.to_bytes(8, byteorder="big"))
        if (int.from_bytes(h.digest(), byteorder="big") >> target_shift) == 0:
            return nonce

    raise RuntimeError("Failed to solve PoW within uint64 space")


# --- Day 18: Epoch 时间窗实现 ---

def get_current_epoch_id(epoch_duration: int) -> int:
    """根据当前时间戳和设定的持续时间计算 Epoch ID"""
    return int(time.time() // epoch_duration)


def is_epoch_valid(ticket_epoch: int, now_ts: int, duration: int, grace: int) -> bool:
    """
    【统一时间契约】判定给定的 Epoch ID 是否仍处于有效期内。
    规则：
    1. 等于当前 Epoch：永远有效。
    2. 等于上一个 Epoch：仅在宽限期（Grace Window）内有效。
    3. 其他情况：无效。
    """
    if duration <= 0:
        raise ValueError("epoch duration must be > 0")
    if grace < 0:
        raise ValueError("epoch grace must be >= 0")

    current_epoch = int(now_ts // duration)

    # 情况 1：当前纪元
    if ticket_epoch == current_epoch:
        return True

    # 情况 2：上一个纪元，检查是否处于宽限期
    if ticket_epoch == current_epoch - 1:
        # 当前纪元刚开始多久
        seconds_into_current = now_ts % duration
        return seconds_into_current < grace

    return False