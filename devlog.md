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
## 2026-04-18

## Day 20：binding verify 完成

### 完成内容
1. **Verifier 侧 Binding Consistency Check 落地**
   - 在 `services/verifier/main.py` 中实现真实 binding 校验逻辑
   - verifier 当前不再只信任客户端提交的 `binding_tag`
   - 而是基于请求内容重算：
     - `c_q = H(q)`
     - `sk_t = derive_sk_t(sigma_bytes, sn, epoch_id)`
     - `witness_bytes = serialize_witness(witness)`
     - `expected_binding_tag = HMAC(sk_t, c_q || w)`

2. **绑定标签比较收口**
   - 将 `req.binding_tag == expected_binding_tag` 改为：
     - `hmac.compare_digest(req.binding_tag, expected_binding_tag)`
   - 避免简单字符串比较

3. **异常兜底补齐**
   - 对以下情况统一返回业务拒绝，而不是炸 500：
     - 非法 base64
     - 缺失字段
     - 非法 binding 材料
   - 当前对外收口语义：
     - `Invalid Binding Material`

4. **缺失 witness 分支补齐**
   - 若 `req.witness is None`
   - 直接返回：
     - `decision=REJECTED`
     - `reason="Missing Request Witness"`

5. **Day 20 验收脚本**
   - 新增 / 收口：
     - `scripts/test_day20_binding_verify.py`
   - 从配置读取 verifier 地址
   - 增加 timeout
   - 负例先行，正例最后，避免票据被提前消费

### 运行结果
执行：
- `python scripts/test_day20_binding_verify.py`

结果：
1. 合法 Ticket 与合法 Bound Request 生成成功
2. 篡改 `q` -> 被拒绝
3. 篡改 `binding_tag` -> 被拒绝
4. 篡改 `witness.nonce` -> 被拒绝
5. 移除 `witness` -> 被拒绝
6. 原始合法请求 -> 成功通过并执行

关键输出：
- `✅ Defender Win: Tampered query correctly rejected.`
- `✅ Defender Win: Tampered binding tag correctly rejected.`
- `✅ Defender Win: Tampered witness correctly rejected.`
- `✅ Defender Win: Missing witness correctly rejected.`
- `✅ Genuine request correctly accepted and executed (Ticket Consumed).`
- `🎉 [PASS] Day 20 Acceptance Criteria Met: All verification branches tested and passed!`

### 关键结论
- Day 20 目标已完成：
  - verifier 检查 `BindConsistent`
  - 篡改 `q / b / w` 会拒绝
  - 缺失 `witness` 会拒绝
  - 合法请求仍可通过
- binding check 已从“客户端生成”推进到“verifier 真实校验”
- Day 19–20 的 binding 链已经闭合

### 当前限制 / 备注
- 当前测试已覆盖 q/b/w/missing witness/happy path
- 后续如需进一步强化，可增加：
  - 非法 `ticket.sigma` 的 binding 材料异常测试
- issuer/client/verifier 中原始 `client_tag` 日志仍建议后续继续收口为 hash 截断值

### 下一步建议
进入 Day 21：本周联调
重点：
- 正常请求
- 无票据请求
- 过期票据
- 篡改 binding 请求
目标：
- 所有场景被真实区分处理
- 收口为一份周联调 / 回归脚本
## 2026-04-18

## Day 21：本周联调完成

### 完成内容
1. **RequestInstance 模型调整**
   - 在 `common/models.py` 中将以下字段改为 Optional：
     - `ticket`
     - `binding_tag`
     - `witness`
   - 目的：
     - 支持业务层联调与场景化拦截测试
     - 避免所有非法输入都在 schema 层被 422 提前拦截
   - 同时在模型注释中明确：
     - verifier 必须显式做缺失校验

2. **Verifier 精细化拒绝分支补齐**
   - 在 `services/verifier/main.py` 中补齐以下业务拒绝语义：
     - `Missing Ticket in request`
     - `Ticket epoch ... has expired.`
     - `Missing Request Witness`
     - `Missing Binding Tag`
     - `Binding Consistency Check Failed`

3. **Day 21 联调脚本**
   - 新增 / 收口：
     - `scripts/test_day21_integration.py`
   - 从配置读取 verifier 地址与 timeout
   - 使用断言锁死业务契约，不只做打印演示

### 联调场景
本次脚本覆盖以下四类核心场景：

1. **正常请求**
   - 获取合法 ticket
   - 生成合法 binding
   - 发送至 verifier
   - 预期：`SUCCESS`

2. **无票据请求**
   - `ticket = None`
   - 预期：`REJECTED`
   - 原因：`Missing Ticket in request`

3. **过期票据**
   - 先 `epoch_id -= 2`
   - 再生成 binding
   - 预期：`REJECTED`
   - 原因：包含 `expired`

4. **篡改 binding 请求**
   - 修改 `query_payload`
   - 保持原 `binding_tag`
   - 预期：`REJECTED`
   - 原因：`Binding Consistency Check Failed`

### 运行结果
执行：
- `python scripts/test_day21_integration.py`

结果：
- `✅ 正常请求 -> SUCCESS`
- `✅ 缺失票据 -> 真实区分 (Missing Ticket in request)`
- `✅ 过期票据 -> 真实区分 (Ticket expired)`
- `✅ 篡改绑定 -> 真实区分 (Binding Consistency Check Failed)`
- `🎉 [PASS] Day 21 Weekly Integration Complete! All scenarios distinctly handled.`

### 关键结论
- Day 21 目标已完成：
  - 正常请求
  - 无票据请求
  - 过期票据
  - 篡改 binding 请求
  均被真实区分处理
- 这不是单点功能测试，而是本周核心防线的场景化联调
- 当前 Day 17–21 已形成阶段性闭环

### 当前限制 / 备注
- 当前已覆盖四类本周计划中的核心场景
- `Missing Binding Tag` 分支已实现，但 Day 21 脚本中尚未单独作为场景覆盖
- `scripts/test_day21_integration.py` 中仍有一个未使用的 `import time`，后续可清理
- issuer/client/verifier 中原始 `client_tag` 日志仍建议继续收口为 hash 截断值

### 下一步建议
后续可选方向：
1. 推进 Auditor 审计闭环
2. 或先整理更系统的周回归 / 端到端回归套件

从当前状态看，主链已经通，后续重点应放在稳定性与闭环证据，而非重构主线。

## 2026-04-18

## Day 22：Redis 状态表与状态查询接口收口完成

### 完成内容
1. **Redis 状态表管理器收口**
   - 在 `services/verifier/state_manager.py` 中完善 `TicketStateManager`
   - 状态仍保持：
     - `UNUSED`
     - `PENDING`
     - `CONSUMED`
     - `FAILED`

2. **`UNUSED` 语义正式收口**
   - 明确：
     - `Redis miss == UNUSED`
   - 不要求 Issuer 在签发时预写 Redis
   - 避免将状态表错误耦合进 blind ticket 签发链

3. **统一配置接入**
   - Redis 连接参数改为优先从统一 YAML 读取：
     - `host`
     - `port`
     - `db`
   - Redis key 前缀改为从配置读取：
     - `ticket_state_prefix`

4. **Epoch 关联 TTL 落地**
   - 终态 `CONSUMED / FAILED` 的 Redis TTL 不再使用固定保留时长占位
   - 改为按 `epoch_id` 推导：
     - 票据所属 epoch 结束时间
     - `+ grace_window`
     - `+ 600s retention buffer`
   - `ttl_override_sec` 仅供测试 / 联调使用

5. **懒初始化改造**
   - 将 `state_manager` 从 import-time 单例改为懒初始化
   - 避免脚本 / 模块 import 时立刻强依赖 Redis

6. **Verifier 状态查询接口**
   - 新增：
     - `GET /api/v1/verifier/ticket_state/{sn}`
   - 增加严格 `64-char hex` SN 校验
   - 合法 SN 返回状态
   - 非法 SN 返回 `400`

7. **Day 22 验收脚本**
   - 收口 `scripts/test_day22_redis_state.py`
   - 覆盖：
     - Redis miss 默认 `UNUSED`
     - `PENDING` 原子占位
     - `CONSUMED` 终态写入
     - Epoch 驱动 TTL
     - TTL 过期后逻辑状态回归 `UNUSED`

### 运行结果

#### 1. Day 22 Redis 状态表核心语义脚本
执行：
- `python scripts/test_day22_redis_state.py`

结果：
- Redis miss -> `UNUSED`
- `PENDING` 原子占位成功
- 终态写入成功
- Redis 实际 TTL 可按 Epoch 规则推导
- TTL 过期后 Redis key 被物理清理
- 再次查询逻辑状态回归 `UNUSED`

关键输出：
- `✅ 验收点 1 通过: Redis Miss == UNUSED`
- `✅ 验收点 2 通过: PENDING 原子占位成功`
- `✅ 验收点 3 通过: 成功流转终态，且真实 TTL 严格符合 Epoch 时间窗预期`
- `✅ 验收点 4 通过: TTL 过期后发生 Redis Miss，逻辑状态优雅回归 UNUSED`

#### 2. Verifier 状态查询接口
执行：
- `curl -s http://127.0.0.1:8002/api/v1/verifier/ticket_state/<SN>`
- `curl -s http://127.0.0.1:8002/api/v1/verifier/ticket_state/<invalid_sn>`

结果：
- 合法 64-char hex `SN` 返回：
  - `{"sn":"...","ticket_state":"UNUSED"}`
- 非法 `SN` 返回：
  - `{"detail":"Invalid SN format: must be 64-char hex"}`

### 关键结论
- Day 22 的 Redis 状态表核心语义已落地
- Day 22 的“verifier 可查询状态”验收已通过
- 当前实现保持了与既有 blind ticket 主链的一致性：
  - 不要求 Issuer 预写 `UNUSED`
  - 状态查询与终态 TTL 均留在 verifier / Redis 侧完成

### 当前限制 / 备注
- 当前 Redis value 第一版仍只存状态字符串
- 若后续 Auditor 对账需要更强状态可解释性，再考虑升级为结构化 JSON
- 当前 `try_lock()` 已存在，但 Day 23 仍需正式将其收口为原子防并发验收主体
- Verifier 启动时若 Issuer 未开启，仍会在启动日志中出现公钥抓取失败提示；这不影响 Day 22 的只读状态查询接口，但会影响 `/execute` 主链验签路径

### 下一步建议
- 进入 Day 23：原子核销正式收口
- 重点：
  1. 明确 `UNUSED -> PENDING` 的原子状态转换语义
  2. 验证并发 replay 仅允许一次成功
  3. 将短锁 TTL 视需要收口到 YAML 配置

## 2026-04-18

## Day 23：原子核销并发验收完成

### 完成内容
1. **原子核销验收脚本落地**
   - 新增：
     - `scripts/test_day23_concurrency.py`
   - 目标：
     - 验证同一 `SN` 在高并发下只能有一个请求成功完成 `UNUSED -> PENDING`

2. **并发测试机制增强**
   - 使用 `threading.Barrier` 作为统一起跑发令枪
   - 避免仅靠 `sleep()` 制造“近似并发”
   - 提升并发竞争真实性

3. **回归稳定性处理**
   - 测试开始前显式清理目标 `SN` 对应 Redis key
   - 避免旧状态污染本轮并发验收结果

4. **状态落点断言补齐**
   - 在统计成功/失败次数之外
   - 额外断言并发结束后票据最终状态必须为：
     - `PENDING`

### 运行结果

#### Day 23 并发原子核销验收
执行：
- `python scripts/test_day23_concurrency.py`

结果：
- 50 个并发线程统一起跑竞争同一 `SN`
- 成功获取锁：`1` 次
- 原子拦截失败：`49` 次
- 最终票据状态：`PENDING`

关键输出：
- `✅ 成功获取锁 (进入 PIR 主线): 1 次`
- `❌ 触发原子拦截 (被 Verifier 弹回): 49 次`
- `📌 最终票据状态: PENDING`
- `✅ 状态落点断言通过: 最终状态稳定为 PENDING`

### 关键结论
- Day 23 的 `UNUSED -> PENDING` 原子状态转换已通过并发验收
- 当前基于 Redis `SETNX` 的最小原子占位路线可工作
- 当前“并发 replay 只允许一次成功”验收已通过

### 当前限制 / 备注
- 当前 Day 23 仅完成原子占位并发语义的单点验收
- 下一步仍需在 Day 24 中把该原子占位与 verifier 主路径正式绑定
- 当前 `lock_ttl_sec` 仍为脚本 / 调用参数，后续可视需要收口进 YAML

### 下一步建议
- 进入 Day 24：判定路径绑定原子核销
- 重点：
  1. 只有验证通过并成功占位的请求才允许进入 PIR
  2. PIR 成功推进 `CONSUMED`
  3. PIR 失败推进 `FAILED`
  4. 前置验证失败不得改变状态
## 2026-04-19

## Day 24：判定路径绑定原子核销验收完成

### 完成内容
1. **Day 24 验收脚本落地**
   - 新增：
     - `scripts/test_day24_consume_semantics.py`
   - 目标：
     - 验证 Verifier 的判定结果与票据状态消费语义是否严格一致

2. **前置失败不吞票语义确认**
   - 确认以下分支均保持：
     - `ticket_state = UNUSED`
   - 覆盖场景：
     - 缺失票据
     - 过期票据
     - 篡改 binding

3. **成功消费语义确认**
   - 正常请求通过后：
     - 先 `UNUSED -> PENDING`
     - 再 `PENDING -> CONSUMED`
   - 对外返回：
     - `decision = SUCCESS`
     - `ticket_state = CONSUMED`

4. **失败烧毁语义确认**
   - PIR 后端失败时：
     - 先 `UNUSED -> PENDING`
     - 再 `PENDING -> FAILED`
   - 对外返回：
     - `decision = REJECTED`
     - `ticket_state = FAILED`
     - `reason` 包含 burned

5. **故障注入闭环确认**
   - 使用 `trigger_failure_test` 触发 `pir_server` 返回 500
   - Verifier 能正确识别后端失败并将票据烧毁为 `FAILED`

### 运行结果

#### Day 24 判定路径绑定原子核销验收
执行：
- `python scripts/test_day24_consume_semantics.py`

结果：
- 正常请求 -> `SUCCESS + CONSUMED`
- 缺失票据 -> `REJECTED + UNUSED`
- 过期票据 -> `REJECTED + UNUSED`
- 篡改绑定 -> `REJECTED + UNUSED`
- PIR 后端失败 -> `REJECTED + FAILED`

#### 关键日志确认
Verifier 日志显示：
- `UNUSED -> PENDING -> CONSUMED`
- `UNUSED -> PENDING -> FAILED`

PIR Server 日志显示：
- `normal_query` 成功返回 200
- `trigger_failure_test` 触发模拟崩溃并返回 500

### 关键结论
- Day 24 的“判定与消费语义一致”验收已通过
- 当前票据状态机定义与 Verifier 主路径实现已经对齐
- 当前状态机语义可以正式收口为：
  - `UNUSED`：已签发但尚未进入处理流程
  - `PENDING`：已通过前置验证并进入后端处理阶段
  - `CONSUMED`：请求成功执行完成
  - `FAILED`：已进入处理阶段，但后端执行失败或调用异常终止

### 当前限制 / 备注
- 当前 `/execute` 返回体已经足以证明 Day 24 语义成立
- 如后续需要，可再补基于 `/api/v1/verifier/ticket_state/{sn}` 的状态后查复核
- shell 中 `deactivate` 的 CRLF / Anaconda 残留问题不影响本轮 Day 24 验收结果，应单独处理

### 下一步建议
- 进入 Day 25：tamper-evident 审计日志
- 重点：
  1. 明确最小审计字段
  2. 设计链式 HMAC / prev_hash
  3. 保持 Auditor 不影响 Verifier 主返回

## 2026-04-19

## Day 25：tamper-evident 审计日志验收完成

### 完成内容
1. **Day 25 第一版方案定稿**
   - 采用链式 HMAC 审计日志作为第一版篡改留痕机制
   - 不引入更重的链式账本 / 外部公证 / 区块链式结构
   - 保持与当前原型“小修收口”的路线一致

2. **Auditor 配置收口**
   - 在 `configs/common/base.yaml` 中新增 / 收口：
     - `auditor.ledger_path`
     - `auditor.hmac_secret`

3. **Auditor 链式状态机落地**
   - 在 `services/auditor/main.py` 中实现：
     - 启动时恢复 `current_prev_hash`
     - 读取最后一条非空账本记录恢复状态
     - 使用 `lifespan` 托管初始化
     - 使用 `threading.Lock()` 保护链式写入临界区
     - 计算 `prev_hash` 与 `entry_mac`
     - 顺序写入 `audit_ledger.jsonl`

4. **MAC payload 契约固定**
   - 当前 Day 25 第一版固定为：
     - `sn | query_commitment | decision | timestamp_ms | prev_hash`
   - Auditor 与本地验收脚本已使用同一契约

5. **Day 25 验收脚本收口**
   - 完成 `scripts/test_day25_audit_chain.py`
   - 增加：
     - `timeout`
     - `raise_for_status()`
     - 副本文件篡改验证
     - 清理副本，避免污染真实账本

### 运行结果

#### Day 25 审计链验收
执行：
- `python scripts/test_day25_audit_chain.py`

结果：
1. 生成 2 条真实访问请求，构建正常审计链
2. 真实账本完整性校验通过
3. 在副本账本中静默篡改单条记录
4. 再次验证时成功发现 `entry_mac` 校验失败
5. 真实账本保持完好

关键输出：
- `✅ 完整性验证通过 (共 2 条记录)`
- `🚨 [篡改发现] 行 2: entry_mac 校验失败`
- `✅ 成功在副本中捕获篡改行为，真实账本保持完好。`

### 关键结论
- Day 25 的链式 HMAC 审计日志已落地
- 当前方案已能对单条历史记录的静默篡改提供留痕能力
- Day 25 的“每条日志都能串成防篡改链”验收已通过

### 当前限制 / 备注
- 当前安全边界默认 HMAC 密钥不泄露
- 当前 `threading.Lock()` 仅适用于单进程原型场景
- 当前方案主要证明“已记录账本的篡改可发现”，并不等价于更强的外部不可抵赖机制
- 如后续需要支持多进程部署或更强威胁模型，应再升级顺序化与密钥管理方案

### 下一步建议
- 进入 Day 26：Auditor 查询接口
- 重点：
  1. 按 `SN` 查询
  2. 按 `SN + c_q` 做一致性查看
  3. 能读出前后链字段，支撑最小追溯
## 2026-04-19

## Day 26：Auditor 查询接口验收完成

### 完成内容
1. **Auditor 单条追溯接口落地**
   - 在 `services/auditor/main.py` 中新增：
     - `GET /api/v1/auditor/trace/{sn}`
   - 当前用于对单条审计记录做最小追溯

2. **按 SN 查询能力**
   - 可根据票据 `SN` 在 JSONL 账本中定位对应审计记录
   - 返回：
     - `sn`
     - `ledger_line`
     - `record`

3. **链上下文字段回显**
   - 接口当前显式返回：
     - `prev_hash`
     - `entry_mac`
   - 用于最小链上下文查看与后续完整性校验

4. **一致性查询能力**
   - 当传入 `expected_cq` 时：
     - 将其与账本中的 `query_commitment` 比较
   - 返回：
     - `cq_consistent = true / false`

5. **输入与验收收口**
   - 为 `expected_cq` 增加 64-char hex 格式校验
   - 验收脚本前置交易增加：
     - `timeout`
     - `raise_for_status()`
     - `decision == SUCCESS` 断言
   - 明确当前返回的是“当前记录的链上下文”，不是前后邻居完整记录

### 运行结果

#### Day 26 Auditor 追溯与一致性接口验收
执行：
- `python scripts/test_day26_auditor_trace.py`

结果：
1. Client 成功发起一笔真实交易
2. Auditor 可按 `SN` 追溯到对应账本记录
3. 接口返回：
   - `ledger_line`
   - `prev_hash`
   - `entry_mac`
4. 使用正确 `c_q` 查询时：
   - 一致性判定成功
5. 使用伪造 `c_q` 查询时：
   - 一致性判定失败

关键输出：
- `✅ 成功追溯！位于账本第 3 行`
- `✅ 一致性判定成功：账本记录的 c_q 与预期完全匹配`
- `✅ 一致性拦截成功：成功识破事后伪造的载荷承诺！`

### 关键结论
- Day 26 的 Auditor 查询接口已落地
- Day 26 的“Auditor 能追溯单条请求”验收已通过
- 当前审计系统已具备：
  - 最小追溯能力
  - 最小一致性核查能力
  - 最小链上下文读取能力

### 当前限制 / 备注
- 当前接口默认一张票据只对应一条主审计记录，按 `SN` 找到即停
- 当前返回的是链上下文字段，不是完整前后邻居记录
- shell 中 `deactivate` 的 CRLF / Anaconda 残留问题不影响本轮 Day 26 验收结果，应单独处理

### 下一步建议
- 进入 Day 27：最小争议验证闭环
- 重点：
  1. 被 drop 的请求能解释原因
  2. 进入 `PENDING` 的请求能查到处理中痕迹
  3. `CONSUMED / FAILED / replay` 能区分不同原因