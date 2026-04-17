# services/client/crypto.py
import secrets
import logging
from Crypto.Util.number import inverse, GCD
from common.crypto_utils import encode_ticket_message

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
        【代理到统一编码契约】
        消除冗余实现，直接复用 common.crypto_utils 的单一事实来源。
        """
        return encode_ticket_message(sn_hex, epoch_id)

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