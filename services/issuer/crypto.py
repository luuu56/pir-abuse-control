# services/issuer/crypto.py
from Crypto.PublicKey import RSA
import logging

logger = logging.getLogger("issuer.crypto")


class IssuerCryptoManager:
    def __init__(self, bits: int = 2048):
        """
        初始化时生成 RSA 密钥对。

        【工程约束声明】：
        当前仅用于联调，不保证服务重启后历史票据可验证。
        每次重启都会重新生成密钥，导致旧公钥签发的票据在 Verifier 侧全部失效。
        """
        # 【修改 2】对输入参数 bits 进行轻量化边界检查
        if bits < 1024:
            raise ValueError("RSA key size is too small for this prototype (min 1024)")
        if bits % 8 != 0:
            raise ValueError("RSA key size must be a multiple of 8")

        logger.info(f"Generating {bits}-bit RSA key pair for Issuer (This may take a few seconds)...")
        self.key = RSA.generate(bits)
        self.n = self.key.n
        self.e = self.key.e
        self.d = self.key.d

        # 【修改 1】严格从实际生成的 n 推导模长（字节数和 Hex 字符数）
        # 这种写法保证了后续定长序列化对齐的是真实的模数长度
        self.modulus_bytes_len = (self.n.bit_length() + 7) // 8
        self.pad_len_hex = self.modulus_bytes_len * 2

        logger.info(f"RSA key pair generated. Actual modulus length: {self.modulus_bytes_len} bytes.")

    def get_public_key(self) -> dict:
        """
        供客户端/Verifier 下载公钥 (n, e)。

        【格式约定】：
        - n: 无 '0x' 前缀、严格左补零对齐到模长的纯小写 hex 字符串 (定长)。
        - e: 无 '0x' 前缀的普通小写 hex 字符串 (不定长)。
        """
        return {
            "n": f"{self.n:0{self.pad_len_hex}x}",
            "e": f"{self.e:x}"
        }

    def blind_sign(self, blinded_message: int) -> int:
        """
        核心盲签逻辑：s' = (m')^d mod n

        【责任边界说明】：
        1. gcd(blinded_message, n) == 1 的约束由客户端保证。
        2. 盲签名不涉及补码逻辑 (Textbook RSA)。
        """
        if not isinstance(blinded_message, int):
            raise TypeError(f"Blinded message must be an integer, got {type(blinded_message)}")

        if blinded_message <= 0 or blinded_message >= self.n:
            raise ValueError("Blinded message is out of bounds (must be 0 < m' < n).")

        # 使用 Python 内置的高效模幂运算
        return pow(blinded_message, self.d, self.n)


# 实例化全局单例
crypto_manager = IssuerCryptoManager()