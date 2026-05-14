# common/models.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum

# --- 状态机与决策定义 ---

class TicketState(str, Enum):
    UNUSED = "UNUSED"       # 隐式初始态：尚未在 Redis 中存在
    PENDING = "PENDING"     # 处理中：已被 Verifier 锁定，正在验证或执行 PIR
    CONSUMED = "CONSUMED"   # 成功终态：已成功完成 PIR 执行
    FAILED = "FAILED"       # 失败终态：PIR 执行失败或超时（票据烧毁，禁止重用）

class Decision(str, Enum):
    SUCCESS = "SUCCESS"
    REJECTED = "REJECTED"
    FAILED = "FAILED"

# --- 核心对象模型 ---

class Ticket(BaseModel):
    """票据对象 t = (SN, sigma, EpochID)"""
    sn: str = Field(..., description="64-character Hex string representing 256-bit original value")
    sigma: str = Field(..., description="Blind RSA Signature (Base64 string)")
    epoch_id: int = Field(..., description="Epoch identifier (Integer)")

class RequestContext(BaseModel):
    """请求上下文 w (Witness), 需规范化序列化后参与 HMAC"""
    timestamp_ms: int = Field(..., description="Millisecond timestamp")
    nonce: str = Field(..., description="Unique anti-replay nonce (e.g., UUIDv4 hex)")
    client_state_digest: Optional[str] = Field(None, description="Client state digest (Hex string) for binding freshness")

class RequestInstance(BaseModel):
    """请求实例 r = (q, t, b, w)"""
    request_id: str = Field(..., description="Global unique tracking ID (UUID/ULID)")
    query_payload: str = Field(..., description="PIR Query Payload (Encoded string/Base64)")
    # Day 21 起为了支持业务层联调与场景化拦截测试，ticket / binding_tag / witness 允许为空；verifier 必须显式做缺失校验。
    ticket: Optional[Ticket] = None
    binding_tag: Optional[str] = None
    witness: Optional[RequestContext] = None

    # Evaluation-only metadata. These fields are ignored by the security logic
    # and are only forwarded to the PIR backend so experiments can record
    # backend-invocation ground truth by request type. Do not use them for
    # authentication, authorization, or policy decisions.
    eval_run_id: Optional[str] = Field(None, description="Evaluation run identifier")
    eval_point_id: Optional[str] = Field(None, description="Evaluation point identifier")
    eval_request_type: Optional[str] = Field(None, description="legit / attack_replay / attack_stale / attack_tamper / replay_preconsume")

# --- 审计与响应模型 ---
# [Day 35] 对外接口的 PIR 结果强类型载荷
class PIRResultPayload(BaseModel):
    result_string: str
    mapped_index: int
    recovered_val: int
# [Day 47] 修正描述：不再特指 Authenticated PIR，而是兼容 APIR/VPIR 风格的证明载荷
    apir_proof: Optional[str] = Field(None, description="Generic APIR/VPIR style cryptographic proof blob")

class PIRResponse(BaseModel):
    request_id: str
    decision: Decision
    ticket_state: Optional[TicketState] = None
    reason: Optional[str] = None
    data: Optional[PIRResultPayload] = None  # 告别 Optional[Any]


# AuditRecord 保持原样，绝不提前塞 mapped_index
class AuditRecord(BaseModel):
    """审计分录 Entry"""
    request_id: str = Field(..., description="Associated request tracking ID")
    sn: str
    query_commitment: str = Field(..., description="c_q = H(q) (Hex string)")
    binding_tag: str
    epoch_id: int
    decision: Decision
    reason: Optional[str] = Field(None, description="Detailed reason for REJECTED/FAILED")
    timestamp_ms: int
    prev_hash: str
    entry_mac: str

# --- 准入原语相关模型 (Day 16 新增/修改) ---

class AdmissionPayload(BaseModel):
    """HMAC 签名的原始载荷"""
    client_tag: str = Field(..., description="Short-lived context tag")
    epoch_id: int = Field(..., description="Day 16 stub: currently fixed at 1")
    difficulty: int = Field(ge=1, le=256)
    issued_at: int
    expires_at: int
    server_nonce: str

class AdmissionChallenge(BaseModel):
    """下发给客户端的挑战包裹"""
    payload: AdmissionPayload
    hmac_sig: str  # Hex

class AdmissionResponse(BaseModel):
    """客户端提交的证明"""
    challenge: AdmissionChallenge
    nonce: int = Field(ge=0, lt=2**64) # 显式约束 uint64 空间，防止溢出

class ChallengeRequest(BaseModel):
    client_tag: str = Field(..., min_length=1)

class IssueRequest(BaseModel):
    blinded_message: str = Field(..., description="Blinded message (Hex string)")
    admission_proof: AdmissionResponse  # 替换原来的 dummy_proof 占位符

class IssueResponse(BaseModel):
    blinded_signature: str = Field(..., description="Blind signature s' (Hex string, zero-padded, no '0x')")