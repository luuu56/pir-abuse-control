# services/verifier/crypto.py
import base64
import logging
from common.crypto_utils import encode_ticket_message

logger = logging.getLogger("verifier.crypto")


class VerifierCryptoManager:
    @staticmethod
    def verify_ticket_signature(sn_hex: str, epoch_id: int, sigma_b64: str, n: int, e: int) -> bool:
        """
        验证票据的 RSA 盲签名。
        """
        try:
            # 1. 使用统一工具函数重构被签消息 m_int
            m_int = encode_ticket_message(sn_hex, epoch_id)

            # 2. 严格解码 Base64 签名
            # validate=True 会拒绝非法的 base64 字符输入
            sig_bytes = base64.b64decode(sigma_b64, validate=True)
            s_int = int.from_bytes(sig_bytes, byteorder='big')

            # 3. 边界检查：s 必须在 [1, n) 之间
            if s_int <= 0 or s_int >= n:
                logger.warning("Signature s_int out of bounds.")
                return False

            # 4. 核心验签公式: s^e mod n == m
            return pow(s_int, e, n) == m_int

        except ValueError as ve:
            logger.error(f"Validation error during signature verification: {ve}")
            return False
        except Exception as err:
            logger.error(f"Unexpected error during signature verification: {err}")
            return False


crypto_manager = VerifierCryptoManager()