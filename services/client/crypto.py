# services/client/crypto.py
import secrets
import logging
from Crypto.Util.number import inverse, GCD

logger = logging.getLogger("client.crypto")


class ClientCryptoManager:
    @staticmethod
    def generate_sn() -> str:
        """生成 256-bit 的随机序列号 (SN)，返回 64 字符纯 Hex 字符串"""
        sn_bytes = secrets.token_bytes(32)
        return sn_bytes.hex()

    @staticmethod
    def encode_message(sn_hex: str, epoch_id: int) -> int:
        """
        【严格编码契约 (Day 9 第一版)】
        将 SN 与 EpochID 拼接：SN(32 bytes) || EpochID(4 bytes big-endian)
        注意：Verifier 侧在验签时，必须按同一规则重构 m_int！
        """
        if len(sn_hex) != 64:
            raise ValueError(f"SN hex must be 64 characters, got {len(sn_hex)}")
        if not all(c in '0123456789abcdefABCDEF' for c in sn_hex):
            raise ValueError("SN must be a valid hex string")
        if not (0 <= epoch_id <= 0xffffffff):
            raise ValueError(f"EpochID {epoch_id} out of 32-bit range")

        epoch_hex = f"{epoch_id:08x}"
        encoded_hex = sn_hex + epoch_hex
        return int(encoded_hex, 16)

    @staticmethod
    def generate_blinding_factor(n: int) -> int:
        """生成与 n 互质的随机盲因子 r"""
        if n <= 3:
            raise ValueError("Modulus n must be strictly greater than 3")

        while True:
            r = secrets.randbelow(n)
            if r > 1 and GCD(r, n) == 1:
                return r

    @staticmethod
    def blind_message(m_int: int, r: int, e: int, n: int) -> int:
        """盲化: m' = m * (r^e) mod n"""
        if m_int >= n:
            raise ValueError("Encoded message must be smaller than RSA modulus n")

        r_pow_e = pow(r, e, n)
        return (m_int * r_pow_e) % n

    @staticmethod
    def unblind_signature(blinded_sig_int: int, r: int, n: int) -> int:
        """去盲: s = s' * (r^-1) mod n"""
        r_inv = inverse(r, n)
        return (blinded_sig_int * r_inv) % n


crypto_manager = ClientCryptoManager()