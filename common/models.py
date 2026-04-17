from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

# --- 状态机与决策定义 ---

class TicketState(str, Enum):
    UNUSED = "UNUSED"
    PENDING = "PENDING"
    CONSUMED = "CONSUMED"
    FAILED = "FAILED"  # 终态，不可重试

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
    ticket: Ticket = Field(..., description="Ticket (t)")
    binding_tag: str = Field(..., description="Binding Tag b = HMAC(sk_t, H(q)||w) (Hex string)")
    witness: RequestContext = Field(..., description="Context w")

# --- 审计与响应模型 ---

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

class PIRResponse(BaseModel):
    """标准响应包装"""
    request_id: str
    decision: Decision
    ticket_state: Optional[TicketState] = Field(None, description="Current state of the ticket in DB")
    reason: Optional[str] = Field(None, description="Execution or rejection details")
    data: Optional[str] = Field(None, description="PIR result (Base64/Encoded) if SUCCESS")