import sys
from pathlib import Path

# 将根目录加入 sys.path
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from services.client.main import acquire_ticket, create_bound_request


def test_day19_binding_structure():
    print("🚀 === Day 19: Binding Generation & Request Structure Test ===")
    try:
        # 1. 验证 Ticket 获取成功
        print("Step 1: Acquiring ticket...")
        ticket = acquire_ticket()
        assert ticket is not None, "Ticket acquisition failed"
        assert ticket.sn and ticket.sigma, "Ticket structure is incomplete"
        print(f"✅ Ticket acquired! SN: {ticket.sn[:16]}...")

        # 2. 验证 create_bound_request() 成功
        print("\nStep 2: Creating bound request...")
        test_payload = "day19_test_payload"
        bound_req = create_bound_request(ticket, test_payload)

        # 3. 结构完整性严苛校验
        assert bound_req.request_id, "request_id is empty"
        assert bound_req.ticket is not None, "ticket is missing from request instance"
        assert bound_req.ticket.sn == ticket.sn, "ticket SN mismatch"

        # Binding 专项校验
        assert bound_req.binding_tag, "binding_tag is empty"
        assert len(bound_req.binding_tag) == 64, "binding_tag must be exactly 64-char hex"

        # Witness 专项校验
        assert bound_req.witness is not None, "witness is missing"
        assert bound_req.witness.nonce, "witness nonce is empty"
        assert bound_req.witness.timestamp_ms > 0, "witness timestamp is invalid"

        assert bound_req.query_payload == test_payload, "query_payload was not preserved correctly"

        # 打印关键结构以供肉眼复核
        print(f"✅ Bound request successfully generated and structured!")
        print(f"   - Request ID: {bound_req.request_id}")
        print(f"   - Binding Tag: {bound_req.binding_tag[:16]}... (len: {len(bound_req.binding_tag)})")
        print(f"   - Witness Nonce: {bound_req.witness.nonce}")
        print(f"   - Witness Timestamp: {bound_req.witness.timestamp_ms}")
        print(f"   - Preserved Payload: {bound_req.query_payload}")

        print("\n🎉 [PASS] Day 19 Acceptance Criteria Met: Request instance structure is fully formed.")

    except AssertionError as ae:
        print(f"\n❌ [FAIL] Assertion Error: {ae}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ [FAIL] Unexpected Exception during binding generation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    test_day19_binding_structure()