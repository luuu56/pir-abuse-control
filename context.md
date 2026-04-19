# PIR 匿名抗滥用访问控制原型 - 当前上下文

## 一、固定前提（当前不变）

- 主线：`blind ticket -> admission -> binding -> verifier -> PIR -> audit`
- blind signature 第一版：`RSA blind signature`
- PIR 后端：`独立进程 / 微服务集成`
- 状态机：`UNUSED / PENDING / CONSUMED / FAILED`
- eBPF 第一版：`仅轻量前置过滤`
- Python 服务：`统一 YAML 配置 + 统一 logging`
- 当前项目目录位于：`WSL Linux 文件系统`

---

## 二、当前阶段结论

当前项目已经完成从 **Issuer -> Client -> Verifier** 的第一段闭环，并进一步完成了：

- Admission primitive 第一版落地
- blind ticket 与 admission 的主链整合
- epoch 时间窗正式接入 Ticket 主链
- binding 生成逻辑正式落地
- verifier 侧 binding verify 正式落地
- 本周联调完成（四类核心场景已真实区分）
- Redis 原子防重放与票据生命周期流转（已有第一版实现）
- Verifier -> PIR Server 的第一阶段网络桥接
- blind-sign 主链路的第一批核心单测与错误码 / API 收口
- Day 22：Redis 状态表与状态查询接口收口
- Day 23：`UNUSED -> PENDING` 原子核销并发验收通过
- Day 24：判定路径绑定原子核销已通过验收
- Day 25：tamper-evident 审计日志已通过验收
- Day 26：Auditor 查询接口已通过验收
- Day 27：最小争议验证闭环已通过验收
- Day 28：verifier 阶段重构已最终收口
- Day 29：真实主候选 PIR 正式接入并通过确定性验收

当前已完成：

- Issuer blind-sign API
- Issuer admission challenge / verify_admission / issue 内联 admission 校验
- Issuer 公钥真实接口：`GET /api/v1/issuer/public_key`
- Client blind / unblind 与 ticket acquisition
- Client 侧 admission -> blind issue -> unblind -> local verify 整合主链
- epoch 时间窗配置与统一 epoch 公共函数
- Ticket 中 `epoch_id` 的动态计算与有效性校验
- binding 所需的 `query_commitment / witness / binding_tag` 生成逻辑
- `create_bound_request(ticket, query_payload)` 主链收口
- Verifier RSA signature verification
- Verifier binding consistency check
- Verifier 对缺失 ticket / 缺失 witness / 缺失 binding_tag / 过期 epoch / binding 篡改的业务拒绝语义
- Redis 原子防重放与票据生命周期流转
- PIR Server HTTP 适配层（Stub）
- Verifier 跨服务调用 PIR Server
- 审计本地日志存根
- blind-sign / verify 第一批核心单测
- Day 22 Redis 状态表管理器
- `GET /api/v1/verifier/ticket_state/{sn}` 状态查询接口
- Day 23 并发原子核销验收脚本
- Day 24 判定路径与票据终态绑定一致性验收脚本
- Day 25 链式 HMAC 审计账本
- Day 26 Auditor trace 查询接口
- Day 27 最小争议验证脚本与证据闭环
- Day 28 verifier 分层重构与最终回归确认
- Day 29 `pir_server` subprocess JSON bridge
- Day 29 Go wrapper 主候选入口：
  - `pir_engine/simplepir/cmd/json_bridge`
- Day 29 真实 SimplePIR 最小调用链：
  - `Init`
  - `Setup`
  - `Query`
  - `Answer`
  - `Recover`

当前 Day 12 生命周期在跨服务模式下已再次通过 4 条关键验收：

1. 并发冲突命中 `PENDING`
2. PIR 执行失败后票据转 `FAILED`
3. 正常执行后票据转 `CONSUMED`
4. 前置验证失败不吞票，票据保持 `UNUSED`

当前 Day 13 blind-sign 全链路联调已完成：

- blind issue
- unblind
- verify
- ticket object 贯通
- 最小反例（篡改 `SN` / 篡改 `sigma` 表示）验证通过

当前 Day 14 第一批核心单测已通过：

- 执行：
  - `PYTHONPATH=. pytest -q tests/test_crypto_core.py`
- 结果：
  - `6 passed`

当前 Day 16 admission primitive 第一版已通过基础验收：

1. 不带 `admission_proof` 调 `/issue` -> 失败（422）
2. 伪造 `hmac_sig` -> `/verify_admission` 返回 403
3. 正确 challenge + 错误 nonce -> `/issue` 返回 403
4. 同一 challenge 连续 issue 两次 -> 第一次 200，第二次 403（Redis burn semantics 生效）

当前 Day 17 blind ticket + admission 已完成整合，并通过最小链路与全链路烟雾测试：

1. `challenge` 申请成功
2. PoW 求解成功
3. `/issue` 完成 blind sign
4. Client 去盲成功
5. Client 本地验签成功
6. 成功输出最终 `Ticket`
7. 全链路烟雾测试通过：
   - Binding 成功
   - Verifier 放行成功
   - PIR Server 返回成功
   - 最终 `decision = SUCCESS`

当前 Day 18 epoch 时间窗机制已正式接入 Ticket 与 Verifier 验证路径，并通过过期票据拒绝验收：

1. 获取当前 epoch 的合法 ticket 成功
2. 将 ticket epoch 强制改为两个纪元之前
3. Verifier 返回：
   - `decision = REJECTED`
   - `reason = Ticket epoch ... has expired`
4. Verifier 日志记录：
   - `Fast-rejecting expired ticket epoch`

当前 Day 19 binding 生成逻辑已正式接入 `RequestInstance` 构造流程，并通过结构完整性验收：

1. 合法 Ticket 获取成功
2. `create_bound_request()` 成功执行
3. 成功生成完整 `RequestInstance`
4. `binding_tag` 成功生成，长度为 64
5. `witness.nonce`、`witness.timestamp_ms` 均正常
6. `query_payload` 被正确保留

当前 Day 20 verifier 侧 binding verify 已真实生效，并通过全分支验收：

1. 合法 Ticket + 合法 Bound Request 生成成功
2. 篡改 `query_payload` -> 被拒绝
3. 篡改 `binding_tag` -> 被拒绝
4. 篡改 `witness.nonce` -> 被拒绝
5. 移除 `witness` -> 被拒绝
6. 原始合法请求 -> `decision = SUCCESS`

当前 Day 21 本周联调已完成，并证明系统能够真实区分四类核心场景：

1. 正常请求（Happy Path）
2. 无票据请求（Missing Ticket）
3. 过期票据（Expired Ticket）
4. 篡改 binding 请求（Binding Consistency Failure）

当前 Day 22 已完成 Redis 状态表核心语义与状态查询接口收口：

1. `Redis miss == UNUSED` 已明确为逻辑默认态
2. 不要求 Issuer 在签发时物理预写 `UNUSED` 状态，避免与签发链耦合
3. `TicketStateManager` 已接入统一 YAML 配置
4. Redis key 已支持统一前缀
5. 终态 `CONSUMED / FAILED` 已支持基于 `epoch_id` 的 TTL 推导
6. `ttl_override_sec` 仅保留给测试/联调用
7. Verifier 已提供：
   - `GET /api/v1/verifier/ticket_state/{sn}`
8. 验收结果：
   - Redis miss 默认返回 `UNUSED`
   - `PENDING` 原子占位成功
   - `CONSUMED` 终态写入成功
   - TTL 过期后 Redis key 被物理清理，逻辑状态回归 `UNUSED`
   - 非法 SN 查询返回 `400 Bad Request`

当前 Day 23 已完成 `UNUSED -> PENDING` 原子核销的并发验收：

1. 基于 Redis `SETNX` 语义实现 `try_lock(sn, lock_ttl_sec=...)`
2. 新增 `scripts/test_day23_concurrency.py`
3. 使用 `threading.Barrier` 实现 50 个并发线程统一起跑
4. 同一 `SN` 在 50 个并发请求中：
   - 仅 1 个请求成功占位
   - 49 个请求被原子拦截
5. 并发结束后，票据最终状态稳定为 `PENDING`

当前 Day 24 已完成判定路径绑定原子核销的验收：

1. 只有当前置验证全部通过，且成功执行 `try_lock()` 将票据推进到 `PENDING` 时，请求才允许进入 PIR 主路径
2. 当前置验证失败时，请求被直接拒绝，票据状态保持 `UNUSED`，不会误吞票
3. 当 PIR 后端执行成功时，票据状态由 `PENDING -> CONSUMED`，并返回：
   - `decision = SUCCESS`
   - `ticket_state = CONSUMED`
4. 当 PIR 后端执行失败或调用异常时，票据状态由 `PENDING -> FAILED`，并返回：
   - `decision = REJECTED`
   - `ticket_state = FAILED`
   - `reason` 包含 burned 语义

当前 Day 25 已完成 tamper-evident 审计日志的验收：

1. Auditor 采用链式 HMAC 账本方案
2. 每条记录覆盖至少以下字段：
   - `sn`
   - `query_commitment`
   - `decision`
   - `timestamp_ms`
   - `prev_hash`
   - `entry_mac`
3. Auditor 与验收脚本统一采用以下 MAC payload 顺序：
   - `sn | query_commitment | decision | timestamp_ms | prev_hash`
4. 真实账本完整性验证通过
5. 篡改副本中单条记录后，`entry_mac` 校验失败
6. 篡改能够被明确发现，真实账本未被污染

当前 Day 26 已完成 Auditor 查询接口验收：

1. 已新增：
   - `GET /api/v1/auditor/trace/{sn}`
2. 当前接口支持：
   - 按 `SN` 查询单条审计记录
   - 返回所在账本行号 `ledger_line`
   - 返回链上下文字段：
     - `prev_hash`
     - `entry_mac`
   - 在传入 `expected_cq` 时执行最小一致性判定
3. 验收结果：
   - 按 `SN` 可成功追溯到目标请求
   - 正确 `c_q` 一致性判定成功
   - 伪造 `c_q` 一致性判定失败

当前 Day 27 已完成最小争议验证闭环验收：

1. 已可组合使用三类证据：
   - HTTP 响应证据
   - Verifier 状态证据
   - Auditor 审计证据
2. 已覆盖争议场景：
   - 前置拦截（Dropped Request）
   - 处理中重放（PENDING Collision）
   - 已核销重放（CONSUMED Collision）
   - 后端失败与烧毁重放（FAILED Collision）
3. 已证明：
   - 被 drop 的请求能解释原因
   - 进入 `PENDING` 的请求能查到处理中痕迹
   - 成功完成的请求能证明状态转为 `CONSUMED`
   - 后端失败或异常中断的请求能证明状态转为 `FAILED`
   - replay 请求能区分命中 `PENDING / CONSUMED / FAILED`

当前 Day 28 已完成 verifier 阶段重构的最终收口：

1. `services/verifier/main.py` 当前已稳定拆分为三层：
   - `_run_precondition_check`
   - `_run_crypto_verification`
   - `execute_query`
2. 当前外部契约保持不变：
   - `Missing Ticket in request`
   - `Invalid Ticket Signature`
   - `Missing Request Witness`
   - `Missing Binding Tag`
   - `Binding Consistency Check Failed`
   - `Invalid Binding Material`
   - `Invalid SN format: must be 64-char hex`
3. 当前状态机主路径仍保持：
   - `UNUSED -> PENDING -> CONSUMED`
   - `UNUSED -> PENDING -> FAILED`
4. `call_pir_server()` 异常分类已恢复为：
   - `timeout`
   - `http_error_<code>`
   - `connection_error`
   - `unknown_error`
5. 最终版回归已完成以下三组高强度验收：
   - `scripts/test_day27_dispute_resolution.py`
   - `scripts/test_day26_auditor_trace.py`
   - `scripts/test_day25_audit_chain.py`

当前 Day 29 已完成“真实主候选 PIR 正式接入”的阶段性收口：

1. `pir_server` 的 subprocess 桥接层已收口为 JSON stdin/stdout 协议
2. Go wrapper 已从独立 mock 外部脚本推进为主候选仓库内的真实桥接入口：
   - `pir_engine/simplepir/cmd/json_bridge`
3. 已恢复并保留边界验收分支：
   - `fatal_crash_test`
   - `bad_json_test`
   - `status_error_test`
4. 已解决真实加密区 stdout 污染 JSON 协议的问题
5. 已在 Go wrapper 中接入真实 SimplePIR 最小调用链，并对齐官方 `RunPIR` 顺序：
   - `Init`
   - `Setup`
   - `Query`
   - `Answer`
   - `Recover`
6. 当前 Day 29 的确定性基线为：
   - `numEntries = 1024`
   - 固定小型 DB
   - `vals[42] = 4242`
   - 查询索引 `42`
   - 期望恢复真值 `4242`
7. 已通过两类关键验收：
   - Go wrapper 边界验收（正常成功、进程崩溃隔离、协议脏数据拦截、`status=error` 逻辑失败）
   - 真实主候选确定性验收（Python 请求成功穿透 `pir_server -> subprocess -> Go wrapper`，真实 SimplePIR 核心被成功调用，固定索引 `42` 成功恢复固定真值 `4242`）

因此，当前项目已经从“本地 stub 语义的 verifier”进入“blind-sign 主链稳定、admission 第一版落地并已并入签票主链、epoch 时间窗已正式接入、binding 生成与 verifier 侧 binding verify 均已落地、主链核心场景已完成本周联调区分验证、Redis 状态表已完成 Day 22 收口、Day 23 原子核销并发验收通过、Day 24 判定与消费语义一致性已落地、Day 25–27 审计留痕/追溯/争议闭环已形成、Day 28 verifier 内部结构已稳定收口、Day 29 Python 控制层已可实际驱动真实主候选 SimplePIR 计算、并保持独立进程 / 微服务边界不变”的阶段。

---

## 三、当前已经固化的关键工程契约

### 1. Ticket 结构
当前 `Ticket` 语义保持不变：

- `sn`: 256-bit 随机序列号，64 字符 hex
- `sigma`: RSA 签名，存为 Base64
- `epoch_id`: 当前时间窗标识

即：

- `t = (SN, sigma, EpochID)`

### 2. Ticket 被签消息的统一编码契约
当前 blind-sign / verify 两端统一采用：

- `m = SN(32 bytes) || EpochID(4 bytes big-endian)`

工程上统一入口为：

- `common.crypto_utils.encode_ticket_message(sn_hex, epoch_id)`

说明：

- Client 与 Verifier 不允许再各自维护独立编码逻辑
- 后续所有 ticket 验签都必须复用这份统一函数

### 3. sigma 的工程存储约定
当前 `sigma` 的存储语义已经定下：

- `sigma` = **定长模数字节串** 的 Base64 编码

因此 Verifier 验签时必须严格执行：

1. `base64.b64decode(sigma)`
2. 恢复为定长字节串
3. `int.from_bytes(..., "big")` 得到签名整数 `s`
4. 验证 `pow(s, e, n) == m`

### 4. Admission Primitive 第一版约定
当前 admission primitive 第一版采用：

- **Interactive Hashcash PoW**
- **HMAC-authenticated challenge**
- **Redis challenge burn semantics**

当前 admission 契约包括：

- `client_tag` 仅作为短时上下文标识使用
- challenge payload 必须采用规范化序列化
- Issuer 使用 HMAC secret 对 challenge payload 认证
- `admission_proof` 必须在 `/issue` 前通过校验
- challenge 只允许单次成功消费
- challenge replay 防护与 Ticket 生命周期状态机分表

### 5. Epoch 时间窗统一契约
当前 epoch 已接入 Ticket 主链，并由 Issuer / Verifier 共用统一公共函数：

- `get_current_epoch_id(epoch_duration)`
- `is_epoch_valid(ticket_epoch, now_ts, duration, grace)`

统一规则：

1. `ticket_epoch == current_epoch`：有效
2. `ticket_epoch == current_epoch - 1`：仅在 grace window 内有效
3. 其他情况：无效

当前 epoch 相关配置来自统一 YAML：

- `epoch.duration_sec`
- `epoch.grace_window_sec`

### 6. Binding 第一版契约
当前 binding 已从“仅生成”推进到“生成 + verifier 侧验证”两个阶段。

#### 6.1 载荷承诺
- `c_q = SHA256(query_payload)`
- 工程函数：
  - `compute_query_commitment(query_payload)`

#### 6.2 票据派生密钥
- `sk_t = derive_sk_t(sigma_bytes, sn, epoch_id)`
- 当前继续沿用既有工程派生实现

#### 6.3 请求上下文
- `witness = {timestamp_ms, nonce, client_state_digest}`
- 规范化序列化入口：
  - `serialize_witness(witness.model_dump())`

#### 6.4 绑定标签
- `b = HMAC_SHA256(sk_t, c_q || w)`
- 工程函数：
  - `compute_binding_tag(sk_t, c_q_hex, witness_bytes)`

#### 6.5 Verifier 侧 binding consistency check
当前 verifier 侧 binding 校验流程为：

1. 检查 `req.witness` 是否存在
2. 重算 `expected_c_q = compute_query_commitment(req.query_payload)`
3. 还原 `sigma_bytes = base64.b64decode(req.ticket.sigma, validate=True)`
4. 派生 `expected_sk_t = derive_sk_t(sigma_bytes, req.ticket.sn, req.ticket.epoch_id)`
5. 规范化序列化 `witness_bytes = serialize_witness(req.witness.model_dump())`
6. 重算 `expected_binding_tag = compute_binding_tag(expected_sk_t, expected_c_q, witness_bytes)`
7. 使用 `hmac.compare_digest(req.binding_tag, expected_binding_tag)` 进行一致性比较

当前拒绝语义包括：

- `Missing Request Witness`
- `Missing Binding Tag`
- `Binding Consistency Check Failed`
- `Invalid Binding Material`

### 7. Issuer 公钥的当前约束
当前 Issuer 第一版为了简化原型：

- 服务启动时在内存中动态生成 RSA key pair
- 每次重启都会更换 key

因此当前 Client / Verifier 采取的策略是：

- 从 Issuer 真实网络接口获取公钥
- 不再依赖本地硬编码公钥 stub
- 若刷新失败，则拒绝继续基于旧 key 工作

这只是当前原型阶段策略，后续若进入稳定阶段需要考虑持久化或固定 key 管理。

### 8. Redis 状态表第一版契约（Day 22）
当前 Day 22 的 Redis 状态表契约为：

- Redis 以 `SN` 为核心管理票据状态
- 当前 key 形态为：
  - `"{ticket_state_prefix}:{sn}"`
- 当前 Redis value 第一版仅保存：
  - `PENDING`
  - `CONSUMED`
  - `FAILED`
- `UNUSED` 不强制物理存储，作为逻辑默认态存在：
  - Redis miss == `UNUSED`

当前状态查询入口：

- `services.verifier.state_manager.get_state(sn)`
- `GET /api/v1/verifier/ticket_state/{sn}`

当前终态 TTL 契约：

- 正式主流程优先传入 `epoch_id`
- TTL 基于以下规则推导：
  - 票据所属 epoch 结束时间
  - `+ grace_window_sec`
  - `+ retention buffer (当前为 600 秒)`
- `ttl_override_sec` 仅用于测试 / 联调

### 9. 原子核销第一版契约（Day 23）
当前 Day 23 的原子核销契约为：

- `try_lock(sn, lock_ttl_sec=...)`
- 基于 Redis `SETNX` 语义执行原子占位
- 目标状态转换为：
  - `UNUSED -> PENDING`
- 语义保证：
  - 同一 `SN` 在并发竞争下只允许一次成功
  - 其余并发请求必须命中失败分支
- 当前并发验收已通过：
  - 50 并发线程
  - 1 次成功
  - 49 次失败
  - 最终状态落点为 `PENDING`

### 10. 判定路径与原子核销绑定契约（Day 24）
当前 Day 24 的主路径契约为：

1. 只有当前置验证全部通过，且 `try_lock()` 成功将票据推进到 `PENDING` 时，请求才允许进入 PIR 主路径
2. 前置验证失败时，请求必须直接拒绝，票据状态保持 `UNUSED`
3. PIR 成功时：
   - `PENDING -> CONSUMED`
4. PIR 失败时：
   - `PENDING -> FAILED`

这意味着：

- “是否进入 PIR” 与 “是否成功占位到 `PENDING`” 已绑定
- “PIR 执行结果” 与 “票据终态” 已绑定
- 当前判定路径与票据消费语义已一致

### 11. tamper-evident 审计日志契约（Day 25）
当前 Day 25 第一版采用链式 HMAC 审计日志方案。

当前至少覆盖以下字段：

- `sn`
- `query_commitment`
- `decision`
- `timestamp_ms`
- `prev_hash`
- `entry_mac`

当前 Auditor 与验收脚本统一采用以下顺序计算 HMAC：

- `sn | query_commitment | decision | timestamp_ms | prev_hash`

说明：

- 该顺序是 Day 25 第一版固定契约
- 若后续扩展字段，必须同步更新 Auditor 与本地验收脚本

当前实现约束：

- Auditor 作为唯一落账方
- 使用 `threading.Lock()` 保护当前进程内顺序落账
- 账本按 JSONL 顺序写入 `audit_ledger.jsonl`
- Auditor 启动时通过 `lifespan` 恢复链状态

### 12. Auditor 最小追溯契约（Day 26）
当前已新增：

- `GET /api/v1/auditor/trace/{sn}`

当前接口支持：

1. 按 `SN` 查询单条审计记录
2. 返回该条记录所在账本行号
3. 返回链上下文字段：
   - `prev_hash`
   - `entry_mac`
4. 当传入 `expected_cq` 时，执行最小一致性判定

当前原型假设：

- 一张票据最终只对应一条主审计记录
- 因此当前接口按 `SN` 找到即停

### 13. 最小争议验证契约（Day 27）
当前系统已可组合使用以下三类证据：

1. HTTP 响应证据
2. Verifier 状态证据
3. Auditor 审计证据

当前已覆盖争议场景：

- 前置拦截（Dropped Request）
- 处理中重放（PENDING Collision）
- 已核销重放（CONSUMED Collision）
- 后端失败与烧毁重放（FAILED Collision）

### 14. verifier 分层重构契约（Day 28）
当前 `services/verifier/main.py` 已稳定拆分为三层：

1. `_run_precondition_check`
2. `_run_crypto_verification`
3. `execute_query`

当前外部行为保持不变：

- `Missing Ticket in request`
- `Invalid Ticket Signature`
- `Missing Request Witness`
- `Missing Binding Tag`
- `Binding Consistency Check Failed`
- `Invalid Binding Material`
- `Invalid SN format: must be 64-char hex`

当前 `call_pir_server()` 异常分类保持：

- `timeout`
- `http_error_<code>`
- `connection_error`
- `unknown_error`

因此，当前 `services/verifier/main.py` 已可视为本阶段稳定收口版本。

### 15. 真实主候选 PIR 接入契约（Day 29）
当前 Day 29 保持以下架构前提不变：

- PIR 后端继续保持独立进程 / 微服务边界
- Python `pir_server` 继续仅作为 adapter / 控制层
- 未引入 Python 进程内 FFI 硬绑定 Go/C/C++ PIR 引擎
- 未破坏既有 `stub / subprocess` 双模式和前序回归路径

当前 subprocess bridge 契约为：

- Python 与 Go wrapper 通过 JSON stdin/stdout 交互
- 主候选桥接入口为：
  - `pir_engine/simplepir/cmd/json_bridge`

当前保留的边界失败分支：

- `fatal_crash_test`
- `bad_json_test`
- `status_error_test`

当前真实主候选确定性基线为：

- `numEntries = 1024`
- 固定小型 DB
- `vals[42] = 4242`
- 查询索引 `42`
- 期望恢复真值 `4242`

当前 Go wrapper 已对齐官方最小调用顺序：

- `Init`
- `Setup`
- `Query`
- `Answer`
- `Recover`

说明：

- 当前只是“真实主候选 PIR 已正式接入并可被 Python 控制层驱动”
- 还未完成 `q -> PIR query` 正式映射、最终 I/O 协议收口与 DB / hint 生命周期优化

---

## 四、当前 Verifier 的真实语义边界

当前 `/api/v1/verifier/execute` 已具备如下真实语义：

当前已做：

- 接收 `RequestInstance`
- 在最前面执行 epoch 快拒绝
- 显式检查 ticket / witness / binding_tag 是否缺失
- 提取并校验 `ticket`
- 校验 RSA 签名是否有效
- 校验 binding consistency
- 查询并推进 Redis 状态机
- 在进入后端执行前将票据原子推进为 `PENDING`
- 通过 HTTP 将合法请求转发至 `PIR Server`
- 根据 PIR Server 返回结果将票据推进为：
  - `CONSUMED`
  - `FAILED`
- 主链完成后异步投递审计记录，不阻塞客户端主返回

当前额外已具备：

- `GET /api/v1/verifier/ticket_state/{sn}`：
  - 用于只读查询当前票据逻辑状态
  - 要求 `sn` 为 64-char hex
  - Redis miss 返回 `UNUSED`

当前拒绝语义已明确：

- `Missing Ticket in request`：请求缺失 ticket 时业务拒绝
- `PENDING`：表示 in-flight / 并发 replay
- `CONSUMED`：表示 double spend / replay after success
- `FAILED`：表示 burned ticket / replay after execution failure
- `Ticket epoch ... has expired`：epoch 失效时业务拒绝
- `Missing Request Witness`：缺失 witness 时拒绝
- `Missing Binding Tag`：缺失 binding_tag 时拒绝
- `Binding Consistency Check Failed`：`q / b / w` 任一被篡改时拒绝
- `Invalid Binding Material`：binding 材料异常时业务拒绝
- 其他前置验证失败：请求被拒绝，但票据状态保持 `UNUSED`

当前审计语义：

- Verifier 已完成异步审计投递分层
- Auditor 已具备落账、最小追溯与最小一致性核查能力
- 当前已达到原型阶段“可留痕、可最小追溯、可最小对账、可争议解释”的水平

当前 blind-sign 语义：

- blind-sign 已成为唯一主线
- 不再保留普通签名占位路径
- 核心 blind-sign / verify 契约已开始由 `pytest` 单测稳定回归

当前仍未完全做完：

- Auditor 更强威胁模型下的密钥托管与外部锚定
- 审计多事件追踪模式
- `q -> PIR query` 的正式映射
- Python 与独立 PIR 后端之间的最终输入输出协议
- 输出解析与错误返回路径标准化
- DB / hint 生命周期与性能优化

---

## 五、当前对象与请求模型状态

当前仍对齐既定对象模型：

### Ticket
- `t = (SN, sigma, EpochID)`

### RequestInstance
- `r = (q, t, b, w)`

当前 `RequestInstance` 为支持 Day 21 业务层联调与场景化拦截测试，字段已调整为：

- `request_id`
- `query_payload`
- `ticket: Optional[Ticket] = None`
- `binding_tag: Optional[str] = None`
- `witness: Optional[RequestContext] = None`

当前这些字段的状态如下：

- `request_id`：用于请求跟踪
- `query_payload`：当前已进入 binding 生成与 verifier 侧重算校验
- `ticket`：允许为空以支持无票据业务场景联调；Verifier 必须显式检查
- `binding_tag`：允许为空以支持业务层场景化测试；Verifier 必须显式检查
- `witness`：允许为空以支持业务层场景化测试；Verifier 必须显式检查

说明：

- 这些字段允许为空是为了支持 Day 21 业务层联调
- 不能依赖 Pydantic 422 代替业务拒绝
- 业务语义必须由 verifier 显式区分处理

### Admission 相关对象
当前 admission 第一版已引入：

- `AdmissionPayload`
- `AdmissionChallenge`
- `AdmissionResponse`
- `ChallengeRequest`
- `IssueRequest.admission_proof`

说明：

- blind issue 已不再只接收 `blinded_message`
- `admission_proof` 已进入 `/issue` 的前置校验路径

### TicketState
当前 Day 22 / Day 23 / Day 24 已使用统一状态枚举：

- `UNUSED`
- `PENDING`
- `CONSUMED`
- `FAILED`

说明：

- `UNUSED` 为逻辑默认态
- Redis 不要求预写物理 `UNUSED`
- `PENDING` 为原子占位后的处理中状态
- `CONSUMED / FAILED` 为 PIR 成功 / 失败后的终态
- 对外查询与内部状态机语义统一使用同一枚举

---

## 六、当前测试与验收状态

### 已通过的验证
1. Issuer API 可工作
2. Client 可成功获取合法 Ticket
3. Client 本地验签通过
4. Verifier 可对合法 Ticket 验签通过
5. Verifier 可拒绝篡改 `SN`
6. Verifier 可拒绝篡改 `sigma`
7. Day 12 生命周期 4 条关键分支已通过
8. Day 13 blind-sign 全链路正反例已通过
9. Day 14 `tests/test_crypto_core.py` 已通过（6 passed）
10. Day 16 admission primitive 第一版反例验收已通过
11. Day 17 blind ticket + admission 整合链路已通过
12. Day 17+ 全链路烟雾测试已通过
13. Day 18 epoch 时间窗过期拒绝验收已通过
14. Day 19 binding 生成结构完整性验收已通过
15. Day 20 verifier 侧 binding verify 全分支验收已通过
16. Day 21 本周联调已完成，四类核心场景均能被真实区分处理
17. Day 22 Redis 状态表核心语义已通过：
   - Redis miss == `UNUSED`
   - `PENDING` 原子占位成功
   - 终态可写入
   - Epoch 关联 TTL 生效
   - TTL 过期后逻辑状态回归 `UNUSED`
18. Day 22 verifier 状态查询接口已通过：
   - 合法 64-char hex `SN` 返回 200 + `ticket_state`
   - 非法 `SN` 返回 400
19. Day 23 原子核销并发验收已通过：
   - 50 并发线程统一起跑
   - 1 次成功
   - 49 次失败
   - 最终状态 `PENDING`
20. Day 24 判定路径绑定原子核销语义验收已通过：
   - 正常请求 -> `SUCCESS + CONSUMED`
   - 无票据请求 -> `REJECTED + UNUSED`
   - 过期票据 -> `REJECTED + UNUSED`
   - 篡改 binding -> `REJECTED + UNUSED`
   - PIR 后端失败 -> `REJECTED + FAILED`
21. Day 25 审计账本防篡改链验收已通过：
   - 真实账本完整性验证通过
   - 篡改副本后 `entry_mac` 校验失败
22. Day 26 Auditor trace 与一致性查询验收已通过：
   - 按 `SN` 成功追溯
   - 正确 `c_q` 一致
   - 伪造 `c_q` 不一致
23. Day 27 最小争议验证闭环验收已通过：
   - drop / `PENDING` / `CONSUMED` / `FAILED` 四类争议均可给出最小证据解释
24. Day 28 verifier 最终重构回归已通过：
   - Day 27 dispute resolution 全绿
   - Day 26 auditor trace 全绿
   - Day 25 audit chain 全绿
25. Day 29 真实主候选 PIR 接入验收已通过：
   - Go wrapper 边界验收通过
   - 真实主候选确定性验收通过
   - 固定索引 `42` 成功恢复固定真值 `4242`

### 已有脚本 / 测试
- `scripts/test_ticket_flow.sh`
  - 验证 Day 9 ticket 获取链路
- `scripts/test_day10_verifier.py`
  - 验证 Day 10 verifier 正反例链路
- `scripts/test_day11_binding.py`
  - 旧版 binding 联调脚本（当前应以最新主链语义重新审视）
- `scripts/test_day12_lifecycle.py`
  - 验证生命周期状态机
- `scripts/test_day13_blind_link.py`
  - 验证 blind-sign 全链路正反例
- `scripts/test_day17_chain.py`
  - 验证 blind ticket + admission 最小链路
- `scripts/test_day17_full_e2e.py`
  - 验证 `Client -> Admission -> Issuer -> Binding -> Verifier -> PIR Server` 主线烟雾测试
- `tests/test_crypto_core.py`
  - blind-sign / verify 核心单测
- `scripts/test_day22_redis_state.py`
  - 验证 Day 22 Redis 状态表核心语义与 Epoch TTL
- `scripts/test_day23_concurrency.py`
  - 验证 Day 23 原子核销并发语义
- `scripts/test_day24_consume_semantics.py`
  - 验证 Day 24 判定路径与票据终态绑定一致性
- `scripts/test_day25_audit_chain.py`
  - 验证 Day 25 审计账本链式 HMAC 防篡改
- `scripts/test_day26_auditor_trace.py`
  - 验证 Day 26 Auditor trace 与一致性查询
- `scripts/test_day27_dispute_resolution.py`
  - 验证 Day 27 最小争议验证闭环

---

## 七、当前最值得继续推进的方向

### 下一阶段：端到端回归脚本 / 周回归套件
目标：

- 在 Day 21 本周联调、Day 22 状态表收口、Day 23 原子核销并发验收、Day 24 判定-消费语义验收、Day 25–27 审计闭环验收、Day 28 verifier 收口回归、Day 29 真实主候选 PIR 接入验收的基础上，将核心场景沉淀为可重复执行的周联调脚本 / 回归脚本
- 避免后续在真实 PIR 后端收口或更强审计增强阶段把当前主链路打坏

建议覆盖场景：

1. 正常请求
2. 无票据请求
3. 过期票据
4. 篡改 binding 请求
5. PIR 后端失败请求
6. `PENDING / CONSUMED / FAILED` replay 请求
7. Auditor trace / 最小一致性查询
8. 审计账本完整性校验
9. 真实主候选 PIR 确定性基线（索引 `42` -> 真值 `4242`）

需要完成：

1. 整理覆盖正常请求与异常请求的最小联调矩阵
2. 验证无票据请求是否被正确业务拒绝
3. 验证过期票据是否在 verifier 前置快拒绝
4. 验证篡改 `q / b / w` 请求是否命中 binding consistency reject
5. 验证 PIR 后端失败是否稳定命中 `FAILED`
6. 验证正常请求仍可成功进入 PIR Server 并返回 `SUCCESS`
7. 验证 Auditor 侧最小追溯与一致性查询保持可用
8. 验证真实主候选 PIR 路径保持确定性通过
9. 将以上场景沉淀为一份周联调脚本 / 回归脚本

### 再下一阶段：更强审计与部署增强（后续）
目标：

- 在不破坏当前已稳定的最小审计闭环前提下，逐步增强威胁模型覆盖与部署稳健性

候选方向：

1. 审计密钥托管与轮换
2. 多进程 / 多实例下的顺序化落账
3. 外部锚定或周期性摘要封存
4. 多事件追踪模式（单 SN 多记录）
5. 更强的审计恢复与自检能力

### 再下一阶段：PIR 协议与真实后端收口（第三阶段）
目标：

- 将当前 Python stub adapter / subprocess bridge 逐步推进到正式独立 PIR 后端协议边界

需要完成：

1. 抽取 PIR 请求/响应公共模型
2. 明确 Python 控制层与 PIR 适配层的最终输入输出协议
3. 完成 `q -> PIR query` 的正式映射
4. 统一输出解析与错误返回路径
5. 收口 DB / hint 生命周期与性能优化

### 当前不应轻易改动的部分

以下内容已经通过文档、实现、联调与单测逐步固化，短期内不应轻易推翻：

- blind signature 第一版使用 RSA blind signature
- 主线仍为 `blind ticket -> admission -> binding -> verifier -> PIR -> audit`
- ticket 结构仍为 `t = (SN, sigma, EpochID)`
- ticket 被签消息编码仍为 `SN || EpochID`
- 状态机仍为 `UNUSED / PENDING / CONSUMED / FAILED`
- blind-sign 已成为唯一主线，不再保留普通签名占位
- admission 第一版采用 Interactive Hashcash PoW，不使用 VDF 代码实现
- epoch 时间窗已正式进入 Ticket 与 Verifier 验证路径
- binding 第一版生成逻辑已正式进入 RequestInstance 构造路径
- binding verify 已在 verifier 侧正式生效
- PIR 后端仍保持独立进程 / 微服务集成方向
- eBPF 仍只做轻量前置过滤
- 当前审计已形成最小闭环，但仍应避免在未评估前贸然重型化
- 项目继续优先“小修收口”，避免中途大重构
- Day 22 当前保持 `UNUSED` 为逻辑默认态，而非签发即预写 Redis
- Day 23 当前保持基于 Redis `SETNX` 的最小原子占位路线，不额外引入复杂 Lua/事务重构
- Day 24 当前保持“前置验证失败不吞票；只有成功占位到 `PENDING` 的请求才进入 PIR；PIR 结果严格绑定终态”的主路径语义
- Day 25 当前保持链式 HMAC 审计账本作为第一版 tamper-evident 方案
- Day 26 当前保持按 `SN` 单条追溯的最小 trace 语义
- Day 28 当前保持 verifier 三层拆分结构与既有外部 API 契约不漂移
- Day 29 当前保持 Python 控制层通过 subprocess / JSON bridge 驱动真实主候选 PIR，不引入进程内 FFI 硬绑定

---

## 八、当前一句话状态总结

当前项目已完成：

- **Issuer blind-sign**
- **Client ticket acquisition**
- **Admission primitive 第一版**
- **blind ticket + admission 整合**
- **epoch 时间窗接入**
- **binding 生成接入**
- **binding verify 落地**
- **Verifier ticket signature verification**
- **Redis 原子防重放与生命周期状态机**
- **Verifier -> PIR Server 网络桥接（第一阶段）**
- **blind-sign / verify 第一批核心单测**
- **Day 21 本周联调**
- **Day 22 Redis 状态表与状态查询接口收口**
- **Day 23 原子核销并发验收通过**
- **Day 24 判定路径绑定原子核销已通过验收**
- **Day 25 tamper-evident 审计日志已通过验收**
- **Day 26 Auditor 查询接口已通过验收**
- **Day 27 最小争议验证闭环已通过验收**
- **Day 28 verifier 阶段重构已最终收口**
- **Day 29 真实主候选 PIR 正式接入**

并已确认：

- Day 12 生命周期在跨服务模式下回归通过
- Day 13 blind-sign 全链路联调完成
- Day 14 第一批核心单测通过
- Day 16 admission primitive 第一版反例验收通过
- Day 17 blind ticket + admission 整合通过
- Day 18 epoch 时间窗过期拒绝通过
- Day 19 binding 生成通过
- Day 20 binding verify 通过
- Day 21 本周联调四类场景通过
- Day 22 Redis 状态表核心语义与 verifier 状态查询接口通过
- Day 23 原子核销并发验收通过
- Day 24 判定路径绑定原子核销语义验收通过
- Day 25 审计账本链式 HMAC 防篡改通过
- Day 26 Auditor trace 与最小一致性查询通过
- Day 27 最小争议验证闭环通过
- Day 28 verifier 最终重构回归通过
- Day 29 真实主候选 PIR 接入与确定性基线通过