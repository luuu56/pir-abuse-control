# common/crypto_utils.py

def encode_ticket_message(sn_hex: str, epoch_id: int) -> int:
    """
    【统一编码契约】
    将 SN 与 EpochID 拼接：SN(32 bytes) || EpochID(4 bytes big-endian)
    """
    if len(sn_hex) != 64:
        raise ValueError(f"Invalid SN length: expected 64, got {len(sn_hex)}")

    # 验证是否为合法 hex
    try:
        int(sn_hex, 16)
    except ValueError:
        raise ValueError("SN must be a valid hex string")

    if not (0 <= epoch_id <= 0xffffffff):
        raise ValueError(f"EpochID {epoch_id} out of 32-bit range")

    epoch_hex = f"{epoch_id:08x}"
    encoded_hex = sn_hex + epoch_hex
    return int(encoded_hex, 16)