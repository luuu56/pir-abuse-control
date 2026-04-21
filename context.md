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
- Day 31：请求实例与 PIR 输入对齐第一轮收口完成
- Day 32：主链 happy path 已可返回真实 PIR 结果
- Day 33：非法请求不进入 PIR 的隔离验证已通过
- Day 34：第一轮功能性指标已可自动化产出并对账
- Day 35：缓冲 / 修复日收口完成，PIR 响应类型与 verifier 防御性检查已稳定落地
- Day 36：eBPF 第一版职责范围固定
- Day 37：eBPF 环境搭建与最小 hello-ebpf 验证完成
- Day 38：TC 挂载的第一版轻量前置过滤已打通
- Day 39：eBPF fast path 与 verifier full path 两级架构联动已验证成立
- Day 40：来源级短时 derived block 联动已成立
- Day 41：两级前置验证漏斗效果已完成第一轮量化测试
- Day 42：两级前置验证架构文档化与重构收口完成
- Day 43：恶意客户端 replay 攻击实验已完成
- Day 44：客户端批量滥用攻击与 full path 承压测试已完成
- Day 45：恶意 verifier 状态篡改测试已完成
- Day 46：恶意服务端伪造执行记录测试已完成
- Day 47：Authenticated / Verifiable PIR 兼容性验证已完成
- Day 48：基线实验 1（无 access-control 前置保护）已完成
- Day 49：基线实验 2（仅用户态 verifier）已完成
- Day 50：完整方案实验已完成，形成 `L7 verifier -> derived block dispatch -> L4 eBPF/TC drop` 协同防御闭环

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
- Day 31 `q -> pir_index` 映射契约与 Python/Go 双向结构化协议
- Day 32 Verifier 成功分支透传结构化 PIR 结果
- Day 33 verifier 轻量 metrics 与 PIR 探针日志
- Day 34 功能性指标脚本与固定流量体检报表
- Day 35 `PIRResponse.data` 强类型收口为 `PIRResultPayload`
- Day 35 verifier 成功分支 malformed PIR response 防御性检查
- Day 36 eBPF 第一版 In-Scope / Out-of-Scope 边界固定
- Day 37 BCC + Clang/LLVM + kprobe hello-ebpf 最小链路验证
- Day 38 BCC Python + pyroute2 + TC / `eth0 ingress` 第一版落地
- Day 39 eBPF fast path 与 verifier full path 联调验收
- Day 40 verifier/Redis 派生来源级短时 block -> eBPF blocklist 联动
- Day 41 两级前置验证漏斗统计
- Day 42 `docs/architecture_defense.md` 与 docs 体系收口
- Day 43 replay attack 三阶段实验与联合防御统计
- Day 44 batch abuse 压测与 full path / abuse payload 分离验证
- Day 45 Redis 状态篡改与 Auditor/Redis 外部对账验证
- Day 46 恶意服务端伪造执行记录与账本链断裂检测
- Day 47 APIR / VPIR proof-bearing response 最小兼容透传
- Day 48 baseline 1：无 access-control 前置保护直打 PIR 入口性能基线
- Day 49 baseline 2：仅用户态 verifier 的 L7 防线性能基线
- Day 50 full solution：`L7 verifier -> derived block dispatch -> L4 eBPF/TC drop` 完整方案实验

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

当前 Day 31 已完成“请求实例与 PIR 输入对齐”的第一轮收口：

1. 当前 Python `pir_server` 已定义第一版映射规则：
   - `pir_index = SHA256(query_payload) % DB_NUM_ENTRIES`
2. 当前固定：
   - `DB_NUM_ENTRIES = 1024`
   - 且必须与 Go 侧 `NUM_ENTRIES = 1024` 严格一致
3. 当前 Python -> Go 输入 JSON 包括：
   - `request_id`
   - `query_payload`
   - `pir_input`
   - `engine_request_type`
4. 当前 Go -> Python 输出 JSON 包括：
   - `status`
   - `result`
   - `recovered_val`
   - `error_type`
   - `error_message`
   - `engine_meta`
5. 当前 Go wrapper 已采用动态可预测测试数据库：
   - `vals[i] = i * 101`
6. 当前动态映射验收已通过：
   - `query_apple`
   - `query_banana`
   - `user_12345`

当前 Day 32 已完成主链路 Happy Path 联调：

1. Verifier 不再只把 PIR 执行结果当作成功/失败布尔值处理
2. `call_pir_server()` 已返回四元组：
   - `success`
   - `payload_or_error`
   - `mapped_index`
   - `recovered_val`
3. 在 PIR 成功时：
   - `ticket_state = CONSUMED`
   - `decision = SUCCESS`
   - `reason = "PIR execution completed"`
   - `PIRResponse.data` 携带结构化 PIR 结果
4. 当前实际通过的结构化结果示例：
   - `mapped_index = 86`
   - `recovered_val = 8686`
5. 且与 Python 侧本地预测：
   - `expected_index = 86`
   - `expected_val = 8686`
   一致

当前 Day 33 已完成“非法请求不进入 PIR”的第一轮隔离验证：

1. verifier 已新增轻量级内存 metrics：
   - `total_requests`
   - `blocked_before_pir`
   - `pir_invoked`
2. 已暴露：
   - `/api/v1/verifier/metrics`
3. 当前已增加 PIR 探针日志：
   - `[PIR_START]`
   - `[PIR_END]`
4. Day 33 攻击脚本结果已确认：
   - 合法请求：成功进入 PIR 并返回真实结果
   - 篡改 binding 请求：被挡下
   - 缺失 ticket 请求：被挡下
   - replay 请求：被挡下
5. 最终对账结果为：
   - `Total Requests Fired : 4`
   - `Business Blocked     : 3`
   - `Actual PIR Invoked   : 1`

当前 Day 34 已完成第一轮功能性指标整理：

1. 使用 `scripts/test_day34_functional_metrics.py` 发射固定 10 个请求：
   - 5 个正常请求
   - 3 个 replay 攻击
   - 1 个 binding 篡改请求
   - 1 个伪造签名请求
2. 当前指标结果为：
   - `Normal Request Success Rate: 100.00% (5/5)`
   - `Replay Interception Rate: 100.00% (3/3)`
   - `Binding Interception Rate: 100.00% (1/1)`
   - `Signature Interception Rate: 100.00% (1/1)`
3. metrics 对账结果为：
   - `Total Requests Processed = 10`
   - `Expected PIR Invocations = 5`
   - `Actual PIR Engine Invoked = 5`
   - `PIR Entry Proportion = 50.00%`

当前 Day 35 已完成一轮“缓冲 / 修复日”收口：

1. `common.models.PIRResponse.data` 已从宽松类型收口为强类型 `PIRResultPayload`
2. 但该收口仅作用于 verifier 对外响应层，不改变 `pir_server` 当前桥接层 JSON 契约
3. 当前桥接层仍保持：
   - `pir_server -> verifier` 返回：`data / mapped_index / recovered_val`
   - `verifier -> client` 对外返回：`PIRResponse.data = PIRResultPayload(result_string, mapped_index, recovered_val)`
4. Day 35 明确保持 Auditor 契约不扩面：
   - `AuditRecord` 暂不加入 `mapped_index`
   - verifier 投递 auditor 的 payload 继续不带 `mapped_index`
5. verifier 成功分支已增加防御性检查：
   - 若 `success=True` 但 `mapped_index` 或 `recovered_val` 为空，则按 `malformed PIR response` 处理
   - 票据状态流转为 `PENDING -> FAILED`
   - 保持失败烧毁语义一致
6. Day 35 后已再次运行 `scripts/test_day34_functional_metrics.py`，结果未回退，说明本轮收口未破坏既有主链与功能性指标口径

当前 Day 36 已完成 eBPF 第一版职责范围固定：

1. 当前已明确 eBPF/XDP 在本原型中的定位是“前置的 L3/L4 及极轻量级 L7 早期启发式清洗层”
2. 不是业务判定层，也不是第二个 verifier
3. 第一版挂载点优先级已固定为：
   - 优先尝试 XDP
   - 若受限于环境或可见性约束，再降级评估 TC
4. 第一版 eBPF In-Scope 已固定为：
   - 仅对目标端口 TCP 流量执行前置启发式过滤
   - 有限窗口内的浅层模式检查
   - 基于 eBPF Map 的预置 denylist 快速丢包
5. 第一版 eBPF Out-of-Scope 已固定为：
   - 不做 TCP 流重组
   - 不做 HTTP/JSON 深度解析
   - 不做 RSA 盲签名验签
   - 不做 HMAC binding 校验
   - 不连接 Redis
   - 不做 replay 状态检查
   - 不做原子核销
   - 不做动态复杂限流
6. 当前工程原则已写死：
   - 如果 eBPF 无法在常数或严格受控时间内安全完成判断，则默认 `PASS` 给用户态 Verifier
   - 不允许在内核侧编写复杂补救或循环逻辑

当前 Day 37 已完成 eBPF 环境搭建与最小 hello-ebpf 验证：

1. 在 WSL2 环境中，最小 eBPF 程序已成功通过 BCC + Clang/LLVM 编译、加载并执行
2. 当前已验证通过的链路为：
   - `scripts/hello_ebpf.py`
   - 使用系统 Python 与 root 权限运行
   - attach 到 `execve` 的 kprobe
   - 通过 `bpf_trace_printk` 输出 trace
3. 当前结论是：
   - WSL2 当前环境具备运行最小 eBPF 程序的能力
   - clang/llvm + BCC + kprobe 最小链路可用
4. 当前尚未验证：
   - XDP 数据面是否可用
   - TC 数据面是否可用
   - 网络包级早期过滤是否已打通

当前 Day 38 已完成服务器版第一轮 TC 轻量前置过滤：

1. Day 38 继续严格遵守既定边界：
   - eBPF 第一版仅做轻量前置过滤
   - 不做 Redis 查询
   - 不做 blind ticket verify
   - 不做 binding verify
   - 不做原子核销
   - 不做复杂 JSON 深解析
   - 不做动态复杂限流
2. 当前实现路线已固定为：
   - BCC Python 绑定 + pyroute2 + TC
   - 挂载点：`eth0 ingress`
   - 目标流量：仅 `TCP dport=8002`
3. 第一版规则已收口为：
   - 硬丢弃条件：`payload[0:4] == "HACK"` -> `TC_ACT_SHOT`
   - 轻量观测信号：
     - `HTTP POST detected`
     - 前 96 字节窗口内观察 `"ticket"`
   - 除命中 `HACK` 指纹外，其余流量统一 `TC_ACT_OK`
4. 验收结果：
   - `HACK...` 垃圾 TCP 字节可被 TC trace 命中 `[TC DROP]`
   - 正常 HTTP POST 到 verifier 可见 `[TC OBSERVE]`
   - 正常 HTTP 流量可继续进入 verifier

当前 Day 39 已完成两级架构联动验证：

1. 已证明以下责任边界成立：
   - Case A：`HACK...` 垃圾 TCP 流量在 `eth0 ingress` 被 eBPF/TC 提前丢弃
   - Case B：候选 HTTP 流量不会被 eBPF 误杀，而是进入 verifier 后被业务拒绝
   - Case C：replay / double spend 不由 eBPF 处理，而是由 verifier 状态机以 `Ticket already CONSUMED` 拒绝
   - Case D：合法流量能够穿透 fast path + full path，最终成功进入真实 PIR 执行路径
2. 因此已证明：
   - eBPF fast path 与 verifier full path 的两级架构联动成功
   - eBPF 第一版仍严格停留在轻量前置过滤边界内
   - verifier 仍是唯一完整业务判定与 consume 承担方
3. 当前补充说明：
   - Day 39 中 verifier 曾两次出现 `Auditor report failed: All connection attempts failed`
   - 该问题不影响 Day 39 “eBPF 与 verifier 协作”验收结论

当前 Day 40 已完成来源级短时 derived block 联动：

1. 当前实现采用“来源级短时 L4 dampening”路线：
   - verifier 在命中明确 replay / double spend（当前仅 `Ticket already CONSUMED`）时
   - 基于 `client_ip` 派生一条 `BLOCK <ip> <duration>` 控制指令
   - 本机控制面将其同步到 eBPF `blocklist` map
   - eBPF 仅在 `TCP dport=8002` 时检查该 blocklist 并执行 drop
2. 当前准确语义为：
   - 基于 verifier/Redis 决策派生出的来源级短时抑制
   - 不是票据状态被同步进 eBPF
   - 不是 eBPF 现在理解 ticket 语义
3. 联调结果已证明：
   - 静态 HACK 指纹仍可被 eBPF 直接丢弃
   - 候选 HTTP 流量仍能进入 verifier，并被用户态以 `Missing Ticket in request` 拒绝
   - 第一次请求成功消费；第二次 replay 先进入 verifier，再被 Redis 状态机判定为 `CONSUMED`，随后 verifier 派生来源级短时 block
   - 同一来源后续的新合法请求仍可从 Issuer(8001) 正常获取新票，但发往 Verifier(8002) 时被 eBPF fast-path 提前丢弃
4. 因此已证明：
   - Redis / verifier 仍是业务状态 Source of Truth
   - eBPF 没有独立伪造业务决策
   - eBPF 与状态表联动当前以“来源级短时抑制”的形式成立

当前 Day 41 已完成前置验证效果测试：

1. 测试顺序已固定为：
   - 正常流量
   - 无票据流量
   - 静态恶意指纹流量
   - replay 流量
2. 原因：
   - Day 40 的 derived L4 block 会污染后续流量
   - 因此 replay 必须放在最后
3. 四类流量的实际落点已验证：
   - 正常流量：主要进入 PIR
   - 无票据流量：主要在 verifier 被拒绝
   - 静态恶意指纹流量：主要在 eBPF 前置层被拦截
   - replay 流量：首个 replay 到达 verifier 并被 Redis 状态机识别；后续 replay 大多被 eBPF derived block 提前压制
4. 当前漏斗统计结果为：
   - `Total Traffic Sent Attempts = 21`
   - `HTTP Responses Received = 12`
   - `Reached Verifier (L7) = 12`
   - `Verifier Logic Blocks = 6`
   - `Penetrated to PIR = 6`
   - `eBPF Gateway Drops (Approx) = 9`

当前 Day 42 已完成两级前置验证架构的文档化与重构收口：

1. 已新增：
   - `docs/architecture_defense.md`
2. 当前文档承载内容包括：
   - 两级前置验证总览图
   - Fast Path / Full Path 职责划分
   - Source of Truth 与 Derived Block 的主从关系
   - Day 41 漏斗效果与统计口径说明
3. 当前文档中已明确：
   - Fast Path = eBPF / TC
   - Full Path = Verifier / Redis / PIR
   - Redis 仍是唯一业务状态真相源
   - eBPF 不维护 `UNUSED / PENDING / CONSUMED / FAILED`
   - eBPF 不单独伪造业务决策
   - Derived Block 仅是 verifier 基于 `CONSUMED` replay 派生出的来源级短时 L4 dampening
4. 当前还在 `docs/sequence.md` 中补入了对 `architecture_defense.md` 的引用，使 docs 体系形成互补关系：
   - `ebpf_scope.md` 负责边界
   - `sequence.md` 负责总体时序
   - `architecture_defense.md` 负责两级前置验证分层防御留档

当前 Day 43 已完成 replay 攻击实验：

1. Day 43 已进入第 7 周“攻击实验、恶意客户端测试、兼容性验证”阶段，当前聚焦恶意客户端 replay 攻击
2. 当前核心验收标准为：
   - 单票据重复请求下只允许一次成功
   - 并发 replay 风暴下仍只允许一次成功
3. 当前脚本 `scripts/test_day43_replay_attacks.py` 已收口为三阶段：
   - Phase 1：串行 replay
   - Phase 2：20 线程并发 replay storm
   - Phase 3：联合防御战果统计
4. 当前实验结果表明：
   - 串行 replay：
     - 第 1 次合法请求成功
     - 第 2 次 replay 被 verifier 以 `Ticket already CONSUMED` 拒绝
     - 第 3 次 replay 被 eBPF derived L4 dampening 提前压制
   - 并发 replay storm：
     - 仅 1 个请求成功进入处理路径
     - 其余 19 个请求全部命中 `PENDING` 状态被拒绝
     - 未出现第二次成功
5. 因此当前最准确的解释是：
   - 串行 replay：由 `CONSUMED` 状态机 + derived L4 block 共同拦截
   - 并发 replay storm：主要由 Redis 原子锁 / `PENDING` 状态在最前沿完成拦截
   - 当前测到的是“联合防御矩阵下的 replay 抗性”，而不是仅测单一组件

当前 Day 44 已完成批量滥用攻击与 full path 承压测试：

1. Day 44 聚焦客户端批量滥用攻击与 full path 承压测试
2. 当前脚本 `scripts/test_day44_batch_abuse.py` 已收口为三阶段：
   - Phase 1：合法洪峰（Valid Ticket Storm / Full Path Stress）
   - Phase 2：密码学材料滥用（Fake Sigs & Bad Bindings）
   - Phase 3：无票据 / 缺 witness 滥用（Missing Ticket / Missing Witness Abuse）
3. 当前关键修正：
   - Phase 1 与 Phase 2 的 payload 已彻底分离
   - Phase 2 使用 fresh unused tickets 派生 abuse payload
   - 因此 Phase 2 现在真正测的是：
     - 伪签名材料拒绝
     - binding 一致性校验拒绝
   - 不再被 `Ticket already CONSUMED` 污染
4. 当前结果表明：
   - 合法 full path 流量：
     - `Reached Verifier = +100`
     - `Blocked Before PIR = +0`
     - `Penetrated to PIR = +100`
   - 密码学材料滥用：
     - `Reached Verifier = +100`
     - `Blocked Before PIR = +100`
     - `Penetrated to PIR = +0`
     - 典型拒绝原因为：
       - `Invalid Ticket Signature`
       - `Binding Consistency Check Failed`
   - 无票据 / 缺 witness 滥用：
     - `Reached Verifier = +100`
     - `Blocked Before PIR = +100`
     - `Penetrated to PIR = +0`
     - 典型拒绝原因为：
       - `Missing Ticket in request`
5. 当前最准确的 Day 44 结论是：
   - verifier 的 L7 分层前置拦截有效
   - PIR backend 只承接合法 full path 流量
   - 批量 abuse 请求未穿透到 PIR
   - 当前“fake ticket abuse”主要由 `sigma` 篡改来代表，而非覆盖所有 fake ticket 形态

当前 Day 45 已完成恶意 verifier 状态篡改测试：

1. 当前目标是验证：
   - 如果 verifier / Redis 被恶意写入虚假 `CONSUMED` 状态，系统能否被外部对账发现
2. 当前结论是：
   - 仅篡改 Redis 状态而不伴随 Auditor 账本记录时，会出现“ghost consumption”
   - 该不一致可通过：
     - `GET /api/v1/verifier/ticket_state/{sn}`
     - `GET /api/v1/auditor/trace/{sn}`
     的外部对账发现
3. 因此当前最准确表述是：
   - Day 45 证明了 Redis 状态与 Auditor 账本是两个独立证据源
   - 当 verifier 侧状态被恶意篡改时，可被 cross-check 发现
   - 这不是自动防篡改修复，而是“可检测的不一致”

当前 Day 46 已完成恶意服务端伪造执行记录测试：

1. 当前目标是验证：
   - 如果服务端试图伪造执行记录或静默改写账本，外部是否能发现
2. 当前结论是：
   - 若伪造记录未同步反映在 Redis / ticket_state / HTTP 证据中，则会形成跨证据源不一致
   - 若直接静默改写 `audit_ledger.jsonl`，则会破坏链式 HMAC 完整性
3. 因此当前最准确表述是：
   - Day 46 证明了“伪造执行记录”可通过跨证据源对账与离线账本完整性校验被发现
   - 当前系统具备最小可检测篡改能力，但不等于具备自动追责或自动恢复能力

当前 Day 47 已完成 APIR / VPIR 兼容性验证：

1. 当前目标不是把系统切换为 APIR / VPIR
2. 而是验证：
   - 当前控制层 / verifier / models 是否能最小兼容携带 proof 的 PIR response
3. 当前结论是：
   - 当前结构允许在不破坏主线的前提下透传 proof-bearing payload
   - 即：
     - `result`
     - `mapped_index`
     - `recovered_val`
     - `proof`
     可作为扩展字段兼容承载
4. 因此当前最准确表述是：
   - Day 47 完成的是“兼容性验证”
   - 不是“已正式实现可验证 PIR”

当前 Day 48 已完成基线实验 1：

1. 当前实验定义为：
   - 无 access-control 前置保护
   - 直接打 PIR 服务入口
2. 当前结果可作为：
   - “无保护”性能与资源承压基线
3. 当前最准确表述是：
   - Day 48 提供的是对照组 baseline 1
   - 用于和后续“仅 verifier”及“完整方案”实验横向比较

当前 Day 49 已完成基线实验 2：

1. 当前实验定义为：
   - 仅用户态 verifier 的 L7 防线
   - 不启用 eBPF fast path
2. 当前结果可作为：
   - “只有 full path”时的性能 / 拦截 / 资源承压基线
3. 当前最准确表述是：
   - Day 49 提供的是对照组 baseline 2
   - 用于与 Day 48 和 Day 50 横向比较

当前 Day 50 已完成完整方案实验：

1. 当前实验定义为完整方案：
   - `L7 verifier -> derived block dispatch -> L4 eBPF/TC drop`
2. 当前结果说明：
   - replay flood 下，首次请求在 full path 被消费
   - 随后部分流量由 verifier / Redis 状态机拦截
   - 再后续一部分流量可被 derived block 驱动的 L4 eBPF/TC 提前压制
3. 因此当前最准确表述是：
   - Day 50 证明了完整方案下的协同防御闭环已经成立
   - 项目已具备：
     - baseline 1：无保护
     - baseline 2：仅 verifier
     - full solution：verifier + derived block + eBPF/TC
     三组可对比实验基础

因此，当前项目已经从“本地 stub 语义的 verifier”进入“blind-sign 主链稳定、admission 第一版落地并已并入签票主链、epoch 时间窗已正式接入、binding 生成与 verifier 侧 binding verify 均已落地、主链核心场景已完成本周联调区分验证、Redis 状态表已完成 Day 22 收口、Day 23 原子核销并发验收通过、Day 24 判定与消费语义一致性已落地、Day 25–27 审计留痕/追溯/争议闭环已形成、Day 28 verifier 内部结构已稳定收口、Day 29 Python 控制层已可实际驱动真实主候选 SimplePIR 计算、Day 31–35 已完成请求到真实 PIR 结果的协议对齐、主链 happy path、非法请求 PIR 隔离与第一轮功能性指标闭环、Day 36–42 已完成 eBPF 第一版边界固定、最小环境验证、TC 轻量前置过滤、derived block 联动、漏斗量化与架构留档、Day 43–50 已完成 replay 攻击、batch abuse、恶意状态篡改、伪造执行记录、兼容性验证以及 baseline / full-solution 实验闭环”的阶段。

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

### 16. q -> PIR 输入映射契约（Day 31）
当前 Python `pir_server` 已定义第一版映射规则：

- `pir_index = SHA256(query_payload) % DB_NUM_ENTRIES`

当前固定：

- `DB_NUM_ENTRIES = 1024`

并要求与 Go 侧：

- `NUM_ENTRIES = 1024`

保持严格一致。

当前 Python -> Go 输入协议包括：

- `request_id`
- `query_payload`
- `pir_input`
- `engine_request_type`

其中：

- `pir_input` 当前为字符串化后的 `pir_index`

当前 Go -> Python 输出协议包括：

- `status`
- `result`
- `recovered_val`
- `error_type`
- `error_message`
- `engine_meta`

其中：

- `recovered_val` 已作为结构化字段返回，不再只藏在结果字符串中

### 17. 真实 PIR 结构化结果契约（Day 32 / Day 35）
当前 verifier 不再只把 PIR 执行结果视为成功/失败布尔值，而是支持透传结构化 PIR 数据。

当前 `call_pir_server()` 返回：

- `success`
- `payload_or_error`
- `mapped_index`
- `recovered_val`

当前 verifier 成功返回时：

- `ticket_state = CONSUMED`
- `decision = SUCCESS`
- `reason = "PIR execution completed"`
- `PIRResponse.data = PIRResultPayload(result_string, mapped_index, recovered_val)`

Day 35 进一步明确：

- `common.models.PIRResponse.data` 已从宽松类型收口为强类型 `PIRResultPayload`
- 该收口仅作用于 verifier 对外响应层
- 不改变 `pir_server` 当前桥接层 JSON 契约
- 若 `success=True` 但 `mapped_index` 或 `recovered_val` 为空，则按 `malformed PIR response` 处理，并流转为 `PENDING -> FAILED`

### 18. 非法请求 PIR 前隔离契约（Day 33 / Day 34）
当前 verifier 已新增轻量级内存 metrics：

- `total_requests`
- `blocked_before_pir`
- `pir_invoked`

并暴露：

- `/api/v1/verifier/metrics`

当前口径如下：

- `total_requests`：成功进入 verifier 业务执行函数的请求数
- `blocked_before_pir`：在进入 `call_pir_server()` 前被挡下的请求数
- `pir_invoked`：真正开始调用底层 PIR 的请求数

当前 verifier 已在调用真实 PIR 前后增加探针日志：

- `[PIR_START]`
- `[PIR_END]`

Day 34 当前指标口径说明：

- `pir_invoked` 表示已穿过 verifier 前置验证并真正开始调用底层 PIR 的请求数
- `PIR Entry Proportion` 表示总请求中实际进入 PIR 的比例

### 19. eBPF 第一版职责边界契约（Day 36）
当前已明确：

- eBPF/XDP 在本原型中的定位是“前置的 L3/L4 及极轻量级 L7 早期启发式清洗层”
- 不是业务判定层，也不是第二个 verifier

第一版挂载点优先级固定为：

- 优先尝试 XDP
- 若受限于环境或数据面可见性/可解析性约束，再降级评估 TC

第一版 eBPF In-Scope：

- 仅对目标端口 TCP 流量执行前置启发式过滤
- 有限窗口内的浅层模式检查
- 基于 eBPF Map 的预置 denylist 快速丢包

第一版 eBPF Out-of-Scope：

- 不做 TCP 流重组
- 不做 HTTP/JSON 深度解析
- 不做 RSA 盲签名验签
- 不做 HMAC binding 校验
- 不连接 Redis
- 不做 replay 状态检查
- 不做原子核销
- 不做动态复杂限流

工程原则：

- 若 eBPF 无法在常数或严格受控时间内安全完成判断，则默认 `PASS` 给用户态 Verifier
- 不允许在内核侧编写复杂补救或循环逻辑

### 20. eBPF 第一版实现与联动契约（Day 37–41）
当前 Day 37 已验证：

- WSL2 环境可运行最小 eBPF 程序
- BCC + Clang/LLVM + kprobe 最小链路可用

当前 Day 38 服务器版实现路线固定为：

- BCC Python 绑定 + pyroute2 + TC
- 挂载点：`eth0 ingress`
- 目标流量：仅 `TCP dport=8002`

第一版规则收口为：

- 硬丢弃条件：`payload[0:4] == "HACK"` -> `TC_ACT_SHOT`
- 轻量观测信号：
  - `HTTP POST detected`
  - 前 96 字节窗口内观察 `"ticket"`
- 除命中 `HACK` 指纹外，其余统一 `TC_ACT_OK`

Day 39 已证明两级责任边界：

- eBPF fast path 负责最明显非法流量早丢弃
- verifier full path 负责完整验证、状态机推进与 PIR 调用

Day 40 已形成来源级短时 derived block 契约：

- verifier 在命中明确 replay / double spend（当前仅 `Ticket already CONSUMED`）时
- 基于 `client_ip` 派生短时 block
- 控制面同步到 eBPF `blocklist` map
- eBPF 仅在 `TCP dport=8002` 时检查并执行 drop

该机制准确语义为：

- 基于 verifier/Redis 决策派生出的来源级短时抑制
- 不是票据状态被同步进 eBPF
- 不是 eBPF 现在理解 ticket 语义

Day 41 已形成漏斗统计口径：

- `Reached Verifier (L7)` 来自服务端 `/metrics`，是 authoritative count
- `HTTP Responses Received` 是客户端观测值
- `eBPF Gateway Drops (Approx)` 采用实验室近似：
  - `Total Sent Attempts - Reached Verifier`

### 21. 两级前置验证架构留档契约（Day 42）
当前已新增：

- `docs/architecture_defense.md`

当前文档体系分工已明确：

- `ebpf_scope.md` 负责边界
- `sequence.md` 负责总体时序
- `architecture_defense.md` 负责两级前置验证分层防御留档

当前明确：

- Fast Path = eBPF / TC
- Full Path = Verifier / Redis / PIR
- Redis 仍是唯一业务状态真相源
- eBPF 不维护 `UNUSED / PENDING / CONSUMED / FAILED`
- eBPF 不单独伪造业务决策
- Derived Block 仅是 verifier 基于 `CONSUMED` replay 派生出的来源级短时 L4 dampening

### 22. replay 攻击实验契约（Day 43）
当前 Day 43 聚焦恶意客户端 replay 攻击。

核心验收标准：

- 单票据重复请求下只允许一次成功
- 并发 replay 风暴下仍只允许一次成功

当前脚本 `scripts/test_day43_replay_attacks.py` 收口为三阶段：

1. Phase 1：串行 replay
2. Phase 2：20 线程并发 replay storm
3. Phase 3：联合防御战果统计

当前最准确解释为：

- 串行 replay：由 `CONSUMED` 状态机 + derived L4 block 共同拦截
- 并发 replay storm：主要由 Redis 原子锁 / `PENDING` 状态在最前沿完成拦截
- 当前测到的是“联合防御矩阵下的 replay 抗性”，而不是仅测单一组件

### 23. 批量 abuse 与 full path 承压契约（Day 44）
当前 Day 44 聚焦客户端批量滥用攻击与 full path 承压测试。

当前脚本 `scripts/test_day44_batch_abuse.py` 收口为三阶段：

1. Phase 1：合法洪峰（Valid Ticket Storm / Full Path Stress）
2. Phase 2：密码学材料滥用（Fake Sigs & Bad Bindings）
3. Phase 3：无票据 / 缺 witness 滥用（Missing Ticket / Missing Witness Abuse）

当前关键约束：

- Phase 1 与 Phase 2 的 payload 已彻底分离
- Phase 2 使用 fresh unused tickets 派生 abuse payload
- 因此当前真正测到的是：
  - 伪签名材料拒绝
  - binding 一致性校验拒绝
- 不再被 `Ticket already CONSUMED` 污染

当前最准确结论为：

- verifier 的 L7 分层前置拦截有效
- PIR backend 只承接合法 full path 流量
- 批量 abuse 请求未穿透到 PIR
- 当前 “fake ticket abuse” 主要由 `sigma` 篡改来代表，而非覆盖所有 fake ticket 形态

### 24. 恶意状态篡改 / 伪造执行记录可检测性契约（Day 45 / Day 46）
当前 Day 45–46 已证明：

- Redis 状态与 Auditor 账本是两个独立证据源
- 若仅篡改 verifier / Redis 状态而不伴随账本记录，会形成可检测不一致
- 若伪造执行记录未同步反映在其他证据源中，也会形成跨证据源不一致
- 若直接静默改写 `audit_ledger.jsonl`，会破坏链式 HMAC 完整性

当前最准确表述是：

- 当前系统具备“最小可检测篡改能力”
- 但不等于具备自动修复、自动追责或强对抗下的不可抵赖性保证

### 25. APIR / VPIR proof-bearing response 兼容性契约（Day 47）
当前 Day 47 完成的是兼容性验证，不是正式实现可验证 PIR。

当前已证明：

- 当前控制层 / verifier / models 可在不破坏主线的前提下最小兼容透传 proof-bearing payload

当前最小兼容承载字段包括：

- `result`
- `mapped_index`
- `recovered_val`
- `proof`

### 26. 基线实验与完整方案实验契约（Day 48 / Day 49 / Day 50）
当前三组实验分工已明确：

#### Baseline 1（Day 48）
- 无 access-control 前置保护
- 直接打 PIR 服务入口

#### Baseline 2（Day 49）
- 仅用户态 verifier 的 L7 防线
- 不启用 eBPF fast path

#### Full Solution（Day 50）
- `L7 verifier -> derived block dispatch -> L4 eBPF/TC drop`

当前最准确表述是：

- 项目已经具备：
  - 无保护 baseline
  - 仅 verifier baseline
  - 完整方案 full solution
  三组可横向比较的实验基础

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
- 在成功分支对结构化 PIR 返回执行防御性完整性检查

当前额外已具备：

- `GET /api/v1/verifier/ticket_state/{sn}`：
  - 用于只读查询当前票据逻辑状态
  - 要求 `sn` 为 64-char hex
  - Redis miss 返回 `UNUSED`
- `/api/v1/verifier/metrics`：
  - 用于单进程调试与 Day 33 / Day 34 / Day 41 / Day 44 / Day 50 验收
  - 服务重启后计数清零

当前拒绝语义已明确：

- `Missing Ticket in request`：请求缺失 ticket 时业务拒绝
- `PENDING`：表示 in-flight / 并发 replay
- `CONSUMED`：表示 double spend / replay after success
- `FAILED`：表示 burned ticket / replay after execution failure
- `Ticket epoch ... has expired`：epoch 失效时业务拒绝
- `Missing Request Witness`：缺失 witness 时拒绝
- `Missing Binding Tag`：缺失 binding_tag 时拒绝
- `Binding Consistency Check Failed`：`q / b / w` 任一被篡改时拒绝
- `Invalid Ticket Signature`：伪签名材料业务拒绝
- `Invalid Binding Material`：binding 材料异常时业务拒绝
- `malformed PIR response`：PIR 成功分支结构化字段缺失时按失败烧毁处理
- 其他前置验证失败：请求被拒绝，但票据状态保持 `UNUSED`

当前审计语义：

- Verifier 已完成异步审计投递分层
- Auditor 已具备落账、最小追溯与最小一致性核查能力
- 当前已达到原型阶段“可留痕、可最小追溯、可最小对账、可争议解释”的水平
- 当前明确保持 Auditor 契约不扩面：
  - `AuditRecord` 暂不加入 `mapped_index`

当前 fast path / full path 语义：

- eBPF / TC 仅负责明显非法垃圾流量早丢弃与来源级短时抑制
- verifier 仍是唯一完整业务判定、状态机推进、PIR 放行与终态收敛承担方

当前 blind-sign 语义：

- blind-sign 已成为唯一主线
- 不再保留普通签名占位路径
- 核心 blind-sign / verify 契约已开始由 `pytest` 单测稳定回归

当前仍未完全做完：

- Auditor 更强威胁模型下的密钥托管与外部锚定
- 审计多事件追踪模式
- `q -> PIR query` 的正式映射进一步收口
- Python 与独立 PIR 后端之间的最终输入输出协议
- 输出解析与错误返回路径标准化
- DB / hint 生命周期与性能优化
- XDP / TC 取舍在真实数据面条件下的进一步定型
- Day 44 之外其他 fake ticket 形态覆盖仍待扩展
- Day 45 / 46 目前仍是“可检测篡改”，不是“自动恢复篡改”

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
- `query_payload`：当前已进入 binding 生成与 verifier 侧重算校验，并参与 `q -> pir_index` 映射
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

### PIRResultPayload
当前 Day 35 已明确对外结构化响应载荷：

- `result_string`
- `mapped_index`
- `recovered_val`

说明：

- 仅用于 verifier -> client 对外响应层
- 不要求 auditor 当前同步扩面

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
26. Day 31 动态映射验收已通过：
   - `query_apple`
   - `query_banana`
   - `user_12345`
27. Day 32 主链 happy path 已通过：
   - verifier 成功返回结构化 PIR 结果
   - `mapped_index` 与 `recovered_val` 与本地预测一致
28. Day 33 非法请求 PIR 前隔离验收已通过：
   - `Total Requests Fired : 4`
   - `Business Blocked     : 3`
   - `Actual PIR Invoked   : 1`
29. Day 34 功能性指标脚本已通过：
   - 正常成功率 `100%`
   - replay 拦截率 `100%`
   - binding 拦截率 `100%`
   - signature 伪造拦截率 `100%`
   - `PIR Entry Proportion = 50%`
30. Day 35 缓冲 / 修复日收口已通过：
   - `PIRResultPayload` 强类型收口完成
   - malformed PIR response 防御性检查已生效
   - `scripts/test_day34_functional_metrics.py` 结果未回退
31. Day 37 最小 eBPF hello 链路已通过：
   - BCC + Clang/LLVM + kprobe + trace 输出可用
32. Day 38 TC 轻量前置过滤验收已通过：
   - `HACK...` 垃圾 TCP 被丢弃
   - 正常 HTTP POST 可穿过 TC 进入 verifier
33. Day 39 两级架构联动验收已通过：
   - eBPF fast path 与 verifier full path 分工成立
34. Day 40 derived block 联动验收已通过：
   - 来源级短时抑制生效，且不干扰 8001 取票流量
35. Day 41 漏斗效果测试已通过：
   - `Total Traffic Sent Attempts = 21`
   - `Reached Verifier (L7) = 12`
   - `Penetrated to PIR = 6`
   - `eBPF Gateway Drops (Approx) = 9`
36. Day 42 架构留档已完成：
   - `docs/architecture_defense.md` 已新增
   - docs 体系互补关系已明确
37. Day 43 replay 攻击实验已通过：
   - 串行 replay 下仅首次成功
   - 并发 20 线程 replay storm 下仅 1 次成功
   - 其余 19 次命中 `PENDING`
38. Day 44 batch abuse / full path 承压测试已通过：
   - 合法 full path 100 条全部进入 PIR
   - 密码学材料滥用 100 条全部在 verifier 前被阻断
   - 无票据 / 缺 witness 滥用 100 条全部在 verifier 前被阻断
39. Day 45 恶意 verifier 状态篡改测试已通过：
   - ghost consumption 可被 Redis / Auditor 外部对账发现
40. Day 46 恶意服务端伪造执行记录测试已通过：
   - 跨证据源不一致与离线账本链断裂均可被发现
41. Day 47 APIR / VPIR 兼容性验证已通过：
   - proof-bearing response 可最小兼容透传
42. Day 48 baseline 1 已完成：
   - 无 access-control 前置保护直打 PIR 入口性能基线已获得
43. Day 49 baseline 2 已完成：
   - 仅用户态 verifier 的 L7 防线性能基线已获得
44. Day 50 full solution 实验已完成：
   - `L7 verifier -> derived block dispatch -> L4 eBPF/TC drop` 协同防御闭环已验证成立

### 已有脚本 / 测试
- `scripts/test_ticket_flow.sh`
- `scripts/test_day10_verifier.py`
- `scripts/test_day11_binding.py`
- `scripts/test_day12_lifecycle.py`
- `scripts/test_day13_blind_link.py`
- `scripts/test_day17_chain.py`
- `scripts/test_day17_full_e2e.py`
- `tests/test_crypto_core.py`
- `scripts/test_day22_redis_state.py`
- `scripts/test_day23_concurrency.py`
- `scripts/test_day24_consume_semantics.py`
- `scripts/test_day25_audit_chain.py`
- `scripts/test_day26_auditor_trace.py`
- `scripts/test_day27_dispute_resolution.py`
- `scripts/test_day31_dynamic_mapping.py`
- `scripts/test_day32_full_pipeline.py`
- `scripts/test_day33_abuse_prevention.py`
- `scripts/test_day34_functional_metrics.py`
- `scripts/hello_ebpf.py`
- `scripts/test_day43_replay_attacks.py`
- `scripts/test_day44_batch_abuse.py`
- Day 45 / 46 / 47 / 48 / 49 / 50 当前实验脚本与命令流
  - 当前已形成实验闭环，但文件名与执行编排仍可继续收口

---

## 七、当前最值得继续推进的方向

### 下一阶段：周回归脚本 / 实验编排统一收口
目标：

- 在 Day 44–50 已完成攻击实验、基线实验、完整方案实验的基础上
- 将当前分散脚本收口成可重复执行的周回归 / 实验编排资产

建议优先收口：

1. baseline 1 / baseline 2 / full solution 三组实验统一编排
2. replay attack / batch abuse / fake sig / missing ticket / missing witness 统一编排
3. Auditor trace / ledger verify / state cross-check 统一编排
4. eBPF fast path + verifier full path + derived block 漏斗对账统一编排

### 再下一阶段：PIR 协议与真实后端最终收口
目标：

- 继续推进当前真实主候选 PIR，从“已可驱动”推进到“协议稳定、生命周期清晰、结果处理统一”

需要完成：

1. 抽取 PIR 请求/响应公共模型
2. 明确 Python 控制层与 PIR 适配层的最终输入输出协议
3. 完成 `q -> PIR query` 的正式映射继续收口
4. 统一输出解析与错误返回路径
5. 收口 DB / hint 生命周期与性能优化

### 再下一阶段：eBPF 第一版工程化收口
目标：

- 在不突破 Day 36 已固定边界的前提下，把当前已验证成立的 eBPF fast path 做成更稳定的工程资产

需要完成：

1. 继续验证 XDP / TC 在真实环境中的可用性取舍
2. 收口 Day 38–41 的服务器联调脚本
3. 固化 eBPF blocklist 控制面接口与生命周期
4. 明确 derived block 的时间窗、清理机制与观测口径
5. 保持 eBPF 永远不越界到密码学验证、Redis 查询与业务状态机承担方角色

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
- eBPF 第一版仅做轻量前置过滤，不做业务判定，不做第二个 verifier
- 当前审计已形成最小闭环，但仍应避免在未评估前贸然重型化
- 项目继续优先“小修收口”，避免中途大重构
- Day 22 当前保持 `UNUSED` 为逻辑默认态，而非签发即预写 Redis
- Day 23 当前保持基于 Redis `SETNX` 的最小原子占位路线，不额外引入复杂 Lua/事务重构
- Day 24 当前保持“前置验证失败不吞票；只有成功占位到 `PENDING` 的请求才进入 PIR；PIR 结果严格绑定终态”的主路径语义
- Day 25 当前保持链式 HMAC 审计账本作为第一版 tamper-evident 方案
- Day 26 当前保持按 `SN` 单条追溯的最小 trace 语义
- Day 28 当前保持 verifier 三层拆分结构与既有外部 API 契约不漂移
- Day 29 当前保持 Python 控制层通过 subprocess / JSON bridge 驱动真实主候选 PIR，不引入进程内 FFI 硬绑定
- Day 31 当前保持 `pir_index = SHA256(q) % 1024` 作为第一版映射契约
- Day 35 当前保持 `PIRResponse.data` 强类型收口，但不扩面 Auditor 契约
- Day 36–42 当前保持 Fast Path / Full Path 两级分工：Redis / verifier 仍是唯一业务状态真相源，eBPF 仅承担明显非法流量前置过滤与 verifier 派生的来源级短时抑制
- Day 43 当前测到的是“联合防御矩阵下的 replay 抗性”，不错误归因给单一组件
- Day 44 当前 “fake ticket abuse” 主要由 `sigma` 篡改来代表，不宣称已覆盖所有 fake ticket 形态
- Day 45 / 46 当前系统提供的是“可检测的不一致 / 篡改”，不是“自动恢复”或“强不可抵赖”
- Day 47 当前完成的是 APIR / VPIR proof-bearing response 的兼容性验证，不是正式实现可验证 PIR
- Day 48 / 49 / 50 当前已形成三组可横向比较实验：无保护、仅 verifier、完整方案

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
- **Day 31 请求实例与 PIR 输入对齐第一轮收口**
- **Day 32 主链 happy path 已返回真实 PIR 结果**
- **Day 33 非法请求 PIR 前隔离已通过验收**
- **Day 34 第一轮功能性指标已可对账**
- **Day 35 缓冲 / 修复日收口完成**
- **Day 36 eBPF 第一版职责边界已固定**
- **Day 37 最小 eBPF hello 链路已验证**
- **Day 38 TC 轻量前置过滤已打通**
- **Day 39 eBPF fast path 与 verifier full path 联动已验证**
- **Day 40 derived block 联动已成立**
- **Day 41 两级前置验证漏斗效果已完成量化测试**
- **Day 42 两级前置验证架构文档化已完成**
- **Day 43 replay 攻击实验已完成**
- **Day 44 batch abuse / full path 承压测试已完成**
- **Day 45 恶意 verifier 状态篡改测试已完成**
- **Day 46 恶意服务端伪造执行记录测试已完成**
- **Day 47 Authenticated / Verifiable PIR 兼容性验证已完成**
- **Day 48 基线实验 1 已完成**
- **Day 49 基线实验 2 已完成**
- **Day 50 完整方案实验已完成**

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
- Day 31 动态映射协议通过
- Day 32 主链 happy path 返回真实 PIR 结果通过
- Day 33 非法请求 PIR 前隔离通过
- Day 34 功能性指标与 metrics 对账通过
- Day 35 缓冲 / 修复日收口未破坏既有主链与指标口径
- Day 37 eBPF 最小环境验证通过
- Day 38 TC 轻量前置过滤通过
- Day 39 两级架构联动通过
- Day 40 verifier 派生的来源级短时抑制通过
- Day 41 漏斗统计通过
- Day 42 分层防御文档化完成
- Day 43 replay 抗性实验通过
- Day 44 batch abuse / full path 承压测试通过
- Day 45 ghost consumption 可检测
- Day 46 伪造执行记录可检测
- Day 47 proof-bearing response 最小兼容透传通过
- Day 48 / 49 / 50 三组基线 / 完整方案实验基础已形成