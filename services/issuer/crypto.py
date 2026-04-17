# services/issuer/crypto.py
from Crypto.PublicKey import RSA
import logging

logger = logging.getLogger("issuer.crypto")


class IssuerCryptoManager:
    def __init__(self, bits: int = 2048):
        """
        初始化时生成 RSA 密钥对。

        【工程约束声明】：
        当前仅用于 Day 8 / Day 9 联调，不保证服务重启后历史票据可验证。
        每次重启都会重新生成密钥，导致旧公钥签发的票据在 Verifier 侧全部失效。
        （未来需要引入持久化的 KMS 或本地密钥文件存储）
        """
        logger.info(f"Generating {bits}-bit RSA key pair for Issuer (This may take a few seconds)...")
        self.key = RSA.generate(bits)
        self.n = self.key.n
        self.e = self.key.e
        self.d = self.key.d
        self.pad_len = bits // 4  # 2048 bits 对应 512 个 Hex 字符
        logger.info("RSA key pair generated successfully.")

    def get_public_key(self) -> dict:
        """
        供客户端下载公钥 (n, e)。
        统一格式：无 '0x' 前缀的纯小写 Hex 字符串。n 左侧补零对齐模长。
        """
        return {
            "n": f"{self.n:0{self.pad_len}x}",
            "e": f"{self.e:x}"
        }

    def blind_sign(self, blinded_message: int) -> int:
        """
        核心盲签逻辑：s' = (m')^d mod n

        【责任边界说明】：
        当前不检查 gcd(blinded_message, n) == 1。
        对于 Textbook RSA，该约束（盲因子可逆性）由客户端在 Blind 阶段保证。
        """
        if blinded_message <= 0 or blinded_message >= self.n:
            raise ValueError("Blinded message is out of bounds (must be 0 < m < n).")

        # Python 内置的 pow() 底层为高效模幂运算
        return pow(blinded_message, self.d, self.n)


# 实例化全局单例
crypto_manager = IssuerCryptoManager()