# 核心对象模型与状态机定稿

## 1. 票据与状态模型
### 1.1 票据状态 (TicketState)
在 Redis 中维护的原子状态机：
* `UNUSED`: 初始状态（Redis 中无记录）。
* `PENDING`: 已通过前置验证，正在等待 PIR 引擎返回结果。
* `CONSUMED`: PIR 执行成功，票据正式核销。
* `FAILED`: PIR 执行失败或超时。
  * **严格限制**：只有已经成功进入 `PENDING` 状态的请求，才可能流转为 `FAILED`。前置拒绝不写入任何消费状态。
  * **终态约束**：`FAILED` 为终态；一旦进入该状态，票据即作废（Burned），不可再次使用。

### 1.2 票据对象 (Ticket) 与编码同构约束
对应论文 `t = (SN, sigma, EpochID)`：
* `sn`: 序列号，客户端生成的 256-bit 随机熵（表现为 64 字符纯小写 Hex）。
* `sigma`: 盲签名。**【编码约定】** 采用“定长模数字节串”的 Base64 编码。
* `epoch_id`: 当前时间窗标识。

**⚠️ 【跨服务编码同构约束 (Day 9 追加)】**：
Client 盲化与 Verifier 验签时，必须确保消息 $m$ 与签名 $\sigma$ 的序列化方式完全同构，否则验签必定失败：
1. **被签消息 $m$ 编码**：$m = \text{HexToInteger}( \text{SN} \parallel \text{EpochID}_{32-bit-BigEndian} )$。即 32 字节 SN 加上 4 字节补零对齐的 EpochID。
2. **签名 $\sigma$ 解码**：Verifier 必须先将 Base64 解码为 Bytes，再转为大整数执行 $s^e \pmod n$。

## 2. 绑定与请求模型
### 2.1 绑定机制定义
* **票据派生密钥 (`sk_t`)**：第一版工程约定 `sk_t = SHA256(sigma || sn || epoch_id)`。
  * **编码规范**：参与派生前，`sigma` 使用签名的原始字节串，`sn` 使用 32-byte 原始值，`epoch_id` 使用固定长度大端编码（Big-Endian）；拼接采用明确长度或固定编码，避免歧义拼接。
* **载荷承诺 (Commitment)**: 数学表示为 `c_q = H(q)`，代码层面字段命名为 `query_commitment`。
* **绑定标签 (Binding Tag)**: `b = HMAC(sk_t, c_q || w)`。
* **请求上下文 (Witness)**: `w`。包含时间戳、防重放 nonce 以及客户端状态摘要。
  * **序列化约束**：`w` 的所有字段均参与绑定，必须采用规范化（Canonical）序列化后的字节表示进行 HMAC 计算，防止字段乱序导致验签失败。

## 3. 审计记录模型 (AuditRecord)
用于“最小争议验证”的防篡改日志结构：
* `request_id`: 全局唯一请求追踪 ID。
* `sn`: 票据唯一标识。
* `query_commitment`: 载荷承诺 `c_q`。
* `binding_tag`: 验证绑定一致性。
* `decision`: 最终处理决策（`SUCCESS` / `REJECTED` / `FAILED`）。
* `reason`: 决策的具体原因。
* `timestamp_ms`: 毫秒级时间戳。
* `prev_hash`: 审计链前序哈希。
* `entry_mac`: 审计分录的消息认证码。