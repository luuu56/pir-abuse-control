# scripts/test_day17_chain.py
import sys
from pathlib import Path

# 将根目录加入 sys.path
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from services.client.main import acquire_ticket


def verify_day17_chain():
    print("🚀 === Day 17: Admission + Blind Ticket Full Chain Test ===")
    try:
        # acquire_ticket 内部已经串联了:
        # Challenge -> PoW -> Blind Issue -> Unblind -> Ticket
        # (注：Public Key Retrieval 仅作为 blind-sign 的前置准备步骤)
        ticket = acquire_ticket()

        print("\n✅ Day 17 Integration Successful!")
        print("--- Final Output Ticket ---")
        print(f"SN (Hex): {ticket.sn}")
        print(f"Epoch ID: {ticket.epoch_id}")
        print(f"Sigma (Base64): {ticket.sigma[:60]}... (truncated)")
        print("---------------------------")
        print("🎉 验收通过：Challenge申请、PoW计算、盲签发与本地去盲验签已完全打通为一条链。")

    except Exception as e:
        print(f"\n❌ Integration Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    verify_day17_chain()