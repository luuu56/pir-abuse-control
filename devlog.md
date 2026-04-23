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
## 2026-04-19

## Day 27：最小争议验证闭环验收完成

### 完成内容
1. **Day 27 验收脚本落地**
   - 新增：
     - `scripts/test_day27_dispute_resolution.py`
   - 目标：
     - 验证系统能否对关键争议场景给出最小证据支撑

2. **证据提取逻辑收口**
   - 脚本中统一使用三类证据：
     - HTTP 响应中的 `decision / reason / ticket_state`
     - Verifier 状态接口
     - Auditor 审计记录存在性

3. **前置拦截争议验证**
   - 通过篡改 binding tag 构造前置拒绝场景
   - 证明：
     - 返回原因明确
     - 票据状态保持 `UNUSED`
     - 不会误吞票

4. **PENDING 并发重放争议验证**
   - 通过双请求并发争抢同一票据构造 `PENDING` 冲突
   - 证明：
     - replay 被阻挡
     - 原因提示命中 `PENDING / concurrent`
     - 票据处理中痕迹可见
     - 首个请求最终成功转入 `CONSUMED`

5. **CONSUMED 重放争议验证**
   - 对已成功消费的票据再次重放
   - 证明：
     - replay 命中 `CONSUMED`
     - Verifier 状态为 `CONSUMED`
     - Auditor 审计账本存在记录

6. **FAILED 烧毁重放争议验证**
   - 使用 `trigger_failure_test` 触发后端失败
   - 证明：
     - 首次失败请求进入 `FAILED`
     - 后续 replay 命中 `FAILED`
     - Verifier 状态为 `FAILED`
     - Auditor 审计账本存在记录

### 运行结果

#### Day 27 最小争议验证闭环
执行：
- `python scripts/test_day27_dispute_resolution.py`

结果：
1. 前置拦截场景 -> 通过
2. `PENDING` 并发重放场景 -> 通过
3. `CONSUMED` 已核销重放场景 -> 通过
4. `FAILED` 烧毁重放场景 -> 通过

关键输出：
- `✅ 举证成功: 明确返回原因 [Binding Consistency Check Failed], 票据安全保持在 UNUSED`
- `✅ 举证成功: 并发重放被成功阻挡, 原因 [Ticket already PENDING], 票据当前严格处于 PENDING`
- `✅ 举证成功: 成功识别已完成重放, 原因 [Ticket already CONSUMED], 物理状态 CONSUMED, 具备底层审计哈希链`
- `✅ 举证成功: 后端异常导致票据烧毁为 FAILED, 重放被拦截提示 [Ticket already FAILED], 具备底层审计哈希链`

### 关键结论
- Day 27 的最小争议验证闭环已通过
- 当前系统已经具备对关键争议场景的最小证据支撑能力
- 当前证据链可由以下三部分组成：
  - HTTP 业务响应
  - Verifier 状态查询
  - Auditor 审计留痕

### 当前限制 / 备注
- 当前 `PENDING` 场景仍依赖原型级短暂等待来构造处理中重放
- 当前前置被 drop 的请求默认不产生终态审计记录
- shell 中 `deactivate` 的 CRLF / Anaconda 残留问题不影响本轮 Day 27 验收结果，应单独处理

### 下一步建议
- 进入 Day 28：阶段重构
- 重点：
  1. 清理 verifier 逻辑
  2. 清理审计字段
  3. 清理 API
  4. 为下一阶段真实 PIR 集成前做一次阶段收口

## 2026-04-19

## Day 28：阶段重构最终收口完成

### 完成内容
1. **Verifier 主流程阶段化重构最终版落地**
   - 最终将 `services/verifier/main.py` 收口为三层结构：
     - `_run_precondition_check`
     - `_run_crypto_verification`
     - `execute_query` 编排器

2. **前置规则层最终收口**
   - 保持处理：
     - 缺失票据
     - 纪元过期
     - 状态非 `UNUSED`
   - 外部拒绝语义不变

3. **密码学校验层最终收口**
   - 保持处理：
     - issuer 公钥可用性兜底
     - RSA 验签
     - witness 缺失检查
     - binding_tag 缺失检查
     - binding consistency check
     - invalid binding material 兜底

4. **后端桥接层异常分类最终收口**
   - `call_pir_server()` 当前已明确区分：
     - `timeout`
     - `http_error_<code>`
     - `connection_error`
     - `unknown_error`

5. **审计异步投递最终收口**
   - `dispatch_audit_log()` 增加 `raise_for_status()`
   - 保持：
     - Verifier 只投递业务快照
     - `prev_hash / entry_mac` 真实链式注入继续由 Auditor 负责

6. **API 文案契约最终收口**
   - `query_ticket_state()` 的非法 SN 返回：
     - `Invalid SN format: must be 64-char hex`

### 最终回归验收

#### 1. Day 27 争议闭环回归
执行：
- `python scripts/test_day27_dispute_resolution.py`

结果：
- drop / PENDING / CONSUMED / FAILED / replay 全部通过
- 证明最终版 verifier 主链行为保持一致

#### 2. Day 26 Auditor 查询接口回归
执行：
- `python scripts/test_day26_auditor_trace.py`

结果：
- 按 `SN` 追溯通过
- 正确 `c_q` 一致性通过
- 伪造 `c_q` 一致性拦截通过

#### 3. Day 25 审计链回归
执行：
- `python scripts/test_day25_audit_chain.py`

结果：
- 真实账本完整性验证通过
- 篡改副本仍可被审计链识别

### 关键结论
- Day 28 的阶段重构已最终完成
- 当前最终版 `services/verifier/main.py` 已通过高强度回归验证
- 当前重构真正达到了：
  - 内部更清晰
  - 外部无感知
  - 核心票据 / 验证 / 审计链路稳定

### 当前限制 / 备注
- 当前 `lock_ttl_sec=30` 仍为原型级固定值，后续可收口进 YAML
- 当前审计字段中仍混有核心字段与快照字段，后续可再梳理边界
- shell 中 `deactivate` 的 CRLF / Anaconda 残留问题仍不影响本轮 Day 28 验收结论，应单独处理

### 下一步建议
- 在进入下一阶段前，先做一次总结构梳理
- 明确：
  1. 当前哪些能力已经固化
  2. 哪些仍是原型级占位
  3. 下一阶段真实 PIR / eBPF / 更强审计该如何接入

## 2026-04-19

## Day 29：真实主候选 PIR 正式接入完成

### 完成内容
1. **PIR Adapter 收口**
   - `pir_server` 继续保持为 Python 控制层 / adapter
   - 保持 `stub / subprocess` 双模式
   - subprocess 模式下统一使用 JSON stdin/stdout 协议
   - 未引入 Python 进程内 FFI 硬绑定

2. **Go Wrapper 二进制边界收口**
   - 在主候选仓库内建立：
     - `pir_engine/simplepir/cmd/json_bridge`
   - 恢复并保留以下边界验收分支：
     - `fatal_crash_test`
     - `bad_json_test`
     - `status_error_test`
   - 完成 Go 二进制边界验收，证明 Python 可稳定调度真实 Go ELF 二进制

3. **真实 SimplePIR 核心接入**
   - 不再停留在 placeholder / mock 结果
   - 已根据主候选仓库内 `RunPIR` 的真实顺序接入最小调用链：
     - `Init`
     - `Setup`
     - `Query`
     - `Answer`
     - `Recover`
   - 当前 Day 29 采用固定小型 DB 作为确定性基线：
     - `numEntries = 1024`
     - `vals[42] = 4242`

4. **协议洁净度修复**
   - 发现真实 SimplePIR 调用期间，底层 Go 输出会污染 stdout，导致 Python 侧命中 `502 Bad Gateway`
   - 最终通过在真实加密区局部重定向 stdout -> stderr 的方式完成净化
   - 保证 Python 侧最终仅接收到一份 JSON 响应

5. **确定性红线验收**
   - 新增确定性 PIR 红线脚本
   - 初始阶段该脚本能正确拦住 placeholder 假阳性
   - 真实 SimplePIR 接入后，红线脚本成功转绿：
     - 固定索引 `42`
     - 成功恢复固定真值 `4242`

### 验收结果
#### Day 29（中）：Go Wrapper 边界验收通过
1. 正常调用成功
2. `fatal_crash_test` 被隔离并映射为 `500`
3. `bad_json_test` 被识别并映射为 `502`
4. `status_error_test` 被识别并映射为逻辑失败路径

#### Day 29（下）：真实主候选确定性验收通过
执行：
- `python scripts/test_day29_deterministic_pir.py`

结果：
1. 请求成功穿透 Python adapter 与 Go wrapper
2. 真实 SimplePIR 核心计算被执行
3. 返回：
   - `Decrypted value from index 42 is: 4242`
4. 红线脚本通过，证明当前结果不再是 placeholder 假阳性

### 关键结论
- Day 29 目标已完成：
  - 系统已能实际调用真实主候选 PIR 后端
- 当前完成的是“真实主候选可调用”的收口，不是性能优化版实现
- 当前仍保持既定工程边界：
  - PIR 后端独立进程 / 微服务
  - Python 仅作 adapter
  - 不做进程内 FFI

### 下一步
进入后续阶段时，优先继续收口：
1. `q -> PIR query` 的正式映射
2. Python 与独立 PIR 后端之间的输入输出协议最终版
3. 输出解析与错误返回路径
4. DB / hint 生命周期与性能优化
## 2026-04-19

## Day 31：请求实例与 PIR 输入对齐（第一轮收口完成）

### 完成内容
1. **q -> PIR index 映射落地**
   - 在 Python `pir_server` 中引入第一版映射函数
   - 当前规则：
     - `SHA256(query_payload) % 1024`
   - 将业务字符串请求正式映射到 Go 侧可消费的整数索引

2. **Python -> Go 输入协议收口**
   - 当前发送给独立 Go PIR 后端的 JSON 字段为：
     - `request_id`
     - `query_payload`
     - `pir_input`
     - `engine_request_type`
   - 其中：
     - `pir_input` 为字符串形式的 `mapped_index`

3. **Go -> Python 输出协议收口**
   - Go wrapper 当前输出字段包括：
     - `status`
     - `result`
     - `recovered_val`
     - `error_type`
     - `error_message`
     - `engine_meta`
   - Python `engine_adapter.py` 当前已支持解析并返回：
     - `result`
     - `recovered_val`
     - `engine_meta`

4. **动态可预测数据库基线替换**
   - 当前 Go wrapper 已从 Day 29 固定基线：
     - `vals[42] = 4242`
   - 升级为 Day 31 动态规则：
     - `vals[i] = i * 101`
   - Go 侧新增动态自验：
     - `expectedVal = queryIndex * 101`
     - 若恢复值不匹配，则返回 `crypto_error`

5. **上层返回结构增强**
   - `/api/v1/pir/query` 当前对上层返回：
     - `data`
     - `mapped_index`
     - `recovered_val`
   - 使 Day 31 验收不再依赖字符串观察，而可基于结构化字段断言

6. **Day 31 动态映射验收脚本通过**
   - 当前已通过：
     - `query_apple`
     - `query_banana`
     - `user_12345`
   - 每条测试均验证：
     1. `mapped_index` 与 Python 本地哈希预测一致
     2. `recovered_val` 与 `mapped_index * 101` 一致

### 验收结果
执行：
- `python scripts/test_day31_dynamic_mapping.py`

结果：
- `3/3 Passed`

关键输出：
- `Pass: Index mapped to 447, recovered crypto value 45147`
- `Pass: Index mapped to 188, recovered crypto value 18988`
- `Pass: Index mapped to 322, recovered crypto value 32522`

### 关键结论
- Day 31 第一轮目标已达成：
  - 请求实例已能驱动真实 PIR 查询
- 当前系统已从 Day 29 固定索引基线推进到：
  - `q -> mapped_index -> recovered_val`
  的第一版动态协议链路
- 当前主线验收脚本应切换为：
  - `scripts/test_day31_dynamic_mapping.py`

### 备注
- Day 29 旧脚本失败并不代表主线回退，而是因为它们验证的是固定基线合同
- 当前 Day 31 已切换为动态映射合同，因此旧脚本不再适合作为主线验收脚本

### 下一步
后续优先继续收口：
1. `DB_NUM_ENTRIES` / `NUM_ENTRIES` 的统一来源
2. `engine_meta` 字段规范
3. 错误码 / reason 文案标准化
4. 决定是否保留固定基线模式供历史脚本继续回归
## 2026-04-19

## Day 32：主链路联调完成

### 完成内容
1. **Verifier 结果透传升级**
   - `call_pir_server()` 已从简单成功/失败桥接升级为结构化返回：
     - `success`
     - `payload_or_error`
     - `mapped_index`
     - `recovered_val`
   - verifier 成功分支已将真实 PIR 结果封装进 `PIRResponse.data`

2. **PIR 成功 / 失败状态收敛保持一致**
   - PIR 成功：
     - `PENDING -> CONSUMED`
     - `decision = SUCCESS`
   - PIR 失败：
     - `PENDING -> FAILED`
     - `decision = REJECTED`
   - 未破坏既有状态机语义

3. **Auditor 后台投递继续保留**
   - 当前审计投递仍正常挂在 background task 上
   - 当天未强行把 `mapped_index` 扩进 auditor 模型，避免 auditor schema 阻塞主链 happy path

4. **新增 Day 32 全链路验收脚本**
   - 新增：
     - `scripts/test_day32_full_pipeline.py`
   - 脚本完成以下验证：
     1. client 获取 ticket
     2. client 构造 binding request
     3. 请求提交 verifier
     4. verifier 调真实 PIR
     5. 返回结构化 `mapped_index / recovered_val`
     6. 本地预测值与实际值一致

### 验收结果
执行：
- `python scripts/test_day32_full_pipeline.py`

结果：
- `Status Code: 200`
- `Decision: SUCCESS`
- `Reason: PIR execution completed`

实际返回：
- `result_string = [REAL_SIMPLEPIR_ENGINE] Decrypted value from index 86 is: 8686`
- `mapped_index = 86`
- `recovered_val = 8686`

本地预测：
- `expected_index = 86`
- `expected_val = 8686`

比对结果：
- `mapped_index` 一致
- `recovered_val` 一致

最终输出：
- `Day 32 Success: Full pipeline from Blind-Sign to SimplePIR is verified!`

### 关键结论
- Day 32 验收已通过：
  - 合法请求已能返回真实 PIR 结果
- 当前系统已不再只是“模块可跑通”，而是已形成端到端主链 happy path：
  - blind ticket
  - admission
  - binding
  - verifier
  - real PIR
  - auditor background delivery

### 下一步
进入 Day 33 时，优先验证：
1. 非法请求不会进入 PIR
2. PIR 前后日志能清楚区分“被前置挡下”和“进入真实计算”
3. 主链 happy path 不因 Day 33 的负例验证而回退

## 2026-04-19

## Day 33：非法请求不进入 PIR 验证完成

### 完成内容
1. **Verifier 新增轻量级运行时 metrics**
   - 当前在 verifier 内新增：
     - `total_requests`
     - `blocked_before_pir`
     - `pir_invoked`
   - 并通过：
     - `/api/v1/verifier/metrics`
     对外暴露当前统计信息

2. **PIR 前后探针日志落地**
   - 在 verifier 调用底层 PIR 前增加：
     - `🚀 [PIR_START]`
   - 在 verifier 接收底层 PIR 返回后增加：
     - `🏁 [PIR_END]`
   - 当前日志可用于人工排查某个请求是否真正进入了重计算阶段

3. **Day 33 负例攻击脚本完成**
   - 新增：
     - `scripts/test_day33_abuse_prevention.py`
   - 当前脚本会发射：
     1. 1 个合法请求
     2. 1 个篡改 binding 的恶意请求
     3. 1 个缺失 ticket 的恶意请求
     4. 1 个 replay 请求

4. **业务层与指标层双重对账**
   - 不仅验证 `decision == REJECTED`
   - 还通过 metrics 对账验证：
     - 非法请求没有真正进入 `call_pir_server()` 区域
   - 当前使用的最硬指标为：
     - `added_pir == 1`

### 验收结果
执行：
- `python scripts/test_day33_abuse_prevention.py`

结果如下：

1. 合法请求：
   - `SUCCESS`
   - 成功进入真实 PIR

2. 篡改 binding 请求：
   - 被拦截
   - 原因：
     - `Binding Consistency Check Failed`

3. 缺失 ticket 请求：
   - 被拦截
   - 原因：
     - `Missing Ticket in request`

4. replay 请求：
   - 被拦截
   - 原因：
     - `Ticket already CONSUMED`

最终 metrics 对账为：
- `Total Requests Fired : 4`
- `Business Blocked     : 3`
- `Actual PIR Invoked   : 1`

最终输出：
- `Day 33 Success: PIR engine is perfectly isolated from malicious traffic!`

### 关键结论
- Day 33 验收通过：
  - 非法请求不会触发 PIR 计算
- 当前系统已经同时具备：
  - Day 32 的 happy path 能力
  - Day 33 的负例隔离能力

### 下一步
后续优先进入：
1. Day 34 功能性指标整理
2. 汇总成功率 / 拦截率 / 进入 PIR 比例
3. 保持 Day 32 与 Day 33 的主链与负例能力都不回退
## 2026-04-19

## Day 34：第一轮功能性指标整理完成

### 完成内容
1. **新增 Day 34 功能性指标脚本**
   - 新增：
     - `scripts/test_day34_functional_metrics.py`
   - 脚本采用固定配比测试流量，而非随机概率压测
   - 当前测试波次为：
     1. 5 个正常请求
     2. 3 个 replay 攻击
     3. 1 个 binding 篡改请求
     4. 1 个伪造签名请求

2. **基于 metrics 做 PIR 进入比例对账**
   - 当前继续复用 verifier 的内存指标：
     - `total_requests`
     - `blocked_before_pir`
     - `pir_invoked`
   - 并在报表中同时打印：
     - `Expected PIR Invocations`
     - `Actual PIR Engine Invoked`

3. **功能性指标报表输出完成**
   - 当前脚本会输出以下指标：
     - 正常成功率
     - replay 拦截率
     - binding 错误拦截率
     - signature 伪造拦截率
     - PIR 进入比例

### 验收结果
执行：
- `python scripts/test_day34_functional_metrics.py`

初始 metrics：
- `{'total_requests': 0, 'pir_invoked': 0, 'blocked_before_pir': 0, 'block_ratio_percent': 0.0}`

最终 metrics：
- `{'total_requests': 10, 'pir_invoked': 5, 'blocked_before_pir': 5, 'block_ratio_percent': 50.0}`

最终功能性指标结果：
- `Normal Request Success Rate  : 100.00% (5/5)`
- `Replay Interception Rate     : 100.00% (3/3)`
- `Binding Interception Rate    : 100.00% (1/1)`
- `Signature Interception Rate  : 100.00% (1/1)`
- `Expected PIR Invocations     : 5`
- `Actual PIR Engine Invoked    : 5`
- `PIR Entry Proportion         : 50.00%`

### 关键结论
- Day 34 验收通过：
  - 第一轮功能性指标整理完成
- 当前系统已经同时具备：
  - Day 32：主链 happy path
  - Day 33：非法请求隔离
  - Day 34：功能性指标定量化能力

### 下一步
后续优先继续收口：
1. 失败原因进一步分类统计
2. 功能性指标脚本与主链/攻击脚本的职责边界整理
3. 决定哪些指标保留为常驻调试接口，哪些只保留在实验脚本中
## 2026-04-19

## Day 35：缓冲 / 修复日完成

### 背景
Day 34 已经整理出第一轮功能性指标，当前需要做一次“小修收口”，目标不是重构主架构，而是：
1. 修复 PIR 集成细节问题
2. 清理 wrapper
3. 稳定主链路

本轮严格遵守既有固定前提：
- 主线仍为 `blind ticket -> admission -> binding -> verifier -> PIR -> audit`
- blind signature 第一版仍为 RSA blind signature
- PIR 后端仍保持独立进程 / 微服务集成
- 状态机仍为 `UNUSED / PENDING / CONSUMED / FAILED`
- 不扩大 eBPF 职责
- 保持统一 YAML 配置与统一 logging

### 完成内容
1. **PIRResponse 对外返回契约强类型化**
   - 在 `common/models.py` 中新增：
     - `PIRResultPayload`
   - 将：
     - `PIRResponse.data: Optional[Any]`
     收口为：
     - `PIRResponse.data: Optional[PIRResultPayload]`

2. **Verifier 成功路径收口**
   - 在 `services/verifier/main.py` 中引入 `PIRResultPayload`
   - 成功路径不再返回普通 dict
   - 改为显式组装：
     - `PIRResultPayload(result_string, mapped_index, recovered_val)`

3. **Wrapper 类型注解收缩**
   - 将 `call_pir_server()` 的返回类型从宽松 `Any` 收口为：
     - `tuple[bool, str, Optional[int], Optional[int]]`
   - 保持函数内部逻辑不扩面，不新加额外包装层

4. **成功分支增加防御性检查**
   - 新增对以下异常情况的保护：
     - `success=True`
     - 但 `mapped_index is None` 或 `recovered_val is None`
   - 当前处理策略：
     - 记录错误日志
     - 票据转为 `FAILED`
     - reason 收口为：
       - `PIR execution failed, ticket burned. Error: malformed PIR response`
   - 这样可以避免“表面成功、结果畸形”的桥接返回污染成功路径

5. **保持 Auditor 契约不扩面**
   - 明确 Day 35 不提前把 `mapped_index` 塞入 `AuditRecord`
   - verifier 投递 auditor 的 payload 继续剔除 `mapped_index`
   - 避免 verifier / auditor 模型错位

### 回归验证
执行：
```bash
python scripts/test_day34_functional_metrics.py
```
结果：

初始 metrics 为 0，说明本次统计未受旧值污染
最终 metrics：
total_requests = 10
pir_invoked = 5
blocked_before_pir = 5
功能性指标结果保持：
Normal Request Success Rate = 100.00% (5/5)
Replay Interception Rate = 100.00% (3/3)
Binding Interception Rate = 100.00% (1/1)
Signature Interception Rate = 100.00% (1/1)
Expected PIR Invocations = 5
Actual PIR Engine Invoked = 5
PIR Entry Proportion = 50.00%
关键判断
Day 35 本轮修改属于“小修收口”，没有推翻既有结构
强类型化与成功分支防御检查没有破坏 Day 34 功能性指标脚本
当前可以确认：
该进 PIR 的请求仍能进入 PIR
不该进 PIR 的请求仍被挡在前面
说明 verifier / pir_server / metrics 三者口径仍保持一致
当前备注
PIR Entry Proportion = 50% 的含义仍应在报告中注明：
这是固定 10 个样本（5 合法 + 5 非法）下的进入比例
不是一般流量分布结论
当前尚未单独补 malformed PIR response 的定向故障注入脚本
如后续需要，可补一条专门回归“success=true 但字段缺失”的测试
结论
Day 35 已完成
当前已完成“修复 PIR 集成问题、清理 wrapper、稳定主链路”的目标
主链继续保持稳定，可进入下一阶段
## 2026-04-20

## Day 38：eBPF 早期过滤规则（服务器版）完成

### 完成内容
1. **Day 38 服务器版路线收口**
   - 明确继续采用：
     - `BCC Python 绑定 + pyroute2 + TC`
   - 不切换到 `clang + .o + tc filter add ...` 直加载路线
   - 保持与 Day 37 的 BCC Python 验证路径一致，避免扩大手术面

2. **TC 挂载范围固定**
   - 过滤接口固定为：
     - `eth0 ingress`
   - 过滤目标固定为：
     - 仅 `TCP`
     - 仅目标端口 `8002`

3. **浅层硬丢弃规则落地**
   - 在 `scripts/tc_gateway.py` 中完成：
     - Ethernet / IPv4 / TCP 解析
     - `ip->ihl >= 5` 防御性检查
     - `tcp->doff >= 5` 防御性检查
   - 当前唯一硬丢弃规则为：
     - `payload[0:4] == "HACK"` -> `TC_ACT_SHOT`
   - 该规则用于表达 Day 38 第一版“最明显非法流量早丢弃”的最小落地点

4. **轻量观测信号落地**
   - 增加浅层观测：
     - `HTTP POST detected`
     - 前 96 字节窗口内扫描 `"ticket"` 关键词
   - 当前 `"ticket"` 扫描仅做 trace，不参与 drop 决策
   - 保持 eBPF 第一版只做 fast path 观测，不越界承担 verifier 语义

5. **挂载脚本工程收口**
   - 增加 `eth0` 存在性检查
   - 挂载前清理旧 `clsact`
   - 退出时显式 detach，并打印 cleanup 日志
   - 保持 `bpf_trace_printk()` 仅用于 Day 38 验收观测

6. **外部测试脚本落地**
   - 新增 `scripts/day38_test_client.py`
   - 使用 Python socket 从外部主机发流
   - 强制要求传入服务器 `eth0` IP
   - 明确禁止默认 `127.0.0.1`，避免误走 `lo` 接口导致无法触发 `eth0 ingress`

### 验收过程
#### Case 1：Malicious HACK Fingerprint
- 外部主机向服务器 `eth0:8002` 发送：
  - `HACK_ATTACK_GARBAGE_DATA`
- 客户端视角表现为：
  - `Connection Timeout`
- 服务器 TC trace 明确出现：
  - `[TC DROP] Malicious HACK fingerprint!`

#### Case 2：Standard HTTP POST with ticket
- 外部主机向：
  - `/api/v1/verifier/execute`
  发送标准 HTTP POST
- 服务器 TC trace 明确出现：
  - `[TC OBSERVE] HTTP POST detected`
  - `[TC OBSERVE] Found 'ticket' in payload buffer`
- Verifier 明确收到请求，并返回：
  - `422 Unprocessable Entity`

### 关键结论
- Day 38 第一版目标已完成：
  - eBPF/TC 能真实丢弃一类明显非法流量
  - 正常格式 HTTP 流量能够穿过 TC 到达 verifier
- 当前实现严格保持了既定边界：
  - eBPF 只做轻量前置过滤
  - 不做 Redis / blind ticket verify / binding verify / 原子核销
  - 不把 Day 38 做成第二个 verifier

### 结果解释
- Case 2 返回 `422` 的原因不在 TC，而在于当前外部测试脚本构造的原始 HTTP 报文不完整，body 解析未完全对齐 FastAPI 的请求模型
- 但这不影响 Day 38 验收，因为 Day 38 的判断标准是：
  - 正常候选流量能否穿过 TC 并到达 verifier
  - 而不是在 eBPF 层完成业务成功判定

### 当前状态
- Day 38 已完成服务器版验收
- 当前 eBPF fast path 已具备：
  - 浅层指纹硬丢弃
  - 浅层 HTTP / ticket 观测
  - 正常候选流量放行到 verifier

### 下一步
- 进入 Day 39：eBPF 与 verifier 协作
- 目标：
  1. 明确 fast path / full path 的协作边界
  2. 让 eBPF 负责早拒绝明显非法流量
  3. 让 verifier 继续承担完整验证与 consume 语义
  4. 
  ## 2026-04-20

## Day 39：eBPF 与 verifier 协作联调完成

### 背景
在 Day 38 中，已经完成服务器版 eBPF/TC 轻量前置过滤，并确认：
- `HACK` 指纹垃圾流量可在 `eth0 ingress` 被真实丢弃
- 正常 HTTP 候选流量可继续进入 verifier

因此 Day 39 的目标不是继续增强 eBPF 复杂度，而是验证两级架构是否真实协作：
1. eBPF 早拒绝非法流量
2. 候选流量进入 verifier
3. verifier 做完整验证与 consume

### 完成内容
1. **新增 Day 39 联调脚本**
   - 新增并跑通：
     - `scripts/test_day39_two_level_defense.py`
   - 当前脚本覆盖四类典型流量：
     1. 纯垃圾流量
     2. 候选 HTTP 非法流量
     3. replay / double spend
     4. 完整合法流量

2. **Case A：eBPF 早拒绝验证**
   - 从外部主机向服务器 `8002` 发送：
     - `HACK_ATTACK_GARBAGE_DATA`
   - 客户端视角表现为超时
   - TC trace 明确出现：
     - `[TC DROP] Malicious HACK fingerprint!`
   - 证明明显非法流量已在内核前置层被早期丢弃

3. **Case B：候选流量进入 verifier 并被用户态拒绝**
   - 构造缺失 `ticket` 的 HTTP 请求
   - 请求成功穿过 eBPF
   - verifier 返回：
     - `decision=REJECTED`
     - `ticket_state=UNUSED`
     - `reason=Missing Ticket in request`
   - 证明 eBPF 未误杀候选流量，业务拒绝仍由 verifier 承担

4. **Case C：replay / double spend 仍由 verifier 状态机拦截**
   - 第一枪使用真实 ticket + binding 发起请求
   - verifier 成功推进：
     - `UNUSED -> PENDING -> CONSUMED`
   - 请求成功进入真实 PIR，并返回真实 SimplePIR 结果
   - 第二枪重放同一请求后：
     - verifier 返回 `Ticket already CONSUMED`
   - 证明 replay 拦截语义未下沉到 eBPF，仍由用户态状态机负责

5. **Case D：合法请求穿透两级防线**
   - 获取新的真实 ticket
   - 生成新的合法 binding
   - 请求成功穿透 eBPF + verifier
   - 返回：
     - `decision=SUCCESS`
     - `ticket_state=CONSUMED`
     - 真实 SimplePIR 结果
   - pir_server 日志确认：
     - `External PIR engine executed successfully`

### 关键日志对账
#### 1. TC / eBPF
- trace 中明确出现：
  - `[TC DROP] Malicious HACK fingerprint!`
  - `[TC OBSERVE] HTTP POST detected`
  - `[TC OBSERVE] Found 'ticket' in payload buffer`

#### 2. Verifier
- 明确看到：
  - `Missing Ticket in request`
  - `UNUSED -> PENDING`
  - `[PIR_START]`
  - `[PIR_END]`
  - `Ticket already CONSUMED`

#### 3. PIR Server
- `query_target_C` 与 `query_target_D` 均成功进入外部 SimplePIR 引擎
- 当前返回结果不再是 stub success，而是真实解密结果

### 关键结论
- Day 39 验收通过：
  - BPF 负责早拒绝最明显非法流量
  - verifier 负责完整验证与 consume
- 当前实现仍严格遵守既定边界：
  - eBPF 第一版只做轻量前置过滤
  - verifier 仍是唯一完整业务判定层
- 因而 Day 39 的目标已完成：
  - `eBPF 早拒绝非法流量`
  - `候选流量进入 verifier`
  - `verifier 做完整验证与 consume`
  - `两级架构联动成功`

### 当前问题 / 备注
- verifier 日志中出现：
  - `Auditor report failed: All connection attempts failed`
- 说明 Auditor 服务未在本轮联调中接通
- 该问题不影响 Day 39 主防线验收，但说明 audit 旁路当前未参与联动

### 下一步
- 进入 Day 40：前置验证与状态表联动
- 重点：
  1. 明确 eBPF 不单独伪造业务决策
  2. 保持 verifier 继续使用 Redis 状态表
  3. 进一步收口 fast path / full path 与状态机之间的职责边界
  4. 
  ## 2026-04-21

## Day 40：前置验证与状态表联动完成

### 完成内容
1. **Day 40 职责边界收口**
   - 明确保持：
     - verifier / Redis 为唯一业务状态真相源
     - eBPF 不表达 `UNUSED / PENDING / CONSUMED / FAILED`
     - eBPF 不单独伪造业务决策
   - Day 40 的目标不再是增强 eBPF 复杂度，而是验证：
     - 状态判断仍留在 verifier / Redis
     - eBPF 仅执行 verifier 派生出来的 fast-path block

2. **`tc_gateway.py` 升级为动态联动执行器**
   - 在 eBPF 程序中新增：
     - `BPF_HASH(blocklist, u32, u64, 2048)`
   - 当前 blocklist 语义为：
     - key = source IP
     - value = expire timestamp (ns)
   - 内核态只做：
     - 查表
     - 未过期则 `TC_ACT_SHOT`
   - 不在内核态做删除操作
   - 保留 Day 38 既有静态规则：
     - `payload[0:4] == "HACK"` -> drop

3. **动态 block 作用范围收口**
   - 关键修正：
     - blocklist 只在 `tcp->dest == 8002` 之后生效
   - 因而不会误伤：
     - Issuer `8001`
     - 其他非 verifier 端口
   - 这保证了 Day 40 的联动语义严格限定在 verifier 入口前

4. **本机控制面落地**
   - 在 `tc_gateway.py` 中新增 UDP 控制面线程：
     - 监听 `127.0.0.1:9002`
   - 控制面功能：
     - 接收 verifier 发来的 `BLOCK <ip> <duration_sec>`
     - 将来源级短时封禁同步到 eBPF map
     - 在用户态顺手清理过期条目
   - 当前日志语义收口为：
     - `[CONTROL] Derived Block Sync from verifier decision: IP ...`

5. **verifier 派生信号通道落地**
   - 在 `services/verifier/main.py` 中新增：
     - `Request` 注入
     - `dispatch_l4_block_signal(...)`
   - 当前策略明确收口为：
     - 仅当 `ticket_state == CONSUMED`
     - 即明确 replay / double spend 场景
     - 才派生来源级短时 L4 block
   - `PENDING / FAILED` 当前仍只返回业务拒绝，不派生 L4 block

6. **Day 40 验收脚本落地**
   - 新增：
     - `scripts/test_day40_derived_block.py`
   - 验收脚本覆盖四类流量：
     1. Case A：静态 `HACK` 指纹 drop
     2. Case B：候选 HTTP 流量进入 verifier 并被用户态拒绝
     3. Case C：replay 命中 `CONSUMED`，由 verifier 派生 block
     4. Case D：同源后续新请求在 8002 入口被 eBPF fast-path drop

### 验收结果

#### Case A：Static Fingerprint Drop
- 客户端视角：
  - `Connection Timeout`
- TC trace 出现：
  - `[TC DROP] Static Fingerprint: HACK detected`
- 说明 Day 38 既有静态 fast-path 防线仍正常工作

#### Case B：HTTP Candidate Traffic Rejected in User Space
- Verifier 返回：
  - `decision=REJECTED`
  - `ticket_state=UNUSED`
  - `reason="Missing Ticket in request"`
- 说明候选流量未被 eBPF 误杀，而是继续进入 verifier 后被业务拒绝

#### Case C：Replay -> Redis Decision -> Derived Block
- 第一次真实请求结果：
  - `SUCCESS`
- 第二次 replay 结果：
  - `REJECTED`
  - `reason="Ticket already CONSUMED"`
- verifier 日志同时出现：
  - `Replay detected. Deriving short-term L4 block for source ...`
  - `Derived L4 block signal dispatched ...`
- 控制面日志出现：
  - `[CONTROL] Derived Block Sync from verifier decision: IP ...`
- 说明业务状态判定仍在 verifier / Redis，block 是由 verifier 派生出来的，而非 eBPF 自主生成

#### Case D：Post-Replay Suppression
- 同一来源紧接着重新获取一张新 ticket
- Issuer `8001` 正常签发新票，说明动态 block 未误伤 Issuer
- 但该新请求发往 Verifier `8002` 时，客户端 3 秒超时
- TC trace 连续出现：
  - `[TC DROP] Derived Block: source IP matched short-term L4 blocklist`
- 说明来源级短时 suppress 已在 verifier 入口前生效

### 关键结论
- Day 40 已完成：
  - verifier 仍通过 Redis 状态机作为唯一业务真相源
  - eBPF 不表达票据状态，也不单独伪造业务决策
  - verifier 在命中 `CONSUMED` replay 后，派生来源级短时 L4 block
  - eBPF 仅在 `dport=8002` 入口执行该派生 block
- 因此 Day 40 的“前置验证与状态表联动”已经成立

### 当前说明
- 当前实现的准确语义是：
  - “基于 verifier/Redis 决策派生出的来源级短时 dampening”
  - 而不是“票据状态被同步进 eBPF”
- 这意味着：
  - 同一来源在短时窗口内的后续合法请求也会被 fast-path 抑制
  - 当前属于保守、粗粒度的来源级防御策略

### 附加收获
- Auditor 在本轮联调中已接通
- 日志显示：
  - `Audit Appended ...`
  - `/api/v1/auditor/report` 返回 `200 OK`
- 说明 audit 旁路当前已恢复联动

### 下一步
- 进入 Day 41：前置验证效果测试
- 重点：
  1. 分类统计 eBPF 丢弃数量
  2. 分类统计 verifier 丢弃数量
  3. 统计进入 PIR 数量
  4. 按无票据 / 格式错误 / replay / 正常流量分别测试
  5. 
  ## 2026-04-21

## Day 41：前置验证效果测试完成

### 完成内容
1. **Day 41 统计脚本落地**
   - 新增：
     - `scripts/test_day41_metrics.py`
   - 脚本目标：
     - 在受控顺序下发送四类流量
     - 获取 verifier `/metrics` 的基线与最终值
     - 输出 eBPF / verifier / PIR 三层漏斗效果

2. **测试顺序收口**
   - 当前执行顺序固定为：
     1. 正常流量（5 次）
     2. 无票据流量（5 次）
     3. 静态恶意指纹流量（5 次）
     4. replay 风暴（1 次原始消费 + 5 次 replay）
   - 该顺序的原因是：
     - Day 40 的 derived L4 block 会在 replay 后对同源流量产生短时 suppress
     - 若 replay 提前执行，会污染正常流量统计

3. **客户端观测与服务端统计口径分离**
   - 脚本中同时记录：
     - `total_sent_attempts`
     - `http_responses_received`
   - 同时从 verifier `/metrics` 拉取：
     - `total_requests`
     - `blocked_before_pir`
     - `pir_invoked`
   - 并明确说明：
     - `Reached Verifier (L7)` 为服务端 authoritative count
     - `HTTP Responses Received` 为客户端观测值
     - `eBPF Gateway Drops (Approx)` 为实验室近似值

### 验收结果

#### 1. 正常流量
- 共发送 5 次
- 5 次均返回：
  - `Status: 200`
  - `Decision: SUCCESS`
  - `Reason: PIR execution completed`
- 说明正常流量稳定进入 PIR 路径

#### 2. 无票据流量
- 共发送 5 次
- 5 次均返回：
  - `Status: 200`
  - `Decision: REJECTED`
  - `Reason: Missing Ticket in request`
- 说明候选流量未被 eBPF 误杀，而是稳定在 verifier 业务层被拒绝

#### 3. 静态恶意指纹流量
- 共发送 5 次 raw socket `HACK...` 流量
- 客户端无 HTTP 响应
- 结合最终漏斗统计，说明这类流量主要被 eBPF 前置层拦截

#### 4. replay 流量
- 原始合法消费：
  - `Status: 200`
  - `Decision: SUCCESS`
  - `Reason: PIR execution completed`
- 第 1 次 replay：
  - `Status: 200`
  - `Decision: REJECTED`
  - `Reason: Ticket already CONSUMED`
- 第 2~5 次 replay：
  - 全部 timeout
  - 表明后续 replay 主要被 Day 40 的 eBPF derived block 提前压制

### 最终漏斗统计
脚本最终输出为：

- `Total Traffic Sent Attempts = 21`
- `HTTP Responses Received = 12`
- `Reached Verifier (L7) = 12`
- `Verifier Logic Blocks = 6`
- `Penetrated to PIR = 6`
- `eBPF Gateway Drops (Approx) = 9`

### 结果解释
这组数字可解释为：

- 总共 21 次流量尝试
- 其中 12 次到达 verifier
- 到达 verifier 的 12 次中：
  - 6 次被 verifier 逻辑拒绝
    - 5 次无票据
    - 1 次首个 replay
  - 6 次成功进入 PIR
    - 5 次正常流量
    - 1 次 replay 原始消费
- 剩余 9 次近似归入 eBPF 前置拦截
  - 5 次静态恶意指纹
  - 4 次后续 replay

### 关键结论
- Day 41 已完成前置验证效果测试
- 当前两级防线的漏斗效果已被验证：
  - 正常流量主要进入 PIR
  - 无票据流量主要在 verifier 被拒绝
  - 静态恶意指纹流量主要在 eBPF 被拦截
  - replay 流量中，首个 replay 由 verifier 识别，后续 replay 大多被 eBPF derived block 抑制
- 因而 Day 41 的核心目标已达到：
  - 可以分类观察 eBPF 丢弃数量
  - 可以分类观察 verifier 丢弃数量
  - 可以观察进入 PIR 数量

### 当前说明
- `eBPF Gateway Drops (Approx)` 不是精密网络测量值，而是实验室近似值：
  - `Total Sent Attempts - Reached Verifier`
  - 默认假设外部网络无额外丢包
- `Reached Verifier (L7)` 仍是当前最可信的服务端 authoritative funnel 统计口径

### 下一步
- 进入 Day 42：本周重构与留档
- 重点：
  1. 画两级前置验证图
  2. 写 fast path / full path 文档
  3. 收口 eBPF 与 verifier 的职责边界说明
  4. 
  
## 2026-04-21

## Day 42：本周重构与留档完成

### 背景
经过 Day 36–41 的连续实现与联调，当前两级前置验证架构已经具备：
- eBPF / TC 前置轻量拦截
- Verifier / Redis 完整业务验证与状态推进
- Derived Block 的来源级短时联动
- Day 41 已验证三层漏斗效果：
  - eBPF 前置层
  - verifier 业务拒绝层
  - PIR 执行层

因此 Day 42 的重点不再是新增功能，而是将本周已经收口的架构正式文档化，形成可维护的设计留档。

### 完成内容
1. **新增专项架构文档**
   - 新增：
     - `docs/architecture_defense.md`
   - 该文档专门用于承载两级前置验证架构说明，而不再将此类内容混入 `devlog.md`

2. **完成两级前置验证总览图**
   - 在 `docs/architecture_defense.md` 中新增 Mermaid 架构图
   - 图中明确表达：
     - Client -> eBPF / TC Gateway -> Uvicorn / FastAPI -> Verifier -> Redis / PIR
     - Replay Detected 后由 verifier 经 `UDP 9002` 向控制面派发生命周期短的 Derived Block
     - 控制面再同步到 eBPF BPF Map

3. **完成典型联动时序图**
   - 在 `docs/architecture_defense.md` 中新增 Mermaid 时序图
   - 覆盖：
     - 正常请求完整穿透 fast path + full path
     - replay 首次进入 verifier 并命中 `CONSUMED`
     - 后续同源请求在 eBPF fast path 被提前 drop

4. **完成 Fast Path / Full Path 文档收口**
   - 当前文档中已明确：
     - Fast Path（eBPF / TC）是轻量、无业务状态的网络层执行器
     - Full Path（Verifier / Redis / PIR）是完整业务逻辑、密码学校验与状态机中心
   - 并正式写清：
     - eBPF 不进行深层 JSON / HTTP 业务解析
     - eBPF 不理解 Ticket 生命周期
     - Redis 仍是唯一业务状态真相源
     - Derived Block 是 verifier 派生动作，而不是 eBPF 自主业务判断

5. **完成体系化文档互链**
   - 在 `docs/sequence.md` 末尾追加对 `architecture_defense.md` 的引用说明
   - 当前 docs 体系进一步形成互补关系：
     - `ebpf_scope.md`：eBPF 边界
     - `sequence.md`：整体请求时序
     - `architecture_defense.md`：两级前置验证与分层防御

6. **补充 Day 41 漏斗效果文档化**
   - 在 `docs/architecture_defense.md` 中新增“漏斗效果与统计口径”小节
   - 正式记录：
     - 静态恶意指纹流量主要在 eBPF 被拦截
     - 无票据候选流量主要在 verifier 被拒绝
     - replay 首个命中 verifier，后续大多被 eBPF Derived Block 抑制
     - 正常流量穿透前置防线进入 PIR

### 关键结论
- Day 42 已完成本周重构与留档目标：
  - 两级前置验证图已正式落盘
  - fast path / full path 文档已正式落盘
- 当前架构留档已将 Day 36–41 的实现结果系统化整理为一份独立文档
- 后续若继续做 Day 43+ 攻击实验、基线实验与兼容性验证，可直接以该文档作为前置防御架构基准说明

### 当前状态
- 当前两级前置验证体系已经不仅“能运行”，而且已经具备可引用、可扩展、可用于论文/实验说明的正式文档化表达
- Day 42 可视为本周 eBPF 两级架构阶段性收口完成
- 
## 2026-04-21

## Day 43：恶意客户端 replay 攻击完成

### 背景
进入第 7 周后，当前实验重点从“防线搭建”转向“攻击验证”。Day 43 聚焦恶意客户端 replay 攻击，目标是验证在：
1. 单票据重复请求
2. 并发 replay 风暴
两种场景下，系统是否始终只允许一次成功，杜绝双花。

### 完成内容
1. **新增 Day 43 攻击脚本**
   - 新增：
     - `scripts/test_day43_replay_attacks.py`
   - 脚本分为三阶段：
     1. 串行 replay
     2. 20 线程并发 replay storm
     3. 联合防御战果统计

2. **并发攻击脚本工程收口**
   - 在并发阶段加入 `threading.Barrier`
   - 保证 20 个线程尽可能同一时刻统一起跑
   - 对并发请求 payload 做 `deepcopy`
   - 为每个 storm 请求追加唯一 `request_id` 后缀，提升 verifier 日志可读性与排障能力
   - 增加 config 地址检查，避免 `acquire_ticket()` 误打到本地 loopback

3. **串行 replay 验证**
   - 第 1 次合法请求：
     - `HTTP 200 | SUCCESS | State: CONSUMED | Reason: PIR execution completed`
   - 第 2 次 replay：
     - `HTTP 200 | REJECTED | State: CONSUMED | Reason: Ticket already CONSUMED`
   - 第 3 次 replay：
     - `TIMEOUT (Likely dropped by eBPF L4 Dampening)`
   - 说明：
     - verifier / Redis 能正确记住票据已消费
     - Day 40 的 derived L4 dampening 已接上并生效

4. **并发 replay storm 验证**
   - 20 线程统一起跑，对同一 ticket / same SN 发起高并发 replay
   - 最终结果：
     - `SUCCESS = 1`
     - `REJECTED_PENDING = 19`
     - `REJECTED_CONSUMED = 0`
     - `TIMEOUT = 0`
   - 说明：
     - 真正抢到处理权的只有 1 个请求
     - 其余 19 个请求全部被 `PENDING` 状态前沿拦住
     - 未出现第二次成功
     - 未暴露 double spend / race condition

### 结果解释
Day 43 当前的两个 replay 场景说明了两类不同的主导防线：

1. **串行 replay**
   - 第一个 replay 命中 `CONSUMED`
   - 后续请求再被 eBPF derived L4 dampening 压制
   - 因此串行 replay 主要体现：
     - `CONSUMED` 状态机记忆
     - 派生 L4 抑制联动

2. **并发 replay storm**
   - 主导防线不是后置 `CONSUMED`
   - 而是 Redis 原子锁 / `PENDING` 状态
   - 这说明在真正同起跑的并发夹击下，系统最前沿的原子锁已经足以保证：
     - 只允许 1 个请求成功
     - 其余请求在进入完整处理前即被挡住

### 关键结论
- Day 43 已完成恶意客户端 replay 攻击实验
- 当前系统在两种攻击面下均满足验收标准：
  - 单票据重复请求：只允许一次成功
  - 并发 replay 风暴：只允许一次成功
- 未观察到双花成功，也未观察到 race condition 导致的多次成功
- 当前最准确的结论是：
  - 系统已具备“联合防御矩阵下的 replay 抗性”
  - 该矩阵由以下三层共同组成：
    1. Redis 原子锁
    2. verifier 状态机
    3. eBPF derived L4 dampening

### 当前状态
- Day 43 验收通过
- 当前 replay 防御已经不仅停留在“理论设计”，而是通过串行与并发两类恶意客户端攻击验证了实际有效性
- 
## 2026-04-21

## Day 44：批量滥用攻击完成

### 背景
进入第 7 周后，实验重点从“基础防线搭建”转向“攻击实验与承压验证”。Day 44 聚焦客户端批量滥用攻击，目标是验证：
1. 大量合法格式请求对 full path 的承压表现
2. 伪签名 / 错误 binding 等密码学材料滥用请求是否会被 verifier 前置拦截
3. 无票据 / 缺 witness 等候选请求是否会被 verifier 前置拦截
4. PIR backend 是否只承接真正合法的 full path 请求

### 完成内容
1. **新增 Day 44 主压测脚本**
   - 新增：
     - `scripts/test_day44_batch_abuse.py`
   - 脚本支持：
     - `--batch`
     - `--concurrency`
   - 允许逐步提升批量与并发水位，而不需要反复改代码

2. **引入服务端权威指标对照**
   - 在每个 phase 前后抓取 verifier `/metrics`
   - 输出：
     - `total_requests` 增量
     - `blocked_before_pir` 增量
     - `pir_invoked` 增量
   - 因而 Day 44 不再只是客户端返回分类，而是同时具备 verifier 侧 authoritative 对照

3. **完成三阶段批量滥用测试结构**
   - Phase 1：
     - `Valid Ticket Storm (Full Path Stress)`
   - Phase 2：
     - `Crypto Material Abuse (Fake Sigs & Bindings)`
   - Phase 3：
     - `Missing Ticket / Missing Witness Abuse`
   - 各阶段之间增加冷却时间，减少前一轮尾流、队列与 metrics 刷新对后一轮的污染

4. **修复 Phase 2 污染问题**
   - 本轮最关键的工程修复是：
     - Phase 1 与 Phase 2 不再复用同一批 ticket
   - 当前脚本将弹药分成两批：
     - `valid_payloads_phase1`
     - `fresh_payloads_phase2`
   - 因此 Phase 2 现在真正测到的是：
     - 篡改 `sigma` 导致的签名无效拒绝
     - 篡改 `binding_tag` 导致的 binding 一致性失败拒绝
   - 不再像上一轮那样被 `Ticket already CONSUMED` 污染

### 验收结果

#### Phase 1：Valid Ticket Storm (Full Path Stress)
- 测试规模：
  - `100 reqs @ 30 workers`
- 客户端侧结果：
  - `100 / 100` 全部 `200_SUCCESS`
  - `Reason: PIR execution completed`
- 服务端权威指标：
  - `Total Reached Verifier = +100`
  - `Blocked Before PIR = +0`
  - `Penetrated to PIR = +100`
- 性能观察：
  - Duration ≈ `11.06s`
  - Throughput ≈ `9.04 req/sec`
  - Avg Latency ≈ `2952 ms`
- 结论：
  - 当前在该压力档位下，合法 full path 流量可稳定穿透 verifier 并进入 PIR

#### Phase 2：Crypto Material Abuse (Fake Sigs & Bindings)
- 测试规模：
  - `100 reqs @ 30 workers`
- 客户端侧结果：
  - `100 / 100` 全部 `200_REJECTED`
  - 典型拒绝原因为：
    - `Invalid Ticket Signature`
    - `Binding Consistency Check Failed`
- 服务端权威指标：
  - `Total Reached Verifier = +100`
  - `Blocked Before PIR = +100`
  - `Penetrated to PIR = +0`
- 性能观察：
  - Duration ≈ `0.32s`
  - Throughput ≈ `314 req/sec`
  - Avg Latency ≈ `75 ms`
- 结论：
  - 伪签名与错误 binding 请求均在 verifier 前置校验阶段被拦截
  - 未有任何请求进入 PIR
  - 当前“fake ticket abuse”主要由 `sigma` 篡改来代表

#### Phase 3：Missing Ticket / Missing Witness Abuse
- 测试规模：
  - `100 reqs @ 30 workers`
- 客户端侧结果：
  - `100 / 100` 全部 `200_REJECTED`
  - `Reason: Missing Ticket in request`
- 服务端权威指标：
  - `Total Reached Verifier = +100`
  - `Blocked Before PIR = +100`
  - `Penetrated to PIR = +0`
- 性能观察：
  - Duration ≈ `0.30s`
  - Throughput ≈ `328 req/sec`
  - Avg Latency ≈ `74 ms`
- 结论：
  - 无票据 / 缺 witness 候选流量稳定进入 verifier
  - 并被前置业务规则挡在 PIR 之前

### 关键结论
- Day 44 已完成客户端批量滥用攻击与 full path 承压验证
- 当前三类流量的落点已经清晰分层：
  1. **合法流量**：`100%` 进入 PIR
  2. **伪签名 / 错误 binding**：`100%` 在 verifier 前置拦截，`0` 进入 PIR
  3. **无票据 / 缺 witness**：`100%` 在 verifier 前置拦截，`0` 进入 PIR
- 因此当前最准确的结论是：
  - verifier 的 L7 分层防御有效
  - PIR backend 只承接合法 full path 流量
  - 批量 abuse 请求未穿透到 PIR

### 当前状态
- Day 44 验收通过
- 当前 full path 承压基线（在 `100 reqs @ 30 workers` 档位）约为：
  - Throughput ≈ `9 req/sec`
  - Avg Latency ≈ `3s`
- 当前非法但格式合法的 abuse 请求（伪签名 / 错误 binding / 缺票据）能在 verifier 前段逻辑快速拒绝，且不会进入 PIR
- 
## 2026-04-21

## Day 45：恶意 verifier 状态篡改测试完成

### 背景
进入第 7 周后，实验从客户端攻击逐步扩展到“恶意服务组件”场景。Day 45 的重点不再是验证 replay 或批量 abuse，而是验证：
- 当 verifier 本身出现作恶行为时，
- 审计层是否还能发现状态与日志之间的不一致。

当前 Day 45 的主目标是：
1. 模拟 verifier 篡改核销状态
2. 用 Auditor 检查状态与日志一致性
3. 验收：能发现状态不一致

### 完成内容
1. **新增 Day 45 恶意 verifier 测试脚本**
   - 新增：
     - `scripts/test_day45_malicious_verifier.py`
   - 当前脚本支持：
     - 显式打印 Auditor 与 Redis 目标环境
     - 直连 Redis 模拟“内鬼 verifier”篡改状态
     - 通过 Auditor trace 接口进行账本查询与一致性核查

2. **场景 A：幽灵核销（Ghost Consumption）**
   - 测试步骤：
     1. 生成一个合法格式的 64-char hex 风格测试 SN
     2. 直接在 Redis 中将其标记为 `CONSUMED`
     3. 故意跳过对 Auditor 的审计写入
     4. 通过 `GET /api/v1/auditor/trace/{sn}` 发起对账
   - 实际结果：
     - Redis 状态：`CONSUMED`
     - Auditor 返回：`404`
     - 响应体明确提示该 SN 对应的审计记录不存在
   - 结论：
     - 成功通过“Redis 状态 + Auditor 账本”外部对账发现 ghost consumption
     - 这直接满足 Day 45 的主验收要求：
       - 能发现状态与日志不一致

3. **场景 B：承诺篡改（Commitment Tampering）**
   - 当前将该场景视为 Day 46 的预演
   - 测试步骤：
     1. 构造真实 `expected_cq`
     2. 构造被篡改的 `query_commitment`
     3. 向 Auditor 上报被篡改后的审计记录
     4. 再通过 `trace` + `expected_cq` 查询一致性
   - 实际结果：
     - Auditor 写入阶段返回：
       - `HTTP 200`
       - `{"status":"recorded"}`
     - 后续 trace 查询返回：
       - `cq_consistent = false`
   - 结论：
     - Auditor 不仅能发现“有状态无日志”
     - 也能发现“有日志但内容被篡改”的不一致
     - 这为 Day 46 的恶意执行记录 / 审计内容篡改测试提供了直接预演结果

### 关键结论
- Day 45 主验收已通过：
  - 当 verifier 恶意只改 Redis 状态而跳过审计时，
  - 系统能够通过外部对账发现状态与日志不一致
- 当前最准确的 Day 45 收口表述是：
  - Redis 中存在 `CONSUMED` 状态
  - Auditor 中不存在对应审计记录
  - 因而 ghost consumption 可被发现
- 额外收获：
  - Auditor trace 的 `cq_consistent` 字段也具备发现承诺篡改的能力
  - 该结果更适合作为 Day 46 的预热结论

### 当前状态
- Day 45 验收通过
- 当前审计层已证明不只是“存日志”，而是具备最基本的：
  - 状态 / 日志缺失不一致发现能力
  - 审计内容 / 客户端预期不一致发现能力
- 第 7 周实验已从“客户端攻击验证”扩展到“恶意 verifier / 审计对账验证”
- 
## 2026-04-21

## Day 46：恶意服务端伪造执行记录测试完成

### 完成内容
1. **Day 46 恶意审计验收脚本落地**
   - 新增：
     - `scripts/test_day46_malicious_audit.py`

2. **场景 C：跨证据源最小一致性问题发现**
   - 模拟 Redis 中的执行真相为：
     - `CONSUMED`
   - 同时向 Auditor 上报伪造记录：
     - `decision = FAILED`
     - `query_commitment = fake_cq`
   - 在 `GET /api/v1/auditor/trace/{sn}` 中传入：
     - `expected_cq = real_cq`
   - 成功识别两类矛盾：
     - 状态矛盾：
       - Redis 真相为 `CONSUMED`
       - 账本记录为 `FAILED`
     - 载荷矛盾：
       - 账本中的 `query_commitment` 与 `expected_cq` 不一致

3. **场景 D：离线账本篡改发现**
   - 先生成一条合法审计记录
   - 复制账本副本
   - 在副本中按 `SN` 精确定位目标记录
   - 篡改该记录的：
     - `query_commitment`
   - 使用本地完整性校验器重放 Day 25 HMAC 链验证
   - 成功发现篡改导致的链断裂

4. **完整性验证器收口**
   - 当前 `_verify_integrity_day25()` 已严格对齐 Day 25 契约
   - MAC payload 顺序固定为：
     - `sn|query_commitment|decision|timestamp_ms|prev_hash`
   - 同时执行两类检查：
     1. 链连续性检查：
        - 当前记录 `prev_hash == 上一条记录 entry_mac`
     2. 内容完整性检查：
        - 重算 `entry_mac` 并与账本值比较

### 验收结果
执行：
- `python scripts/test_day46_malicious_audit.py`

结果：
1. 场景 C 通过：
   - 成功发现跨证据源最小一致性问题
   - 输出：
     - `状态矛盾发现=True`
     - `载荷矛盾发现=True`

2. 场景 D 通过：
   - 成功发现离线账本链断裂
   - 输出：
     - `契约级 HMAC 校验失败，篡改被识破`

3. auditor 服务侧日志确认：
   - `POST /api/v1/auditor/report` 返回 `200 OK`
   - `GET /api/v1/auditor/trace/{sn}?expected_cq=...` 返回 `200 OK`

### 关键结论
- Day 46 目标已完成：
  - 模拟服务端伪造执行记录或错误关联 `c_q`
  - Auditor 证据与 Redis 执行证据可联合发现最小一致性问题
- Day 25 的链式 HMAC 审计账本仍有效：
  - 离线篡改 `query_commitment` 会被识别
- 当前原型已具备：
  - 最小一致性发现能力
  - 最小篡改留痕能力

### 当前边界 / 备注
- 当前 Day 46 验证的是：
  - 最小争议验证
  - 最小执行一致性发现
- 当前尚未扩展为：
  - 完整 authenticated PIR
  - 完整 verifiable PIR
  - 完整执行正确性证明机制

### 下一步
- 进入 Day 47：Authenticated / Verifiable PIR 兼容性验证
- 目标是验证 access-control 层与 APIR / VPIR 风格执行路径可共存，而不是重写整套 PIR 正确性证明框架
- 
## 2026-04-21

## Day 47：Authenticated / Verifiable PIR 兼容性验证完成

### 完成内容
1. **PIR 结果模型最小扩展**
   - 在 `common.models.PIRResultPayload` 中新增：
     - `apir_proof: Optional[str]`
   - 当前该字段定位为：
     - Generic APIR / VPIR style cryptographic proof blob
   - 保持其为可选兼容字段，不改变主链核心结果字段：
     - `result_string`
     - `mapped_index`
     - `recovered_val`

2. **pir_server 最小兼容性集成**
   - 在 `services/pir_server/main.py` 中新增 mock proof 返回
   - proof 当前绑定材料为：
     - `mapped_index`
     - `recovered_val`
     - `result_string`
   - 当前生成方式仅用于 Day 47 兼容性验证：
     - 不是完整 APIR / VPIR 证明实现

3. **verifier 透明透传收口**
   - 在 `services/verifier/main.py` 成功路径中提取：
     - `apir_proof`
   - verifier 当前行为为：
     - 仅透明透传 proof blob
     - 不参与 proof 语义验证
   - 并增加日志说明：
     - verifier forwards it without semantic validation

4. **带 Proof 的最小兼容性验证**
   - 新增：
     - `scripts/test_day47_apir_compat.py`
   - 客户端完整走通：
     - ticket acquisition
     - binding
     - verifier access-control
     - pir_server execution
     - proof-bearing response return
   - 成功验证：
     - proof 字段可透明透传
     - 客户端可按 mock 契约重算 proof 与响应上下文一致

5. **Proof 缺失时的向下兼容性 smoke test**
   - 补充完成：
     - proof 缺失场景兼容性验证
   - 实际结果表明：
     - `apir_proof = None`
     - 主链仍可正常返回核心结果
     - verifier 未将 proof 变为成功路径强依赖
     - Optional Proof 平滑缺失

### 验收结果
Day 47 共完成两类验收：

1. **带 Proof 的兼容性验证**
   - access-control 主链不会阻断或破坏 APIR / VPIR 风格 proof 字段透传
   - proof 可与响应上下文保持 mock 契约一致

2. **Proof 缺失时的向下兼容性验证**
   - 核心结果字段仍可正常解析
   - 主链未被 Proof 字段绑死
   - verifier 对 Proof 缺失保持向下兼容

### 关键结论
- Day 47 目标已完成：
  - 完成最小兼容性集成
  - 完成最小兼容性验证
  - 证明 access-control 层可与 APIR / VPIR 风格执行路径共存，不构成最小接口层冲突

- 当前 Day 47 的准确定位是：
  - proof-bearing PIR response 的最小兼容性验证
  - 不是完整 authenticated PIR / verifiable PIR 证明实现

### 当前边界 / 备注
- verifier 当前仍不是 proof verifier
- pir_server 当前返回的是 mock proof blob
- 当前系统尚未实现：
  - 真实 APIR 认证证明验证
  - 真实 VPIR 执行正确性证明验证
  - 数据库真实性 / 输出完整性的完整密码学证明链

### 下一步
- 进入 Day 48：基线实验 1
- 目标：
  - 无任何前置保护
  - 直接打 PIR backend
  - 记录 latency / throughput / CPU / memory
  - 
  ## 2026-04-21

## Day 48：基线实验 1 完成

### 完成内容
1. **Day 48 基线压测脚本落地**
   - 新增：
     - `scripts/test_day48_baseline_1.py`

2. **实验路径固定**
   - 当前 Day 48 严格绕过 verifier
   - 直接压测：
     - `http://<server_ip>:8003/api/v1/pir/query`
   - 当前实验定位为：
     - 无 access-control 前置保护的 PIR 服务基线
   - 注意：
     - 该实验压测的是当前 `pir_server` 服务入口及其后端集成路径
     - 不是纯 Go 引擎裸进程基线

3. **压测脚本统计口径收口**
   - 当前脚本固定使用：
     - `aiohttp`
     - `asyncio.Semaphore`
     - `TCPConnector(limit=concurrency)`
   - 当前载荷模式为：
     - 固定 `query_payload`
   - 当前指标统计包括：
     - 总耗时
     - 发射吞吐量
     - 成功吞吐量
     - 成功请求延迟：
       - `Avg`
       - `P95`
       - `P99`
       - `Max`
       - `Min`
     - Host 级资源监控：
       - CPU `Avg / Max`
       - Memory `Avg / Max`
     - 状态 / 异常分布：
       - `200`
       - `timeout`
       - `client_error`
       - `unknown_error`

4. **第一轮基线实验参数**
   - 执行：
     - `python scripts/test_day48_baseline_1.py 127.0.0.1 --requests 1000 --concurrency 100`

### 运行结果
本轮结果如下：

- 总耗时：
  - `13.05 s`
- 发射吞吐量：
  - `76.65 req/s`
- 成功吞吐量：
  - `76.65 req/s`
- 成功请求延迟：
  - `Avg = 1296.28 ms`
  - `P95 = 1470.34 ms`
  - `P99 = 1522.16 ms`
  - `Max = 1717.16 ms`
  - `Min = 981.88 ms`
- Host CPU：
  - `Avg = 89.7%`
  - `Max = 100.0%`
- Host Memory：
  - `Avg = 40.7%`
  - `Max = 43.9%`
- 状态分布：
  - `HTTP 200 = 1000`
  - 无 `timeout / client_error / unknown_error`

### 关键结论
- Day 48 目标已完成：
  - 无任何前置保护
  - 直接打 PIR 服务入口
  - 成功记录 latency / throughput / CPU / memory

- 当前第一轮基线结果表明：
  - 当前集成路径下的 PIR 服务基线吞吐约为：
    - `76.65 req/s`
  - 在 `concurrency=100` 下：
    - 系统已明显逼近 CPU 主导瓶颈区间
  - 当前延迟分布相对集中：
    - 未出现明显长尾失控
  - 当前内存占用较平稳：
    - 瓶颈更偏向 CPU / 请求处理能力，而不是内存失控

### 当前边界 / 备注
- 当前 CPU / Memory 指标为 Host 级别，不是 `pir_server` 单进程级别
- 当前实验使用固定单载荷，不代表多查询分布下的全部结论
- 当前 Day 48 结果适合作为后续 Day 49 / Day 50 对照基线

### 下一步
- 进入 Day 49：基线实验 2
- 目标是对比加入用户态 access-control 后的性能与资源变化
- 
## 2026-04-21

## Day 49：基线实验 2 完成

### 完成内容
1. **Day 49 L7 防御基线脚本落地**
   - 新增：
     - `scripts/test_day49_baseline_2.py`

2. **实验边界固定**
   - 当前 Day 49 严格固定为：
     - 只有用户态 verifier
     - 无 eBPF
   - 压测目标为：
     - `POST /api/v1/verifier/execute`

3. **模式拆分收口**
   - 当前已将 Day 49 拆成三类基线：
     1. `schema`
        - 入口校验层 (FastAPI / 请求结构缺失) 基线
     2. `crypto`
        - 密码学校验 / 业务拒绝路径基线
     3. `replay`
        - 状态机 / Redis 并发锁 IO 基线

4. **脚本口径收口**
   - 当前脚本已支持：
     - 预生成攻击载荷
     - 解析 verifier 业务返回：
       - `200_SUCCESS`
       - `200_REJECTED`
       - `422_VALIDATION_ERR`
     - 统计：
       - 总耗时
       - 攻击发起吞吐量
       - 防御成功吞吐量
       - 全响应混合延迟：
         - `Avg`
         - `P95`
         - `P99`
         - `Max`
       - Host CPU / Memory
       - 防御结果分布
   - `crypto` 模式已修正为使用当前 epoch，避免被过期票据快拒绝带偏
   - `replay` 模式中的母票申请属于预加载阶段，不计入压测时长

### 运行结果

#### 1. Schema 模式
执行：
- `python scripts/test_day49_baseline_2.py 127.0.0.1 --mode schema --requests 500 --concurrency 100`

结果：
- 总耗时：
  - `0.49 s`
- 攻击发起吞吐量：
  - `1017.76 req/s`
- 防御成功吞吐量：
  - `1017.76 req/s`
- 全响应混合延迟：
  - `Avg = 83.74 ms`
  - `P95 = 107.91 ms`
  - `P99 = 114.29 ms`
  - `Max = 114.91 ms`
- Host CPU：
  - `Avg = 0.0%`
  - `Max = 0.0%`
- 防御结果分布：
  - `500 x 200_REJECTED`

结论：
- schema 缺失字段请求在当前契约下主要落入业务拒绝路径
- 当前是三类模式中最轻的一条防御路径

#### 2. Crypto 模式
执行：
- `python scripts/test_day49_baseline_2.py 127.0.0.1 --mode crypto --requests 500 --concurrency 100`

结果：
- 总耗时：
  - `0.68 s`
- 攻击发起吞吐量：
  - `736.44 req/s`
- 防御成功吞吐量：
  - `736.44 req/s`
- 全响应混合延迟：
  - `Avg = 119.06 ms`
  - `P95 = 143.40 ms`
  - `P99 = 146.83 ms`
  - `Max = 153.32 ms`
- Host CPU：
  - `Avg = 43.0%`
  - `Max = 85.9%`
- 防御结果分布：
  - `500 x 200_REJECTED`

结论：
- 相比 schema，密码学校验 / 材料检查路径明显更重
- 但仍能在较高吞吐下稳定拒绝全部伪造请求

#### 3. Replay 模式
执行：
- `python scripts/test_day49_baseline_2.py 127.0.0.1 --mode replay --requests 500 --concurrency 100`

结果：
- 总耗时：
  - `0.70 s`
- 攻击发起吞吐量：
  - `710.54 req/s`
- 防御成功吞吐量：
  - `710.54 req/s`
- 全响应混合延迟：
  - `Avg = 119.02 ms`
  - `P95 = 155.44 ms`
  - `P99 = 168.39 ms`
  - `Max = 684.23 ms`
- Host CPU：
  - `Avg = 41.4%`
  - `Max = 82.8%`
- 防御结果分布：
  - `499 x 200_REJECTED`
  - `1 x 200_SUCCESS`

结论：
- replay 结果与系统语义完全一致：
  - 仅 1 次成功
  - 其余请求全部被拒绝
- 当前 replay 路径与 crypto 路径成本接近，但存在单点长尾
- 整体分布仍稳定，未出现系统失控

### 关键结论
- Day 49 目标已完成：
  - 已获得“只有用户态 verifier、无 eBPF”条件下的第一版 L7 防御基线
- 与 Day 48 相比，当前结果表明：
  - 用户态 verifier 的拒绝成本显著低于无前置保护直打 PIR 服务入口
- 当前三类模式形成明显成本梯度：
  - `schema` 最轻
  - `crypto` 更重
  - `replay` 与 `crypto` 接近，且保持正确防重放语义

### 当前边界 / 备注
- 当前 CPU / Memory 指标仍为 Host 级别，不是单进程级别
- `schema` 模式当前主要落入 `200_REJECTED`，而非 `422`
- 当前 Day 49 结果适合作为 Day 50 / eBPF 对比前的用户态基线

### 下一步
- 进入 Day 50：基线实验 3 / 后续对照实验
- 目标是在当前 Day 48 / Day 49 基线基础上继续完成有 eBPF 参与条件下的比较
- 
## 2026-04-21

## Day 50：完整方案实验完成

### 完成内容
1. **Day 50 全链路协同防御脚本落地**
   - 新增：
     - `scripts/test_day50_full_solution.py`

2. **localhost L4 block 豁免收口**
   - 为避免直接删除 Day 40 留下的开发保险丝
   - 在 `services/verifier/main.py` 中将 localhost 豁免改为配置开关：
     - `ebpf.allow_localhost_block`
   - 该开关仅用于 Day 50 实验 / 特殊联调场景
   - 默认仍应关闭

3. **完整方案实验边界固定**
   - 当前 Day 50 覆盖完整主链：
     - blind ticket
     - binding
     - consume
     - verifier
     - eBPF / TC
     - audit
   - 当前攻击模式固定为：
     - 1 张真票为母本
     - 高并发 replay flood

4. **脚本统计口径收口**
   - 当前脚本统计：
     - 总压测耗时
     - 客户端平均观测耗时
     - 综合防御成功率
     - L7 业务拒绝占比
     - L4 疑似拦截占比
     - 成功穿透占比
     - Host CPU / Memory
     - 客户端视角状态分布
   - 当前明确：
     - `L4_OR_NET_TIMEOUT / CONN_ERR`
       仅作为与 L4 丢弃机制预期一致的近似证据
     - 不直接替代 eBPF/TC trace 证据

5. **服务端证据闭环要求固定**
   - Day 50 验收必须额外核对：
     1. verifier 日志：
        - `Replay detected. Deriving short-term L4 block for source...`
        - `Derived L4 block signal dispatched for IP ...`
     2. tc_gateway / eBPF trace：
        - `[TC DROP] Derived Block: source IP matched short-term L4 blocklist`
     3. auditor / pir_server：
        - 仅出现极少量早期真实触达事件

### 运行结果

#### 1. 本机打本机实验（弱协同）
先前在本机打本机条件下：
- 客户端侧结果主要为：
  - `1999 x 200_REJECTED`
  - `1 x L4_OR_NET_TIMEOUT`
- 说明：
  - 完整方案主链已跑通
  - L7 为主承担方
  - L4 仅弱介入

#### 2. 远端客户端打服务器实验（正式结果）
执行：
- `python scripts/test_day50_full_solution.py 119.45.48.193 --requests 5000 --concurrency 50`

结果：
- 总压测耗时：
  - `143.11 s`
- 客户端平均观测耗时：
  - `1426.06 ms`
- 综合防御成功率：
  - `99.98%`
- 分层占比：
  - `L7 业务拒绝占比 = 5.50%`
  - `L4 疑似拦截占比 = 94.48%`
  - `成功穿透占比 = 0.02%`

客户端状态分布：
- `4724 x L4_OR_NET_TIMEOUT`
- `275 x 200_REJECTED`
- `1 x 200_SUCCESS`

### 服务端侧证据
1. **Verifier**
   - 出现：
     - `Request ... REJECTED: Ticket already CONSUMED`
     - `Replay detected. Deriving short-term L4 block for source: 220.178.180.101`
     - `Derived L4 block signal dispatched for IP 220.178.180.101`

2. **tc_gateway / eBPF**
   - trace 中出现多条：
     - `[TC DROP] Derived Block: source IP matched short-term L4 blocklist`

3. **pir_server**
   - 仅出现 1 次真实查询执行

4. **auditor**
   - 仅出现极少量早期真实触达事件
   - 当前日志中仅见 1 条追加记录

### 关键结论
- Day 50 目标已完成：
  - 完整方案实验已跑通
  - 已验证 `blind ticket + binding + consume + verifier + eBPF + audit` 的协同闭环

- 当前正式结果表明：
  - 系统已形成：
    - `L7 verifier -> derived block dispatch -> L4 eBPF/TC drop`
      的协同防御路径
  - replay flood 下仅允许 1 次成功执行
  - 后续大部分流量已由 L4 层接管抑制
  - 后续流量未继续大规模进入高开销 PIR 路径

- 与本机打本机实验相比：
  - 远端部署条件更能放大 derived block 生效后的 L4 接管效果
  - 因而远端实验结果更适合作为 Day 50 正式留档结论

### 当前边界 / 备注
- 当前客户端 `L4_OR_NET_*` 仍属于近似证据，需与 verifier / tc_gateway / auditor 三侧日志联合解释
- verifier 日志中同一来源可能重复派发 block，后续可考虑做控制面去重优化
- 当前 CPU / Memory 指标若仅在客户端本机采集，则更多反映客户端宿主机视角，不代表服务端进程独占资源

### 下一步
- Day 48 / Day 49 / Day 50 三组实验现已形成完整对照链：
  1. 无前置保护直打 PIR 服务入口
  2. 只有用户态 verifier
  3. 完整方案：L7 + L4 协同防御
- 后续可进入总结、对照分析与论文/
- 
## 2026-04-22

## Day 51：消融实验完成

### 完成内容
1. **Day 51 消融配置收口**
   - 在 `configs/common/base.yaml` 中新增：
     - `ablation.disable_binding`
     - `ablation.disable_consume_lock`
     - `ablation.disable_epoch`
     - `ablation.disable_admission`

2. **Issuer / Verifier 消融切点落地**
   - 在 `services/issuer/main.py` 中接入：
     - `disable_admission`
   - 在 `services/verifier/main.py` 中接入：
     - `disable_binding`
     - `disable_consume_lock`
     - `disable_epoch`

3. **Day 51 消融攻击脚本落地**
   - 新增：
     - `scripts/test_day51_ablation.py`
   - 当前脚本支持四类单项攻击：
     1. `admission`
     2. `binding`
     3. `replay`
     4. `epoch`

4. **实验方法约束收口**
   - 当前 Day 51 已明确：
     - 一次只开启一个 `disable_*` 开关
     - 一次只运行对应单项攻击
     - `--attack all` 仅供快速联调，不用于正式消融结论留档

### 运行结果

#### 1. Admission 消融
执行条件：
- `disable_admission=true`

攻击方法：
- 构造伪造 challenge HMAC
- 不执行真实 PoW
- 直接提交虚假 `admission_proof` 申请盲签

结果：
- 攻击成功
- Issuer 仍成功签发票据

结论：
- 关闭 admission 后，Issuer 不再验证：
  - challenge HMAC
  - PoW
  - burn semantics
- 因而伪造 proof 亦可成功骗取盲签票据
- 说明 admission 防线对“无成本恶意发票”具备独立贡献

#### 2. Binding 消融
执行条件：
- `disable_binding=true`

攻击方法：
- 先获取一张真实票据
- 合法绑定查询载荷 `SAFE_QUERY`
- 再充当中间人，将 `query_payload` 篡改为恶意载荷后提交 verifier

结果：
- 攻击成功
- verifier 接受并执行了被篡改的请求载荷

结论：
- 关闭 binding 后，请求载荷与票据之间的绑定关系消失
- 中间人篡改攻击成立
- 说明 binding 防线对“请求完整性与不可篡改性”具备独立贡献

#### 3. Consume 消融
执行条件：
- `disable_consume_lock=true`

攻击方法：
- 获取 1 张真实票据
- 对同一载荷并发发起 15 次请求

结果：
- 15 个请求全部成功执行

结论：
- 关闭 consume 后，不仅原子锁失效
- 同时状态机消费语义整体被旁路
- 因而同一票据可被并发重复消费
- 说明 consume / 状态机防线对“防重放与一次性消费”具备独立贡献

#### 4. Epoch 消融
执行条件：
- `disable_epoch=true`

攻击方法：
- 获取一张真实合法票据并完成绑定
- 通过等待方式让票据自然过期
- 过期后原样重新提交请求

结果：
- 攻击成功
- verifier 接受了已自然过期的合法旧票

结论：
- 关闭 epoch 后，真实旧票在过期后仍可继续使用
- 旧票囤积与延迟使用攻击成立
- 说明 epoch 时间窗对“限制票据时间有效性”具备独立贡献

### 关键结论
- Day 51 目标已完成：
  - 已对 admission、binding、consume、epoch 四条防线逐项消融并验证结果
- 当前实验表明：
  - 去掉任意一条机制，都会暴露对应攻击面
- 四条机制对应的独立安全贡献可总结为：
  - admission：
    - 防无成本伪造准入 / 恶意签票
  - binding：
    - 防中间人篡改请求载荷
  - consume：
    - 防并发重放与多次消费
  - epoch：
    - 防旧票囤积与延迟使用

### 当前边界 / 备注
- 当前 Day 51 的 admission 消融语义是：
  - 伪造 proof 亦可签票
  - 不是“完全无 admission_proof 字段也可签票”
- 当前 epoch 消融实验验证的是：
  - 真实票据自然过期后仍可继续被接受
  - 不是“篡改 epoch_id 后伪造旧票”
- 当前 `--attack all` 仅适用于快速连通性检查
- 正式结论仅采用逐项单开关结果

### 下一步
- 进入第 8 周后续工作：
  - 细粒度评估
  - 复现实验
  - 论文对齐
- 当前 Day 48 / Day 49 / Day 50 / Day 51 已形成：
  - 基线
  - 完整方案
  - 消融验证
  
## 2026-04-22

## Day 52：自动统计脚本完成

### 完成内容
1. **统一自动评估入口落地**
   - 新增：
     - `scripts/run_eval_suite.py`
   - 当前脚本统一产出：
     - 微基准 (Part A)
     - 主路径性能 sweep (Part B)
     - 资源保护指标 (Part C)
   - 输出文件：
     - `results/eval_report_day52.json`

2. **微基准层收口**
   - 当前已纳入：
     - `client_solve_pow_d12`
     - `issuer_verify_admission_logic`
     - `blind_issue_sign`
     - `client_unblind_signature`
     - `verifier_verify_ticket_sig`
     - `binding_compute_H_q`
     - `binding_compute_b`
     - `binding_verify`
     - `verifier_redis_try_lock`
     - `ebpf_kernel_drop_estimate`
   - 当前 admission 微基准已修正为使用真实配置中的 `issuer.hmac_secret`
   - 当前 binding verify 微基准已修正为使用语义一致的 `binding_tag_valid`

3. **主路径 sweep 层收口**
   - 当前已分别统计：
     - `raw_pir_by_concurrency`
     - `protected_pir_by_concurrency`
     - `protected_vs_raw_delta`
   - 当前并发 sweep 档位为：
     - `1 / 10 / 30 / 50`
   - 当前已修正：
     - Protected Path 每个并发档位重新装填独立真票
     - 不再复用一次性票据，避免统计失真

4. **资源保护指标层收口**
   - 当前已统计：
     - `blocked_before_compute_ratio`
     - `replay_interception_rate`
     - `pir_invocation_reduction`
   - 当前已修正：
     - abuse 测试复用单个 `ClientSession`
     - `pir_invocation_reduction` 改为 verifier metrics 前后快照差值
   - 当前不再使用不可靠的客户端 CPU 差值去伪装 backend CPU saved

5. **测算声明与边界说明收口**
   - 当前 JSON `notes` 中已明确：
     - `backend_cpu_saved` 未在该脚本中直接实测，而由 `pir_invocation_reduction` 作为业务代理指标
     - `verifier_reject_path_latency_ms` 为接口级近似，包含 HTTP / FastAPI / Pydantic 开销
     - `ebpf_kernel_drop_estimate` 为 estimated constant，不是动态实测值

### 跑分方式
- 当前 `run_eval_suite.py` 在本地运行
- issuer / verifier / pir_server / auditor / tc_gateway 等服务运行在云服务器
- 因此当前宏观结果反映的是：
  - 远端部署下的真实端到端表现
  - 而非纯本机 loopback 路径

### 代表性结果

#### 1. 微基准
- `client_solve_pow_d12 = 15.4126 ms`
- `issuer_verify_admission_logic = 0.0150 ms`
- `blind_issue_sign = 24.1786 ms`
- `client_unblind_signature = 0.4150 ms`
- `verifier_verify_ticket_sig = 0.1630 ms`
- `binding_compute_H_q = 0.0010 ms`
- `binding_compute_b = 0.0028 ms`
- `binding_verify = 0.0109 ms`
- `verifier_redis_try_lock = 0.2428 ms`
- `ebpf_kernel_drop_estimate = 0.0015 ms (estimated)`

#### 2. Raw PIR 主路径
- `C=1`: `25.79 TPS`, `38.72 ms`
- `C=10`: `81.85 TPS`, `114.72 ms`
- `C=30`: `81.56 TPS`, `312.00 ms`
- `C=50`: `82.42 TPS`, `578.49 ms`

结论：
- 当前无保护 PIR 路径在约 `80 TPS` 左右趋于饱和
- 并发继续提高时吞吐不再显著增长，但延迟明显上升

#### 3. Protected Path
- 当前每个 sweep 档位均重新装填独立真票
- 贴出的代表性结果：
  - `Success Count = 50/50`
  - `TPS = 9.74`
  - `Latency = 4010.77 ms`

结论：
- 当前 Protected Path 反映的是完整受保护合法主链的端到端成本
- 不能直接等同于“verifier 单独增加的耗时”
- verifier 纯 L7 reject 路径应结合：
  - `verifier_reject_path_latency_ms = 22.9 ms`

#### 4. 资源保护
- `Blocked-before-compute Ratio = 99.90%`
- `Replay Interception Rate = 99.90%`
- `PIR Invocation Reduction = 99.90%`

结论：
- 当前 replay flood 下，仅有 `1` 次真正成功穿透
- 绝大部分流量被挡在高开销 PIR 计算之前
- `PIR Invocation Reduction` 当前可作为 backend 资源节省的业务代理指标

### 关键结论
- Day 52 目标已完成：
  - 统一自动统计脚本已落地
  - 已能自动生成细粒度组件开销、主路径 sweep、资源保护指标
  - 已能输出结构化 JSON 结果供后续论文表格/图表使用

- 当前 Day 52 的准确定位是：
  - 第 8 周细粒度评估与论文对齐的统一跑分入口
  - 不是一个严格意义上的内核 profiling 工具

### 当前边界 / 备注
- `ebpf_kernel_drop_estimate` 为 estimated，不是直接动态实测
- `verifier_reject_path_latency_ms` 为接口级近似
- `pir_invocation_reduction` 为 backend CPU saved 的业务代理指标
- `issuer_verify_admission_logic` 当前测量的是 in-process verify logic，而不是完整 admission request RTT

### 下一步
- 进入第 8 周后续工作：
  - Day 53：复现实验 / 结果复查
  - Day 54：论文表格与图表对齐
  - Day 55+：总结与最终收口
  - 
  ## 2026-04-22

## Day 53：关键实验复现完成

### 完成内容
1. **关键实验复现与归档脚本落地**
   - 新增：
     - `scripts/run_and_archive_experiments.sh`

2. **Day 53 脚本定位收口**
   - 当前脚本定位为：
     - 半自动关键实验复现与证据归档 (Artifact Snapshot)
   - 当前执行前提已明确：
     - 必须在承载 issuer / verifier / pir_server / auditor 的同一台云服务器上执行
   - 当前不再伪装成“完全无人值守一键复现器”

3. **代码状态快照已固化**
   - 当前归档中已保存：
     - `commit_hash.txt`
     - `git status -s`
     - `git diff --stat`
     - `working_tree.diff`

4. **配置快照已分阶段固化**
   - 当前已保存：
     - `base_at_script_start.yaml`
     - `base_ablation_admission.yaml`
     - `base_ablation_binding.yaml`
     - `base_ablation_consume.yaml`
     - `base_ablation_epoch.yaml`
     - `base_benchmark_clean.yaml`
   - 这意味着：
     - Day 51 每一轮单项消融的实际配置均可追溯
     - Day 52 benchmark 的全甲干净配置也可追溯

5. **运行清单与结果留档已固化**
   - 当前已保存：
     - `manifest.txt`
     - `ablation_admission.log`
     - `ablation_binding.log`
     - `ablation_consume.log`
     - `ablation_epoch.log`
     - `eval_suite_output.log`
     - `eval_report_day52.json`

6. **服务器端日志证据已提取**
   - 当前已保存：
     - `issuer_tail.log`
     - `verifier_tail.log`
     - `pir_server_tail.log`
     - `auditor_tail.log`

7. **最终 tarball 已生成**
   - 归档文件：
     - `results/PIR_Abuse_Control_Artifacts_20260422_111114.tar.gz`

### 关键结论
- Day 53 目标已完成：
  - 已重跑关键实验
  - 已固定并保存中间配置
  - 已保存 commit hash、config、log、JSON 结果与工作区 diff
- 当前项目已形成可复查、可追溯的 artifact snapshot
- Day 48–53 的基线、完整方案、消融、自动统计、复现归档链条现已闭合

### 当前边界 / 备注
- 当前 Day 53 脚本仍属于“半自动”归档脚本：
  - 配置切换与服务重启仍需人工配合
- 但当前已经足以支持：
  - 结果复核
  - 论文附录引用
  - artifact 级证据封存

### 下一步
- 进入第 8 周后续阶段：
  - Day 54：论文表格与图表对齐
  - Day 55：实验结论与章节收口
  - Day 56：最终总结与答辩/汇报材料准备
  - 
  
## 2026-04-23

## Day 56：完整演示日完成

### 完成内容
1. **最终演示控制台落地**
   - 新增：
     - `scripts/demo_day56_showcase.py`
   - 当前脚本定位为：
     - Master Demo CLI
     - 面向答辩 / 汇报 / 录屏的统一交互式演示入口

2. **演示剧本统一收束**
   - 当前已将 6 个核心场景统一到同一套菜单式控制台：
     1. 正常请求（Happy Path）
     2. replay 攻击（L4/L7 协同拦截）
     3. binding 篡改
     4. 幽灵核销争议（Ghost Consumption）
     5. 账本伪造争议（Record Forgery）
     6. 资源保护展示（Computation-DoS Flood）

3. **脚本稳定性增强**
   - 当前已补充：
     - 场景 1 / 3 / 5 的 HTTP `status_code` guard
     - 场景 2 的 timeout / connection error 双路径兼容
     - 场景 4 的 Redis 状态与 Auditor 响应码可视化
     - 场景 5 的写账本 / 查争议异常处理
   - 当前已将 `slow_print` 节奏收口为：
     - `delay = 0.01`
   - 当前已将洪峰展示参数收口为演示友好档位：
     - `300 requests`
     - `30 concurrency`

### 实际演示结果

#### 1. 正常请求（Happy Path）
结果：
- 票据获取、binding、verifier、PIR 执行均成功
- 返回：
  - `decision = SUCCESS`
  - 合法 `recovered_val`
- 演示价值：
  - 证明完整主链可正常流转

#### 2. Replay 攻击
结果：
- 第一枪：
  - `SUCCESS`
- 第二枪：
  - `REJECTED | Ticket consumed`
- 第三枪：
  - 客户端侧出现符合 L4 eBPF 前置丢弃预期的 timeout / connection error

演示价值：
- 清晰展示：
  - 一次成功消费
  - 其后由 L7 与 L4 形成协同抑制

#### 3. Binding 篡改
结果：
- 篡改 `query_payload` 后返回：
  - `REJECTED | Binding Check Failed`

演示价值：
- 清晰展示：
  - 票据与请求绑定关系仍然有效
  - 中间人篡改会被拒绝

#### 4. 幽灵核销争议（Ghost Consumption）
结果：
- Redis 实际状态：
  - `CONSUMED`
- Auditor 返回：
  - `404`
- 最终展示：
  - 成功识别 Redis 与审计账本的跨源矛盾

演示价值：
- 清晰展示：
  - 恶意 verifier 单方面“幽灵核销”可被独立 Auditor 缺席记录识别

#### 5. 账本伪造争议（Record Forgery）
结果：
- 伪造记录被追加
- 用户使用真实 `expected_cq` 发起争议
- 最终检测到：
  - `cq_consistent = false`

演示价值：
- 清晰展示：
  - 当前原型即使接受伪造记录追加
  - 用户仍可通过 commitment 一致性对账发现问题

#### 6. 资源保护展示（Computation-DoS Flood）
结果：
- 总请求：
  - `300`
- L4 拦截：
  - `201`
- L7 拦截：
  - `98`
- 成功触达：
  - `1`
- 穿透率：
  - `0.33%`
- 状态分布：
  - `200_REJECTED = 98`
  - `200_SUCCESS = 1`
  - `L4_TIMEOUT = 201`

演示价值：
- 清晰展示：
  - L4 / L7 协同防线已将绝大多数无效请求阻断在高开销 PIR 计算之前

### 关键结论
- Day 56 目标已完成：
  - 已完成最终完整演示日
- 当前原型现已具备统一的展示入口，可在一次演示中完整覆盖：
  - 正常主链
  - 客户端攻击防御
  - 服务端争议追踪
  - 协同资源保护
- Day 48–56 的实验、评估、复现、讨论与演示链条现已闭合

### 当前边界 / 备注
- 场景 2 / 6 中的 L4 现象仍应表述为：
  - “符合 L4 eBPF 前置丢弃预期”
  - 而非仅凭客户端 timeout 就视为唯一铁证
- 当前 Demo CLI 的定位是：
  - 演示控制台
  - 而非严格 benchmark 工具

### 下一步
- 进入最终收口阶段：
  - Day 57：最终总结 / 项目结论
  - Day 58：论文摘要、贡献点与答辩口径统一