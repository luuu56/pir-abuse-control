# tests/test_crypto_core.py
import pytest
import base64

from common.crypto_utils import (
    encode_ticket_message,
    integer_to_base64,
    base64_to_integer,
)
from services.issuer.crypto import IssuerCryptoManager
from services.client.crypto import ClientCryptoManager
from services.verifier.crypto import VerifierCryptoManager


@pytest.fixture(scope="module")
def crypto_suite():
    issuer = IssuerCryptoManager(bits=2048)
    client = ClientCryptoManager()
    verifier = VerifierCryptoManager()
    return issuer, client, verifier


def test_crypto_utils_encoding_contracts():
    """测试底层编码契约的异常拦截"""
    # 1. 错误的 SN 长度：传入 62 个字符 (31 bytes)，格式是合法的偶数位，但长度不足 32 bytes
    with pytest.raises(ValueError, match="Invalid SN length"):
        encode_ticket_message("a" * 62, 1)

    # 2. 非法 Hex 字符：故意包含字母 z
    with pytest.raises(ValueError, match="valid hex string"):
        encode_ticket_message("z" * 64, 1)

    # 3. Epoch ID 越界
    with pytest.raises(ValueError, match="out of 32-bit range"):
        encode_ticket_message("a" * 64, -1)

    with pytest.raises(ValueError, match="out of 32-bit range"):
        encode_ticket_message("a" * 64, 2**32)


def test_signature_base64_contract_rejection(crypto_suite):
    """测试非法 Base64 或长度错误的签名表示会被拒绝"""
    issuer, _, _ = crypto_suite
    expected_len = issuer.modulus_bytes_len

    # 1. 非法 Base64 字符
    with pytest.raises(ValueError, match="Invalid Base64 format"):
        base64_to_integer("%%%not_base64%%%", expected_len)

    # 2. 长度不匹配 (动态构造比期望长度少 1 个字节的串)
    import base64
    short_bytes = b"\x01" * (expected_len - 1)
    short_b64 = base64.b64encode(short_bytes).decode("utf-8")
    with pytest.raises(ValueError, match="does not match expected"):
        base64_to_integer(short_b64, expected_len)


def test_blind_message_rejects_message_out_of_modulus(crypto_suite):
    """测试当 m >= n 时，Client 盲化逻辑会直接拒绝"""
    issuer, client, _ = crypto_suite
    n_int = issuer.n
    e_int = issuer.e
    r = client.generate_blinding_factor(n_int)

    # 故意传入等于模数 n 的消息
    with pytest.raises(ValueError, match="smaller than RSA modulus"):
        client.blind_message(n_int, r, e_int, n_int)


def test_signature_base64_round_trip(crypto_suite):
    """测试签名定长 Base64 编码与解码 round-trip 一致性"""
    issuer, client, _ = crypto_suite
    n_int = issuer.n
    e_int = issuer.e
    epoch_id = 42

    sn_hex = client.generate_sn()
    m_int = client.encode_message(sn_hex, epoch_id)
    r = client.generate_blinding_factor(n_int)
    m_prime = client.blind_message(m_int, r, e_int, n_int)
    s_prime = issuer.blind_sign(m_prime)
    s_int = client.unblind_signature(s_prime, r, n_int)

    sigma_b64 = integer_to_base64(s_int, issuer.modulus_bytes_len)
    recovered_int = base64_to_integer(sigma_b64, issuer.modulus_bytes_len)

    assert recovered_int == s_int


def test_full_blind_signature_happy_path(crypto_suite):
    """测试标准的盲化、签发、去盲、验签全链路"""
    issuer, client, verifier = crypto_suite
    pub_key = issuer.get_public_key()
    n_int = int(pub_key["n"], 16)
    e_int = int(pub_key["e"], 16)
    epoch_id = 9999

    sn_hex = client.generate_sn()
    m_int = client.encode_message(sn_hex, epoch_id)
    r = client.generate_blinding_factor(n_int)
    m_prime = client.blind_message(m_int, r, e_int, n_int)

    s_prime = issuer.blind_sign(m_prime)

    s_int = client.unblind_signature(s_prime, r, n_int)
    sigma_b64 = integer_to_base64(s_int, issuer.modulus_bytes_len)

    is_valid = verifier.verify_ticket_signature(
        sn_hex=sn_hex,
        epoch_id=epoch_id,
        sigma_b64=sigma_b64,
        n=n_int,
        e=e_int,
    )
    assert is_valid is True


def test_signature_tampering_rejection(crypto_suite):
    """测试各类篡改场景下验签必定失败"""
    issuer, client, verifier = crypto_suite
    n_int = issuer.n
    e_int = issuer.e
    epoch_id = 1234

    sn_hex = client.generate_sn()
    m_int = client.encode_message(sn_hex, epoch_id)
    r = client.generate_blinding_factor(n_int)
    s_prime = issuer.blind_sign(client.blind_message(m_int, r, e_int, n_int))
    s_int = client.unblind_signature(s_prime, r, n_int)
    sigma_b64 = integer_to_base64(s_int, issuer.modulus_bytes_len)

    # 1. 篡改 SN
    tampered_sn = ("1" if sn_hex[0] == "0" else "0") + sn_hex[1:]
    assert not verifier.verify_ticket_signature(tampered_sn, epoch_id, sigma_b64, n_int, e_int)

    # 2. 篡改 EpochID
    assert not verifier.verify_ticket_signature(sn_hex, epoch_id + 1, sigma_b64, n_int, e_int)

    # 3. 篡改 sigma 的 Base64 表示，Verifier 必须拒绝
    tampered_sigma = sigma_b64[:-10] + "A" * 10
    assert not verifier.verify_ticket_signature(sn_hex, epoch_id, tampered_sigma, n_int, e_int)