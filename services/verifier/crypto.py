# services/verifier/crypto.py
import logging
from common.crypto_utils import encode_ticket_message, base64_to_integer

logger = logging.getLogger("verifier.crypto")


class VerifierCryptoManager:
    @staticmethod
    def verify_ticket_signature(sn_hex: str, epoch_id: int, sigma_b64: str, n: int, e: int) -> bool:
        """
        验证票据的 RSA 盲签名。
        """
        try:
            # 动态计算当前 RSA 公钥模数的字节长度
            expected_modulus_bytes = (n.bit_length() + 7) // 8

            # 1. 使用统一工具函数重构被签消息 m_int
            m_int = encode_ticket_message(sn_hex, epoch_id)

            # 2. 严格契约解码 Base64 签名 (内置定长校验与 Base64 字符验证)
            s_int = base64_to_integer(sigma_b64, expected_modulus_bytes)

            # 3. 边界检查：s 必须在 [1, n) 之间
            if s_int <= 0 or s_int >= n:
                logger.warning("Signature s_int out of bounds.")
                return False

            # 4. 核心验签公式: s^e mod n == m
            return pow(s_int, e, n) == m_int

        except ValueError as ve:
            # 捕获如长度不对、非法 Base64、SN 长度不对等格式错误
            logger.error(f"Validation error during signature verification: {ve}")
            return False
        except Exception as err:
            logger.error(f"Unexpected error during signature verification: {err}")
            return False


crypto_manager = VerifierCryptoManager()