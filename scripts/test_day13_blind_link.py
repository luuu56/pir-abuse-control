# scripts/test_day13_blind_link.py
import sys
from pathlib import Path

# 将项目根目录加入 sys.path，保证可以按模块绝对路径导入
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from common.config import load_config
from common.logging_utils import setup_logger
from common.crypto_utils import integer_to_base64
from services.issuer.crypto import IssuerCryptoManager
from services.client.crypto import ClientCryptoManager
from services.verifier.crypto import VerifierCryptoManager

# 【修改 1】使用项目统一配置与日志工厂，对齐工程风格
config = load_config()
logger = setup_logger("day13_test", config)


def run_full_link_test():
    logger.info("=== Starting Day 13 Full Link Blind Signature Test Suite ===")

    # ---------------------------------------------------------
    # 1. 模拟系统初始化 (Issuer 启动)
    # ---------------------------------------------------------
    logger.info("[Init] Bootstrapping Issuer Crypto Manager...")
    issuer = IssuerCryptoManager(bits=2048)
    pub_key = issuer.get_public_key()

    n_int = int(pub_key["n"], 16)
    e_int = int(pub_key["e"], 16)
    modulus_bytes_len = issuer.modulus_bytes_len
    logger.info(f"[Init] Issuer Public Key ready. Modulus bytes: {modulus_bytes_len}")

    # ---------------------------------------------------------
    # 2. 模拟 Client 阶段一：准备盲化请求
    # ---------------------------------------------------------
    logger.info("\n[Client] Preparing blind request...")
    client = ClientCryptoManager()

    sn_hex = client.generate_sn()
    # 【修改 2】使用明确的测试常量，避免与真实业务时间窗混淆
    TEST_EPOCH_ID = 123456

    # 客户端编码消息
    m_int = client.encode_message(sn_hex, TEST_EPOCH_ID)

    # 客户端生成盲因子并盲化
    r = client.generate_blinding_factor(n_int)
    m_prime = client.blind_message(m_int, r, e_int, n_int)
    logger.info("[Client] Blinded message ready. Sending to Issuer...")

    # ---------------------------------------------------------
    # 3. 模拟 Issuer 阶段：执行盲签 (网络边界)
    # ---------------------------------------------------------
    logger.info("\n[Issuer] Received blinded message. Signing...")
    s_prime = issuer.blind_sign(m_prime)
    logger.info("[Issuer] Blind signature generated. Returning to Client...")

    # ---------------------------------------------------------
    # 4. 模拟 Client 阶段二：去盲与 Ticket 组装
    # ---------------------------------------------------------
    logger.info("\n[Client] Received blind signature. Unblinding...")
    s_int = client.unblind_signature(s_prime, r, n_int)

    # 客户端应用定长序列化契约
    sigma_b64 = integer_to_base64(s_int, modulus_bytes_len)

    logger.info("[Client] Ticket successfully assembled!")
    # 【修改 4】截断输出，遵守全项目的 Logging 习惯
    logger.info(f"   - SN: {sn_hex[:16]}...")
    logger.info(f"   - EpochID: {TEST_EPOCH_ID}")
    logger.info(f"   - Sigma: {sigma_b64[:16]}...{sigma_b64[-16:]}")

    # ---------------------------------------------------------
    # 5. Verifier 阶段 A：Happy Path (严格验签)
    # ---------------------------------------------------------
    logger.info("\n[Verifier] (Happy Path) Verifying valid ticket...")
    verifier = VerifierCryptoManager()

    is_valid = verifier.verify_ticket_signature(
        sn_hex=sn_hex,
        epoch_id=TEST_EPOCH_ID,
        sigma_b64=sigma_b64,
        n=n_int,
        e=e_int
    )

    # 【修改 5】携带具体的上下文信息
    assert is_valid, f"Happy path failed! SN={sn_hex[:16]}..., Epoch={TEST_EPOCH_ID}, Modulus={modulus_bytes_len}"
    logger.info("[Verifier] SUCCESS: Happy path verified strictly against modulus length and content.")

    # ---------------------------------------------------------
    # 6. Verifier 阶段 B：Negative Path (轻量反例测试)
    # ---------------------------------------------------------
    logger.info("\n[Verifier] (Negative Path) Testing tamper resistance...")

    # 反例 1：篡改 SN
    tampered_sn = ("0" if sn_hex[0] != "0" else "1") + sn_hex[1:]
    is_valid_tampered_sn = verifier.verify_ticket_signature(
        sn_hex=tampered_sn,
        epoch_id=TEST_EPOCH_ID,
        sigma_b64=sigma_b64,
        n=n_int,
        e=e_int
    )
    assert not is_valid_tampered_sn, "Negative path failed: Tampered SN was accepted!"
    logger.info("   - Tampered SN: Rejected successfully.")

    # 反例 2：破坏 sigma 的 Base64 序列化表示，触发格式/内容边界防御
    # 通过篡改末尾字符，使 verifier 严格校验后的签名表示不再合法
    tampered_sigma_b64 = sigma_b64[:-8] + "A" * 8
    is_valid_tampered_sigma = verifier.verify_ticket_signature(
        sn_hex=sn_hex,
        epoch_id=TEST_EPOCH_ID,
        sigma_b64=tampered_sigma_b64,
        n=n_int,
        e=e_int
    )
    assert not is_valid_tampered_sigma, "Negative path failed: Tampered Sigma length/format was accepted!"
    logger.info("   - Tampered Sigma format: Rejected successfully.")

    logger.info("\n=== Day 13 Full Link Test Suite PASSED ===")


if __name__ == "__main__":
    run_full_link_test()