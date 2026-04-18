# Dev Log

## 2026-04-17

### 完成
- 项目迁移到 WSL Linux 文件系统
- 5 个服务统一 bootstrap
- `common/config.py` 与 `common/logging_utils.py` 完成
- Day 6 文档基本定稿：
  - `docs/stack.md`
  - `docs/blind_signature_choice.md`
  - `docs/pir_backend_choice.md`

### 当前状态
- 所有服务可通过模块方式启动
- 统一 YAML 配置与 logging 已接通

### 已验证通过
- issuer / verifier / client / pir_server / auditor 均可正常启动
- PyCharm 已连接 WSL 项目与对应解释器

### 遇到的问题
- 直接运行脚本路径会触发 `common` 包导入问题
- 已改为 `python -m services.xxx.main` 方式运行

### 下一步
- 完成 `docs/object_model.md`
- 完成 `docs/api.md`
- 完成 `docs/sequence.md`

---

## Day 8：Issuer 签发核心 API 打通

**日期**：2026-04-17

### 完成内容
1. **密码学基座**
   - 在 `services/issuer/crypto.py` 中实现 `IssuerCryptoManager`
   - 基于 `pycryptodome` 落地 Textbook RSA 模幂运算，作为 blind-sign 核心

2. **API 骨架**
   - 使用 FastAPI 搭建：
     - `/api/v1/issuer/challenge`
     - `/api/v1/issuer/issue`

3. **数据清洗与约束**
   - 明确公钥与签名输出格式
   - 增加对输入 `blinded_message` 的容错解析与边界检查

### 关键决策 / 记录
- 当前阶段 Issuer 每次启动都会重新生成 RSA 密钥，仅供联调用
- 历史票据在 Issuer 重启后会失效
- Issuer 端当前只做边界检查
- 盲因子 `r` 的可逆性由 Client 侧负责保证

### 结论
- Day 8 的 blind-sign API 主链路已打通
- Issuer 已具备向 Client 提供公钥与 blind-sign 能力

---

## Day 9：Client 盲签请求与去盲链路闭环

**日期**：2026-04-17

### 完成内容
1. **密码学健壮性**
   - 在 `services/client/crypto.py` 中增加输入校验
   - 增加 `m < n` 边界检查
   - 完成盲因子生成、blind、unblind 逻辑

2. **主流程打通**
   - 在 `services/client/main.py` 中串联：
     - 请求 challenge / public key
     - 生成 `SN`
     - 编码 `SN || EpochID`
     - blind -> issue -> unblind
     - 组装 `Ticket(sn, sigma, epoch_id)`

3. **本地自验签**
   - 成功实现并验证：
     - `pow(s, e, n) == m`

4. **工程修复**
   - 修正 `pad_len` 获取逻辑，消除 `0x` 前缀干扰
   - 将 `ISSUER_URL` 接入 `base.yaml` 配置系统
   - 增加 HTTP 请求超时控制

### 关键记录
- 通过本地自验签确认：
  - `SN || EpochID` 的拼接方式在 blind-sign 流程下工作正常
- 当前 Ticket 语义已经稳定为：
  - `t = (SN, sigma, EpochID)`

### 结论
- Day 9 的 ticket acquisition 主链路已完成
- Client 可稳定生成合法 Ticket
- 下一步进入 Verifier 侧的公钥验签实现

---

## Day 10：Verifier RSA Signature Verification Completed

**日期**：2026-04-17

### 完成内容
1. **统一编码契约**
   - 新增 `common/crypto_utils.py`
   - 统一 Ticket 消息编码规则：
     - `m = SN(32 bytes) || EpochID(4 bytes big-endian)`

2. **Verifier 验签能力**
   - 完成 `services/verifier/crypto.py`
   - 完成 `services/verifier/main.py`
   - Verifier 启动时从 Issuer 拉取并缓存公钥

3. **执行入口**
   - `/api/v1/verifier/execute` 已可对 Ticket 做 RSA 验签
   - 当前版本仍为 Day 10 stub：
     - 仅完成签名验证
     - 尚未接入 Binding / Redis / PIR

### 联调结果
- 正例：合法 Ticket 返回 `SUCCESS`
- 反例：篡改 `SN` 返回 `REJECTED`
- 反例：篡改 `sigma` 返回 `REJECTED`

### 关键记录
- Client / Verifier 已复用统一消息编码逻辑，避免编码漂移
- `sigma` 当前采用：
  - **定长模数字节串** 的 Base64 编码
- Verifier 可正确将 `sigma` 还原为整数并完成：
  - `pow(s, e, n) == m`

### 结论
- Day 10 的票据验签主链路已完成
- Client / Verifier 之间的编码契约已对齐
- 下一步进入 Day 11：Binding Tag 校验

---

## PIR Engine 环境验证完成

**日期**：2026-04-17

### 背景
为避免污染当前 Python 控制面代码，在项目根目录下新增独立目录：

- `pir_engine/`

用于放置真实 PIR 引擎实现，并保持与 `services/`、`common/`、`docs/` 分离。

当前目录结构为：

- `~/pir-abuse-control/pir_engine/simplepir`

### 完成内容
1. 在 WSL2 环境中安装 Go
2. 在 `~/pir-abuse-control/pir_engine/` 下克隆 `SimplePIR` 官方仓库
3. 成功进入：
   - `pir_engine/simplepir/pir`
4. 成功运行官方带宽测试命令：

```bash
LOG_N=14 D=8 go test -v -run=BW
```
# 运行结果

以下测试均已通过：

- TestSimplePirBW -> PASS
- TestDoublePirBW -> PASS

## 关键输出记录：

**SimplePIR**
- db size = 2^14
- Offline download: 512 KB
- Online upload: 0 KB
- Online download: 0 KB

**DoublePIR**
- db size = 2^16
- Offline download: 16384 KB
- Online upload: 256 KB
- Online download: 32 KB

## 当前结论

- WSL2 中的 Go 环境可用
- SimplePIR 官方代码可在本机成功编译并运行
- 当前项目已经具备继续做“独立 PIR 服务封装 / 微服务集成”的基础条件

## 工程判断

当前阶段不应将 Go 代码直接混入 Python 控制面目录。应继续保持：

- Python 控制面：
  - `services/`
  - `common/`
  - `docs/`
- 真实 PIR 引擎实验区：
  - `pir_engine/simplepir`
## Day 11：票据绑定机制 (Binding Mechanism) 落地
**日期**：[填写今日日期]

**完成内容**：
1. **单一事实来源扩展**：在 `common/crypto_utils.py` 实现了 `derive_sk_t`、`compute_query_commitment`、`serialize_witness` 和 `compute_binding_tag`，严格约束了规范化的 JSON 序列化和 Base64 定长语义。
2. **Client 绑定逻辑**：在 `main.py` 中实现了 `create_bound_request`，客户端现可自主组装携带合法 HMAC Binding Tag 的 `RequestInstance`。
3. **Verifier 验绑逻辑**：在 `/execute` 接口中加入了严格的绑定一致性校验。
4. **回归测试闭环**：扩充了 `test_day11_binding.py`，成功验证了合法绑定能顺利放行，且对载荷 (Payload)、上下文 (Witness) 或标签 (Tag) 的任何单比特篡改都会被精准拦截 (`REJECTED`)。

**关键记录**：
* Witness 的 JSON 序列化采用了排序 key 和去空格的紧凑格式 (`sort_keys=True, separators=(',', ':')`)，确保跨语言环境下的哈希一致性。
* 明确了 `sigma_bytes` 的左补零定长约束，防止前导零截断导致 `sk_t` 派生分裂。
## 下一步

1. 阅读 `simplepir/pir` 的最小调用入口
2. 确认数据库初始化、查询生成、响应返回的最小 API
3. 设计后续 Python -> PIR Engine 的独立进程 / 微服务集成边界
4. 先做最小可调用 stub，再考虑接入 verifier
## Day 12：Redis 防重放与票据生命周期流转完成

**日期**：2026-04-17

### 完成内容
1. **Redis 状态机接入**
   - 在 Verifier 侧接入 Redis 状态存储
   - 新增 `services/verifier/state_manager.py`
   - 明确票据状态机：
     - `UNUSED`
     - `PENDING`
     - `CONSUMED`
     - `FAILED`

2. **原子防重放与状态流转**
   - 实现票据序列号 `SN` 的原子占用逻辑
   - 支持状态流转：
     - `UNUSED -> PENDING`
     - `PENDING -> CONSUMED`
     - `PENDING -> FAILED`
   - 明确拒绝语义：
     - 命中 `PENDING`：表示 in-flight / 并发重放
     - 命中 `CONSUMED`：表示已消费 replay / double spend
     - 命中 `FAILED`：表示失败烧毁票据不可重用
   - 前置验证失败不推进票据状态，不误吞票

3. **生命周期联调脚本**
   - 完成 `scripts/test_day12_lifecycle.py`
   - 测试脚本已统一接入配置读取：
     - Verifier URL 从 YAML 配置加载
     - timeout 从 YAML 配置加载
   - 并发测试结果改为带标签输出，便于定位 winner / loser

### 联调结果
已通过以下 4 条关键生命周期验收：

1. **PENDING 分支（并发冲突）**
   - 同一票据并发提交两个请求
   - 仅一个请求成功进入处理路径
   - 另一个请求因命中 `PENDING` 被拒绝

2. **FAILED 分支（异常烧毁）**
   - 请求触发 PIR 执行失败
   - 票据状态转为 `FAILED`
   - 后续重放同票据被直接拒绝，并返回 `Ticket already FAILED`

3. **CONSUMED 分支（正常消费）**
   - 合法请求执行成功
   - 票据状态转为 `CONSUMED`
   - 后续 replay 被拒绝

4. **边界分支（验证失败不吞票）**
   - 篡改 `binding_tag` 的请求被拒绝
   - 票据状态保持 `UNUSED`
   - 随后使用原始合法请求仍可成功消费该票据

### 关键记录
- Day 12 已不再是 Day 10 的“仅验签 stub”语义，而是开始具备真实消费语义：
  - 先做签名 / binding 等前置校验
  - 通过后再原子推进到 `PENDING`
  - 后续根据 PIR 执行结果转 `CONSUMED` 或 `FAILED`
- 当前实现已与既定主线保持一致：
  - `blind ticket -> admission -> binding -> verifier -> PIR -> audit`
- 当前阶段仍保持：
  - blind signature 第一版采用 RSA blind signature
  - PIR 后端采用独立进程 / 微服务集成方向
  - eBPF 第一版仅做轻量前置过滤，不承担复杂状态逻辑

### 结论
- Day 12 的 Redis 原子防重放与生命周期状态机已完成
- Day 12 生命周期联调脚本已通过 4 条关键分支验收
- 当前下一步应进入：
  1. Verifier -> Auditor 写入时机定义
  2. PIR Server stub / 微服务调用打通
  3. 将当前 PIR stub success 替换为真实 PIR 结果绑定

## Day 13+：Verifier -> PIR Server 网络桥接完成（第一阶段）

**日期**：2026-04-17

### 完成内容
1. **PIR Server HTTP 适配层**
   - 新增 `services/pir_server/main.py`
   - 暴露 `/api/v1/pir/query`
   - 当前作为 `PIR Server Adapter (Stub)` 运行
   - 请求协议当前最小化为：
     - `query_payload`
   - 内部以 `asyncio.sleep(1.0)` 模拟耗时执行
   - 保留 `trigger_failure_test` 作为故障注入入口

2. **Verifier 网络桥接改造**
   - 将 `/api/v1/verifier/execute` 改为 `async def`
   - 引入 `httpx` 作为跨服务 HTTP 调用客户端
   - 抽离 `call_pir_server()`，统一承接 Verifier -> PIR Server 的网络桥接
   - 保持原有前置流程不变：
     - RSA 签名验证
     - Binding Consistency Check
     - Redis 状态机与原子 `PENDING` 锁定

3. **状态推进与远端执行结果绑定**
   - 当 PIR Server 成功返回时：
     - `PENDING -> CONSUMED`
   - 当 PIR Server 抛出异常 / 返回 5xx / 执行失败时：
     - `PENDING -> FAILED`
   - 保持 Day 12 既有 reason 语义兼容：
     - `PIR execution failed, ticket burned`

4. **审计本地存根**
   - 在 Verifier 中开始本地组装 `audit_record_stub`
   - 当前仅通过日志记录：
     - `SN`
     - `query_commitment`
     - `binding_tag`
     - `epoch_id`
     - `decision`
     - `reason`
     - `timestamp_ms`
   - 当前阶段尚未接入 Auditor HTTP 后台投递

### 联调结果
在独立启动：
- `services.issuer.main`
- `services.verifier.main`
- `services.pir_server.main`

后，Day 12 生命周期脚本在跨服务模式下再次通过 4 条关键验收：

1. **PENDING 分支（并发冲突）**
   - 首个请求成功占用票据并进入 PIR Server
   - 并发重放请求命中 `PENDING` 并被拒绝

2. **FAILED 分支（远端执行失败）**
   - `trigger_failure_test` 被正确转发到 PIR Server
   - PIR Server 返回 500
   - Verifier 将票据状态推进为 `FAILED`
   - 后续 replay 命中 `FAILED`

3. **CONSUMED 分支（远端执行成功）**
   - 合法请求被转发至 PIR Server 并成功返回
   - 票据状态推进为 `CONSUMED`
   - 后续 replay 命中 `CONSUMED`

4. **边界分支（验证失败不吞票）**
   - 篡改 binding 的请求被前置验证拒绝
   - 票据状态保持 `UNUSED`
   - 随后原始合法请求仍可成功进入 PIR Server 并完成消费

### 关键记录
- 本轮已确认：
  - 当前主链路不再依赖 Verifier 内部的本地 `sleep stub`
  - PIR 执行已从 Verifier 中剥离到独立服务 `pir_server`
- 本轮已确认：
  - 网络桥接并未破坏 Day 12 生命周期状态机语义
  - 当前桥接属于“第一阶段落地”
- 当前审计仍保持“本地日志存根”策略，避免在同一轮中同时引入：
  - PIR 微服务桥接
  - Auditor HTTP 投递
  - 更复杂的异步审计流转

### 小修记录
- 修复了 binding reject 分支中 `PIRResponse` 字段拼写错误导致的错误兜底问题
- 修复后，Test 4 已恢复为预期的业务拒绝路径，而非内部异常路径

### 结论
- Day 13+ 第一阶段：Verifier -> PIR Server 网络桥接已完成
- PIR 执行结果已与票据状态流转绑定
- Day 12 生命周期在跨服务模式下回归通过
- 当前下一步应进入：
  1. Auditor HTTP 存根搭建
  2. 审计记录字段与模型对齐
  3. 后台投递方式的最小闭环验证

## Day 14：blind-sign 主链路收口与核心单测通过

**日期**：2026-04-17

### 完成内容
1. **blind-sign / verify 核心单测**
   - 新增 `tests/test_crypto_core.py`
   - 使用 `pytest` 跑通第一批核心单测
   - 当前测试覆盖：
     - `encode_ticket_message()` 输入边界
     - `sigma` Base64 严格契约反例
     - `blind_message()` 对 `m >= n` 的拒绝
     - `integer_to_base64()` / `base64_to_integer()` round-trip
     - blind issue -> unblind -> verify happy path
     - 篡改 `SN / EpochID / sigma` 的拒绝路径

2. **测试结果**
   - 执行：
     - `PYTHONPATH=. pytest -q tests/test_crypto_core.py`
   - 结果：
     - `6 passed in 0.86s`

3. **错误码和 API 收口**
   - 持续清理 Verifier 拒绝分支的返回语义
   - 保持业务拒绝路径统一走：
     - `PIRResponse(decision=REJECTED, ...)`
   - 保持系统不可用路径（如 Issuer 公钥不可用）与业务拒绝语义分离
   - 清理 blind-sign 主链路中的普通签名占位残留，保持 blind-sign 为唯一主线

4. **与前一阶段的衔接**
   - 当前 blind-sign 主链路已具备：
     - 端到端联调脚本
     - Day 12 生命周期回归
     - Day 13 全链路正反例
     - Day 14 核心单测
   - 说明当前主链路已进入“可回归、可收口”的状态

### 关键记录
- 当前 Day 14 的重点不是继续扩服务数量，而是先把已有 blind-sign 主链路压实
- 现阶段已确认：
  - blind issue / unblind / verify / ticket object 贯通稳定
  - Verifier -> PIR Server 网络桥接未破坏 Day 12 生命周期语义
  - blind-sign 已不再需要普通签名占位路径

### 结论
- Day 14 的前半与后半已完成收口
- blind-sign 主链路当前已具备稳定回归基础
- 下一步应进入：
  1. Auditor HTTP 存根
  2. 审计字段与模型对齐
  3. 后台投递与最小审计闭环验证

## 2026-04-18

## Day 16：Issuer challenge / verify_admission 落地完成

### 完成内容
1. **Admission 公共密码学工具落地**
   - 在 `common/crypto_utils.py` 中新增：
     - `canonical_json_bytes()`
     - `compute_hmac()`
     - `verify_pow()`
     - `solve_pow()`
   - 完成 PoW 前导零 bit 校验
   - 补充 `difficulty_bits` 与 `nonce(uint64)` 边界约束

2. **Admission 对象模型落地**
   - 在 `common/models.py` 中新增：
     - `AdmissionPayload`
     - `AdmissionChallenge`
     - `AdmissionResponse`
     - `ChallengeRequest`
   - 将 `IssueRequest` 扩展为携带：
     - `admission_proof`

3. **Issuer Admission API 落地**
   - 完成 `POST /api/v1/issuer/challenge`
   - 完成 `POST /api/v1/issuer/verify_admission`
   - 在 `/issue` 中内联 admission 校验
   - 当前校验顺序为：
     1. HMAC 真伪校验
     2. challenge 过期校验
     3. Day 16 最小 `epoch_id` 校验（当前固定 1）
     4. PoW 校验
     5. Redis burn / anti-replay
     6. blind sign

4. **Redis Burn Semantics 落地**
   - 使用独立 keyspace：
     - `admission:challenge:<challenge_fingerprint>`
   - 使用 Redis `SET nx=True ex=ttl`
   - 同一 challenge 仅允许成功消费一次
   - 第二次提交命中 replay / burned challenge

5. **配置收口**
   - Admission 相关参数已从 issuer 配置读取：
     - `difficulty_bits`
     - `challenge_ttl_sec`
     - `grace_window_sec`
     - `redis_prefix`

### Day 16 验收脚本
新增：
- `scripts/test_day16_admission.py`

### 验收结果
#### Test 1：No admission proof
- `POST /issue` 返回 `422`
- 结论：未提供 admission proof 无法签票

#### Test 2：Forged HMAC
- `POST /verify_admission` 返回 `403`
- 结论：伪造 challenge 被拒绝

#### Test 3：Invalid PoW Nonce
- `POST /issue` 返回 `403`
- 结论：PoW 校验真实生效

#### Test 4：Replay / Burn Semantics
- 第一次 `/issue` 返回 `200`
- 第二次 `/issue` 返回 `403`
- 结论：Redis burn semantics 生效，同一 challenge 不可复用

### 关键结论
- Day 16 目标已完成：
  - `/challenge` 已实现
  - `/verify_admission` 已实现
  - admission 不通过不能签票
  - 不执行 challenge 拿不到票（已通过反例测试验证）

### 当前限制 / 备注
- `epoch_id` 当前仍为 Day 16 stub，固定为 `1`
- `/verify_admission` 当前主要用于 Day 16 调试与验收
- issuer 日志中当前仍打印原始 `client_tag`，后续应收口为 hash 截断值以满足日志脱敏契约

### 下一步
- 进入 Day 17：blind ticket + admission 整合
- 目标是在不破坏现有 Ticket / Binding / Redis 生命周期契约的前提下，将 admission 与 blind issue 串成一条完整签发链

## 2026-04-18

## Day 17：blind ticket + admission 整合完成

### 完成内容
1. **Client 票据获取主链重构**
   - `services/client/main.py` 中的 `acquire_ticket()` 已整合为完整签票主链：
     1. 获取 Issuer 真实 RSA 公钥
     2. 请求 admission challenge
     3. 本地执行 PoW
     4. 生成 `SN`
     5. 构造并提交 `blinded_message + admission_proof`
     6. 接收 blind signature
     7. 去盲并本地验签
     8. 输出最终 `Ticket(sn, sigma, epoch_id)`

2. **Issuer 公钥获取接口落地**
   - 在 `services/issuer/main.py` 中新增：
     - `GET /api/v1/issuer/public_key`
   - Client 现已不再依赖本地公钥 stub fallback
   - 公钥来源统一收口到 Issuer 真实网络视图

3. **命名收口**
   - 将 client 配置中的 `client_id` 收口为 `client_tag`
   - 保持与 admission 侧“短时上下文标识”的语义一致

4. **Day 17 验收脚本**
   - 新增：
     - `scripts/test_day17_chain.py`
       - 用于最小签票链路验收
     - `scripts/test_day17_full_e2e.py`
       - 用于全链路烟雾测试
       - 覆盖：
         - Client
         - Admission (PoW)
         - Issuer
         - Binding
         - Verifier
         - PIR Server

### 运行结果
#### Day 17+ Full E2E Smoke Test
执行：
- `python scripts/test_day17_full_e2e.py`

结果：
1. Phase 1: Ticket Acquisition (PoW + Blind Sign)
   - challenge 成功
   - PoW 求解成功
   - blind sign 成功
   - 本地去盲与验签成功
   - Ticket 获取成功

2. Phase 2: Payload Binding
   - `create_bound_request()` 成功
   - binding tag 生成成功

3. Phase 3: Verifier Execution & PIR Bridge
   - 请求成功发送至 Verifier
   - Verifier 返回 `decision=SUCCESS`
   - PIR 执行成功并返回结果

关键日志：
- `Local verification passed: Signature is valid.`
- `🎉 [PASS] Full End-to-End Flow is Functional!`

### 关键结论
- Day 17 目标已完成：
  - admission 通过后执行 blind-sign
  - 输出最终 ticket
  - admission 与 blind issue 已串为一条链
- 且该链路已在更大的主线中通过一次真实烟雾测试：
  - `Client -> Admission -> Issuer -> Binding -> Verifier -> PIR`

### 当前限制 / 备注
- issuer / client 日志当前仍打印原始 `client_tag`
- 后续应收口为 hash 截断值，以满足 admission 日志脱敏契约
- `scripts/test_day17_full_e2e.py` 当前已较稳，但错误提示中仍可进一步统一从配置生成

### 下一步建议
优先继续做端到端联调 / 回归脚本收口，而不是立即深挖 Auditor。
原因：
- 主链刚打通，先巩固回归最划算
- 当前项目执行规则仍是：主链路没通前，不深挖高级审计和兼容性
## 2026-04-18

## Day 18：epoch 时间窗接入完成

### 完成内容
1. **Epoch 公共契约落地**
   - 在 `common/crypto_utils.py` 中新增：
     - `get_current_epoch_id(epoch_duration)`
     - `is_epoch_valid(ticket_epoch, now_ts, duration, grace)`
   - 统一 Issuer / Verifier 的 epoch 有效性判定逻辑
   - 为公共函数增加输入边界保护：
     - `duration <= 0` 拒绝
     - `grace < 0` 拒绝

2. **配置层新增 epoch 参数**
   - 在 `configs/common/base.yaml` 中新增：
     - `epoch.duration_sec`
     - `epoch.grace_window_sec`

3. **Issuer 接入动态 epoch**
   - `/challenge` 中不再写死 `epoch_id`
   - 改为根据当前时间动态计算当前纪元
   - `/issue` 在 blind sign 前增加 epoch 有效性检查
   - 避免签发“刚拿到就已过期”的 ticket

4. **Verifier 接入 epoch 前置快拒绝**
   - `/execute` 最前面先检查 `req.ticket.epoch_id`
   - 若明显过期，直接返回业务拒绝
   - 不再让过期票据继续进入验签 / binding / 状态机 / PIR 路径

5. **Day 18 验收脚本**
   - 新增 / 更新：
     - `scripts/test_day18_epoch.py`
   - 将测试从时间敏感方案改为确定性方案：
     - 不再使用 `epoch - 1`
     - 改为 `epoch - 2`

### 运行结果
执行：
- `python scripts/test_day18_epoch.py`

结果：
1. Step 1：获取当前 epoch 的 ticket 成功
   - `✅ Acquired ticket for Epoch: 493473`

2. Step 2：将 ticket 强制篡改为两个纪元之前
   - `expired_ticket.epoch_id = ticket.epoch_id - 2`

3. Verifier 返回：
   - `Status Code: 200`
   - `Decision: REJECTED`
   - `Reason: Ticket epoch 493471 has expired.`

4. Verifier 日志：
   - `Fast-rejecting expired ticket epoch: 493471`

### 关键结论
- Day 18 目标已完成：
  - epoch 已定义
  - 票据带 EpochID
  - verifier 检查当前 epoch
  - 过期票据被拒
- Day 18 未破坏 Day 17 已打通的签票主链
- epoch 时间窗已正式进入 Ticket 与 Verifier 的验证语义

### 当前限制 / 备注
- 当前验收覆盖了“显著过期票据被拒”
- 如后续需要，可再补一个“上一个 epoch 且处于 grace window 内可通过”的正例测试
- issuer/client/verifier 日志中的原始 `client_tag` 仍建议后续收口为 hash 截断值

### 下一步建议
优先继续做端到端回归与联调脚本稳定化，而不是立即深挖 Auditor。
原因：
- 主链刚完成 admission + blind ticket + epoch 收口
- 先保证回归稳定最划算

## 2026-04-18

## Day 19：binding 生成完成

### 完成内容
1. **载荷承诺生成落地**
   - 在 `common/crypto_utils.py` 中实现：
     - `compute_query_commitment(query_payload)`
   - 采用：
     - `c_q = SHA256(query_payload)`
   - 增加输入检查：
     - `query_payload` 必须为非空字符串

2. **绑定标签生成落地**
   - 在 `common/crypto_utils.py` 中实现：
     - `compute_binding_tag(sk_t, c_q_hex, witness_bytes)`
   - 当前工程约定：
     - `b = HMAC_SHA256(sk_t, c_q_hex.encode("utf-8") || witness_bytes)`
   - 增加边界检查：
     - `sk_t` 必须为非空 bytes
     - `c_q_hex` 必须为 64 字符小写 hex
     - `witness_bytes` 必须为非空 bytes

3. **客户端请求实例构造收口**
   - 在 `services/client/main.py` 中完成：
     - `create_bound_request(ticket, query_payload)`
   - 当前执行流程：
     1. Base64 解码 `ticket.sigma`
     2. 派生 `sk_t`
     3. 计算 `c_q`
     4. 构造 `witness`
     5. 规范化序列化 `witness`
     6. 计算 `binding_tag`
     7. 组装 `RequestInstance`

4. **Day 19 验收脚本**
   - 新增：
     - `scripts/test_day19_binding.py`

### 运行结果
执行：
- `python scripts/test_day19_binding.py`

结果：
1. Ticket 获取成功
   - `✅ Ticket acquired!`

2. Binding 生成成功
   - `Binding successful. Binding Tag: ...`

3. RequestInstance 结构完整
   - `request_id` 正常
   - `ticket` 存在且 `SN` 对齐
   - `binding_tag` 存在，长度为 64
   - `witness.nonce` 正常
   - `witness.timestamp_ms` 正常
   - `query_payload` 被正确保留

关键输出：
- `🎉 [PASS] Day 19 Acceptance Criteria Met: Request instance structure is fully formed.`

### 关键结论
- Day 19 目标已完成：
  - `c_q = H(q)` 已生成
  - `b = HMAC(sk_t, H(q)||w)` 已生成
  - 请求实例结构完整形成
- Day 19 未破坏 Day 17/18 已打通的 Ticket 获取主链
- 当前已为 Day 20 的 verifier 侧 binding 校验准备好一致的客户端生成契约

### 当前限制 / 备注
- Day 20 必须严格复用当前 binding 契约：
  - `c_q_hex.encode("utf-8") + witness_bytes`
- verifier 侧若有任何大小写、序列化或 witness 字段漂移，都会导致 binding 验证失败
- issuer/client/verifier 中原始 `client_tag` 日志仍建议后续继续收口为 hash 截断值

### 下一步建议
进入 Day 20：binding verify
重点：
- 在 Verifier 中重算 `c_q`
- 重算 `binding_tag`
- 拒绝篡改 `q / b / w`