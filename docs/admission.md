# Admission Primitive Design (准入原语设计) - 最终定稿

## 1. 背景与动机 (Motivation)
在匿名 PIR 架构中，Client 获得盲签名（Ticket）后即脱离身份追踪。为防范 Sybil Attack（女巫攻击）与资源耗尽，必须在发票阶段引入**非对称准入成本**。

**核心约束与定位：**
- **只做前置拦截**：准入系统只负责给 blind issue 施加计算成本。
- **零侵入性**：不改变 Ticket 结构，不改变 Binding 结构，不改变 Verifier 状态机，不侵入 PIR 引擎。

## 2. 原语选型：交互式 Hashcash PoW
本系统采用 **Interactive Hashcash PoW (带状态的交互式工作量证明)**。
- 采用 **HMAC 认证的 Challenge** 确保挑战由 Issuer 动态生成，防伪造、防预计算。
- 准入层使用专用的 **HMAC Secret**，与盲签层的 RSA 密钥在物理与逻辑上完全隔离。

## 3. 核心协议流与 API 映射 (Protocol Flow)

系统对外仅暴露两个 API，彻底规避“验证通过但未签发”的中间态风险。

### 步骤一：申请挑战 (`POST /challenge`)
1. Client 提交自报的短时上下文标识（`client_tag`）。
2. Issuer 构建 **Challenge Payload**（固定包含：`client_tag`, `epoch_id`, `difficulty`, `issued_at`, `expires_at`, `server_nonce`）。
3. Issuer 使用统一的公共函数 `canonical_json_bytes(payload)` 对字典进行规范化序列化。
4. Issuer 计算 `hmac_sig = HMAC_SHA256(issuer_hmac_secret, canonical_bytes)`。
5. 返回 `(payload, hmac_sig)` 给 Client。

### 步骤二：本地计算 (Client-Side Compute)
1. Client 同样调用 `canonical_json_bytes(payload)`。
2. 穷举 `nonce_solution`，直到满足：
   `SHA256(canonical_bytes || hmac_sig || nonce_solution)` 的二进制表示中，**前导零 bit 数 >= payload['difficulty']**。

### 步骤三：验证并签发 (`POST /issue`)
Client 提交 `blinded_message` + `payload` + `hmac_sig` + `nonce_solution`。
Issuer 在单请求内执行无对外中间态暴露的顺序签发流程，严格按以下顺序处理：
1. **验 HMAC 真伪**：重新计算 HMAC 并与 `hmac_sig` 对比。
2. **验时效**：检查 `payload['expires_at']` 未过期，且 `epoch_id` 有效。
3. **验工作量 (PoW)**：验证 SHA256 前导零。（**注：必须绝对信任且仅使用经过 HMAC 认证的 `payload['difficulty']`**）。
4. **消费防重放**：在 Redis 中写入并核销 challenge_fingerprint。
5. **盲签发**：执行 RSA `blind_sign`。

> **异常与烧毁语义 (Burn Semantics)**：若第 4 步 challenge_fingerprint 已成功在 Redis 核销，但随后的第 5 步 blind sign 过程异常失败，则该 challenge 视为**已烧毁 (burned)**。客户端必须重新申请 challenge，绝对不允许复用同一 challenge 重试签发。

## 4. 工程实现隔离契约 (Implementation Contracts)

为防止架构腐化，制定以下四条硬性隔离红线：

### 4.1 序列化复用契约
绝对禁止在各处散落原生的 `json.dumps`。必须在 `common/crypto_utils.py` 中抽象出统一函数：
`def canonical_json_bytes(obj: dict) -> bytes:`
（实现要求：`sort_keys=True`, `separators=(',', ':')`, UTF-8 编码）。Issuer 与 Client 强制复用此函数。

### 4.2 状态机分表契约 (State Separation)
Challenge 重放防护与 Ticket 生命周期**完全隔离**：
- **Challenge 表**：使用独立 Keyspace（如 `admission:challenge:<fingerprint>`）。
    - 唯一指纹定义：`challenge_fingerprint = SHA256(canonical_payload || hmac_sig)`。
    - 仅需简单的 SETNX 机制（存在即已消费），**换算为相对秒数后**，将 TTL 设为 `(expires_at + grace_window) - current_time`。
- **Ticket 表**：保持现有的 SN 状态机（UNUSED/PENDING/CONSUMED/FAILED）不变。

### 4.3 身份禁区契约 (Identity Quarantine)
`client_tag` 仅用于 Admission Challenge 的短时上下文绑定，不得作为长期身份锚点，也不得进入后续匿名 Ticket 消费路径。具体禁令如下：
- **不得**写入 Ticket。
- **不得**参与 Ticket 编码或 Binding 派生。
- **不得**进入 Verifier / PIR / Auditor 的主链对象模型。

### 4.4 配置与日志契约 (Configuration & Logging)
- **极小配置集**：Admission 相关参数必须统一进入 YAML 配置，至少固定包含以下项：
  - `issuer.admission.challenge_ttl_sec`
  - `issuer.admission.grace_window_sec`
  - `issuer.admission.pow_difficulty`
  - `issuer.admission.hmac_secret`
  - `issuer.admission.redis_prefix`
- **日志脱敏**：日志中严禁记录原始 `client_tag`，仅允许记录其哈希截断值与 `challenge_fingerprint` 前缀。