# PIR 匿名抗滥用访问控制原型 TODO

## 当前固定前提
- 主线：blind ticket -> admission -> binding -> verifier -> PIR -> audit
- blind signature 第一版：RSA blind signature
- PIR 后端：独立进程 / 微服务集成
- 状态机：UNUSED / PENDING / CONSUMED / FAILED
- eBPF 第一版：仅轻量前置过滤
- Python 服务：统一 YAML 配置 + 统一 logging
- 当前项目目录在 WSL Linux 文件系统中

---

## 已完成

## 第 1 周：环境、选型、对象定义、PIR 预热

- [x] **Day 1：Linux 开发环境搭建**
  - [x] 开启 WSL2 (Ubuntu 22.04/24.04)
  - [x] 安装 Python 3.13、Git、Docker Desktop
  - [x] 安装基础编译与开发工具 (`build-essential`, `libssl-dev`, `redis-server` 等)

- [x] **Day 2：项目目录与 Git 初始化**
  - [x] 创建核心服务目录 (`issuer`, `client`, `verifier`, `pir_server`, `auditor`)
  - [x] 创建脚手架目录 (`common`, `configs`, `experiments`, `scripts`, `logs`, `docs`)
  - [x] 初始化 Git 仓库，配置 `.gitignore`，完成首次 Commit
  - [x] 创建 `README.md`, `TODO.md`, `devlog.md`

- [x] **Day 3：环境隔离**
  - [x] 为各核心模块及实验模块建立独立的 Python 虚拟环境 (`.venv`)
  - [x] 确立各服务独立的 `requirements.txt` 管理机制

- [x] **Day 4：开发工具接入**
  - [x] 配置 IDE (PyCharm / VSCode) 环境，确保能正确识别各个 `.venv` 的解释器

- [x] **Day 5：公共基础设施 (Bootstrap)**
  - [x] 建立统一配置文件 `configs/common/base.yaml`
  - [x] 实现配置加载模块 `common/config.py`
  - [x] 实现统一日志格式模块 `common/logging_utils.py`
  - [x] 验证各个微服务的 `main.py` 启动与日志输出正常

### Day 6：关键技术路线定稿
- [x] 选定 blind signature 第一版采用 RSA blind signature
- [x] 明确 PIR 后端采用独立进程 / 微服务集成
- [x] 明确状态机采用 `UNUSED / PENDING / CONSUMED / FAILED`
- [x] 明确 eBPF 第一版仅做轻量前置过滤
- [x] 明确 Python 服务统一 YAML 配置 + 统一 logging

### Day 7：对象 / API / 时序定稿
- [x] 定稿 `docs/object_model.md`
- [x] 定稿 `docs/api.md`
- [x] 定稿 `docs/sequence.md`
- [x] 定稿 `common/models.py`
- [x] 固化 Ticket 模型：`t = (SN, sigma, EpochID)`
- [x] 固化请求实例：`r = (q, t, b, w)`

### Day 8：Issuer Blind-Sign API
- [x] 完成 `services/issuer/crypto.py`
- [x] 完成 `services/issuer/main.py`
- [x] 跑通 `/api/v1/issuer/challenge`
- [x] 跑通 `/api/v1/issuer/issue`
- [x] 验证 blinded message -> blinded signature 正常返回

### Day 9：Client Blind/Unblind & Ticket 获取
- [x] 完成 `services/client/crypto.py`
- [x] 完成 `services/client/main.py`
- [x] 完成 SN 生成、消息编码、盲化、去盲
- [x] 完成本地自验签 `pow(s, e, n) == m`
- [x] 成功组装 `Ticket(sn, sigma, epoch_id)`
- [x] 跑通 `scripts/test_ticket_flow.sh`

### Day 10：Verifier 票据验签
- [x] 完成 `common/crypto_utils.py`
- [x] Verifier 复用统一编码契约，避免 client / verifier 漂移
- [x] 完成 `services/verifier/crypto.py`
- [x] 完成 `services/verifier/main.py`
- [x] Verifier 启动时获取并缓存 Issuer 公钥
- [x] 跑通 `/api/v1/verifier/execute`
- [x] 正例：合法 Ticket 返回 `SUCCESS`
- [x] 反例：篡改 `SN` 返回 `REJECTED`
- [x] 反例：篡改 `sigma` 返回 `REJECTED`
- [x] 跑通 `scripts/test_day10_verifier.py`

### Day 11：继续 PIR demo 编译/运行 (成功在 WSL2 原生编译 SimplePIR Go 官方实现并跑通 Benchmark)
---

## 当前已固化的工程约定

### Ticket 签名消息编码契约
- `m = SN(32 bytes) || EpochID(4 bytes big-endian)`
- 统一实现入口：`common.crypto_utils.encode_ticket_message()`
- Client 与 Verifier 必须复用同一份编码逻辑

### Ticket 中 sigma 的存储约定
- `sigma` 存储为：**定长模数字节串** 的 Base64 编码
- Verifier 验签时必须：
  1. Base64 解码回定长字节串
  2. 转换为大整数 `s`
  3. 验证 `pow(s, e, n) == m`

### 当前 Day 10 Verifier 语义
- 当前 `/execute` 中 `SUCCESS` 仅表示：
  - **RSA 签名验证通过**
  - Binding / Redis / PIR 尚未真正执行
- 这是 Day 10 stub 语义，后续需被完整流程替代

---


### Day 11：Binding 验证
- [x] 明确 `sk_t` 的工程派生实现
- [x] 实现 `query_commitment = H(q)`
- [x] 实现 Witness 规范化序列化
- [x] 实现 `binding_tag = HMAC(sk_t, c_q || w)`
- [x] 在 Verifier 中加入 binding 校验
- [x] 增加正反例：
  - [x] 正确 binding 通过
  - [x] 篡改 `query_payload` 被拒绝
  - [x] 篡改 `witness` 被拒绝
  - [x] 篡改 `binding_tag` 被拒绝

### Day 12：Redis 防重放与状态流转
- [x] 接入 Redis
- [x] 实现 `SETNX SN PENDING`
- [x] 实现状态流转：
  - [x] `UNUSED -> PENDING`
  - [x] `PENDING -> CONSUMED`
  - [x] `PENDING -> FAILED`
- [x] 明确拒绝分支：
  - [x] `PENDING` -> in-flight / replay
  - [x] `CONSUMED` -> double spend
  - [x] `FAILED` -> burned ticket
- [x] 增加状态机联调测试

### Day 13+：Verifier / PIR Server 串联（第一阶段）
- [x] 建立 `services/pir_server/main.py` HTTP 适配层（Stub）
- [x] 暴露 `/api/v1/pir/query`
- [x] 将 Verifier 中本地 stub 执行替换为 HTTP 网络桥接
- [x] 抽离 `call_pir_server()`，避免 `/execute` 路由继续膨胀
- [x] 将 PIR 执行结果与票据状态推进绑定：
  - [x] PIR 成功 -> `PENDING -> CONSUMED`
  - [x] PIR 失败 -> `PENDING -> FAILED`
- [x] 保持 Day 12 生命周期语义在跨服务模式下不回退
- [x] 增加审计本地存根：
  - [x] 在 Verifier 本地组装 `audit_record_stub`
  - [x] 先以日志方式留痕，不立即强绑定 Auditor HTTP 投递

### 下一步：Auditor / 审计闭环（第二阶段）
- [ ] 建立 `services/auditor/main.py` HTTP 存根
- [ ] 暴露 `/api/v1/auditor/report`
- [ ] 将当前 `[Audit Stub]` 升级为后台 HTTP 上报
- [ ] 明确审计记录字段与 `common.models.AuditRecord` 一致
- [ ] 验证 Auditor 不可用时不影响 Verifier 主决策返回

### 下一步：PIR 协议收口（第三阶段）
- [ ] 将 `pir_server` 当前 stub 请求/响应抽成公共模型
- [ ] 将 PIR stub latency 收归配置
- [ ] 为 `call_pir_server()` 增加 timeout / 5xx / connection refused 分类日志
- [ ] 为网络桥接补充单独联调脚本或回归记录
## 进行中 / 下一步

### Day 14：本周重构与单测
- [x] 为 blind issue / verify 补充核心单测
- [x] 新增 `tests/test_crypto_core.py`
- [x] 完成以下单测覆盖：
  - [x] `encode_ticket_message()` 输入边界校验
  - [x] `sigma` Base64 严格契约反例
  - [x] `blind_message()` 对 `m >= n` 的拒绝
  - [x] `integer_to_base64()` / `base64_to_integer()` round-trip
  - [x] blind issue -> unblind -> verify 全链路 happy path
  - [x] 篡改 `SN / EpochID / sigma` 的验签拒绝
- [x] 清理错误码和 API 语义
- [x] 保持 blind-sign 为唯一主线，不再保留普通签名占位

## Day 16：Issuer challenge / verify_admission
- [x] 实现 `POST /api/v1/issuer/challenge`
- [x] 实现 `POST /api/v1/issuer/verify_admission`
- [x] 将 admission proof 接入 `IssueRequest`
- [x] 在 `/issue` 中强制执行 admission 前置校验
- [x] 落地 Interactive Hashcash PoW：
  - [x] `canonical_json_bytes()`
  - [x] `compute_hmac()`
  - [x] `verify_pow()`
  - [x] `solve_pow()`
- [x] 落地 Challenge HMAC 防伪造校验
- [x] 落地 Challenge 过期校验
- [x] 落地 Day 16 最小 `epoch_id` 存根校验（当前固定 `epoch_id=1`）
- [x] 落地 Redis challenge burn semantics：
  - [x] `admission:challenge:<fingerprint>` 独立 keyspace
  - [x] `SET nx=True ex=ttl` 防 replay
- [x] 补充 `client_tag` 命名收口，替换早期 `client_id` 漂移
- [x] admission 配置收口到 YAML：
  - [x] `difficulty_bits`
  - [x] `challenge_ttl_sec`
  - [x] `grace_window_sec`
  - [x] `redis_prefix`
- [x] 新增 Day 16 验收脚本 `scripts/test_day16_admission.py`

### Day 16 验收结果
- [x] 不带 `admission_proof` 调 `/issue` 会失败（422）
- [x] 伪造 `hmac_sig` 会被 `/verify_admission` 拒绝（403）
- [x] 错误 `nonce` 会被 PoW 校验拒绝（403）
- [x] 同一 challenge 二次 `/issue` 命中 replay / burned challenge（第二次 403）

### Day 16 结论
- [x] `/challenge` 已可用
- [x] `/verify_admission` 已可用
- [x] admission 不通过不能签票
- [x] 不执行 challenge 拿不到票（已由反例脚本验证）

### Day 16 小收尾（留给 Day 17 前顺手修）
- [ ] 将 issuer 日志中的原始 `client_tag` 改为 hash 截断值
- [ ] 将 Day 16 结果同步进文档 `docs/admission.md`（若尚未落盘）
---
## Day 17：blind ticket + admission 整合
- [x] 将 `services/client/main.py` 中的 `acquire_ticket()` 收口为完整签发链
- [x] Client 先调用 `GET /api/v1/issuer/public_key` 获取 Issuer 真实 RSA 公钥
- [x] Client 调用 `POST /api/v1/issuer/challenge` 获取 admission challenge
- [x] Client 本地执行 `solve_pow()` 完成 Interactive Hashcash PoW
- [x] Client 将 `blinded_message + admission_proof` 一并提交到 `POST /api/v1/issuer/issue`
- [x] Issuer 在 `/issue` 中完成 admission 校验通过后再执行 blind sign
- [x] Client 完成去盲并执行本地验签
- [x] Client 最终输出 `Ticket(sn, sigma, epoch_id)`
- [x] 将 client 侧配置命名从 `client_id` 收口为 `client_tag`
- [x] 新增 `GET /api/v1/issuer/public_key`，移除 client 端本地公钥 stub fallback
- [x] 新增 `scripts/test_day17_chain.py`
- [x] 新增 `scripts/test_day17_full_e2e.py`

### Day 17 验收结果
- [x] admission 通过后执行 blind-sign
- [x] 成功输出最终 `Ticket`
- [x] admission 与 blind issue 已串为一条链
- [x] 本地去盲后验签通过
- [x] Day 17+ 全链路烟雾测试通过：
  - [x] Client -> Admission(PoW) -> Issuer -> Binding -> Verifier -> PIR Server 全链路成功
  - [x] Verifier 返回 `decision=SUCCESS`
  - [x] PIR 返回成功结果

### Day 17 结论
- [x] Day 17 已完成
- [x] Ticket 获取主链已从“blind-sign + admission”角度完成整合
- [x] 当前已具备继续做更稳定端到端回归或推进 Auditor 的基础

### Day 17 小收尾
- [ ] 将 issuer/client 日志中的原始 `client_tag` 收口为 hash 截断值
- [ ] 将 `scripts/test_day17_full_e2e.py` 中 issuer / pir_server 连接提示也改为从配置打印
- [ ] 将 Day 17 结果同步到 `docs/admission.md` / 相关设计文档（如尚未补齐）

## Day 18：epoch 时间窗
- [x] 定义统一 epoch 配置：
  - [x] `epoch.duration_sec`
  - [x] `epoch.grace_window_sec`
- [x] 在 `common/crypto_utils.py` 中新增：
  - [x] `get_current_epoch_id(epoch_duration)`
  - [x] `is_epoch_valid(ticket_epoch, now_ts, duration, grace)`
- [x] 在 Issuer challenge 阶段动态写入当前 `epoch_id`
- [x] 保持 Ticket 结构不变，继续使用 `t = (SN, sigma, EpochID)`
- [x] 在 Issuer `/issue` 前增加 epoch 有效性检查
- [x] 在 Verifier `/execute` 前增加 epoch 前置快拒绝
- [x] 统一 Issuer / Verifier 的 epoch 判定逻辑，复用 `is_epoch_valid(...)`
- [x] 为 `is_epoch_valid(...)` 补充输入边界保护：
  - [x] `duration > 0`
  - [x] `grace >= 0`
- [x] 新增 `scripts/test_day18_epoch.py`
- [x] 将 Day 18 过期测试改为确定性方案：
  - [x] 不再使用 `epoch - 1`
  - [x] 改为 `epoch - 2`，确保无论是否处于宽限期都会被拒绝

### Day 18 验收结果
- [x] 当前 epoch 的 ticket 仍可正常签发
- [x] 将 ticket 强制改为两个纪元之前后，Verifier 返回 `decision=REJECTED`
- [x] `reason` 明确包含 `expired`
- [x] Verifier 日志出现 `Fast-rejecting expired ticket epoch`

### Day 18 结论
- [x] epoch 已定义并进入统一配置
- [x] Ticket 已动态携带 EpochID
- [x] Verifier 已检查当前 epoch
- [x] 过期票据被成功拒绝
- [x] Day 18 已完成

### Day 18 小收尾
- [ ] 将 issuer/client/verifier 中原始 `client_tag` 日志继续收口为 hash 截断值
- [ ] 视需要补一个“上一个 epoch 但处于 grace window 内仍可通过”的正例测试
- [ ] 将 Day 18 结果同步进相关设计文档（如 `docs/admission.md` / epoch 说明）
---
## Day 19：binding 生成
- [x] 在 `common/crypto_utils.py` 中实现 `compute_query_commitment(query_payload)`
- [x] 在 `common/crypto_utils.py` 中实现 `compute_binding_tag(sk_t, c_q_hex, witness_bytes)`
- [x] 为 `compute_query_commitment()` 增加最小输入检查：
  - [x] `query_payload` 必须为非空字符串
- [x] 为 `compute_binding_tag()` 增加边界检查：
  - [x] `sk_t` 必须为非空 bytes
  - [x] `c_q_hex` 必须为 64 字符小写 hex
  - [x] `witness_bytes` 必须为非空 bytes
- [x] 在 `services/client/main.py` 中完成 `create_bound_request(ticket, query_payload)` 收口
- [x] `create_bound_request()` 已完成以下步骤：
  - [x] 还原 `sigma_bytes`
  - [x] 派生 `sk_t`
  - [x] 计算 `c_q = H(q)`
  - [x] 构造 `witness`
  - [x] 规范化序列化 `witness`
  - [x] 计算 `binding_tag`
  - [x] 组装 `RequestInstance`
- [x] 新增 `scripts/test_day19_binding.py`

### Day 19 验收结果
- [x] Ticket 获取成功
- [x] `create_bound_request()` 执行成功
- [x] `RequestInstance` 结构完整形成
- [x] `request_id` 非空
- [x] `ticket` 正确进入请求实例
- [x] `binding_tag` 非空且长度为 64
- [x] `witness` 存在且 `nonce` / `timestamp_ms` 正常
- [x] `query_payload` 被正确保留

### Day 19 结论
- [x] `c_q = H(q)` 已生成
- [x] `b = HMAC(sk_t, H(q)||w)` 已生成
- [x] 请求实例结构完整形成
- [x] Day 19 已完成

### Day 19 小收尾
- [ ] 将 verifier 侧 Day 20 binding 校验继续对齐到当前 `c_q_hex.encode("utf-8") + witness_bytes` 契约
- [ ] 继续收口 issuer/client/verifier 中原始 `client_tag` 的日志脱敏
- [ ] 将 Day 19 结果同步进相关设计文档（如 binding 说明）

## Day 20：binding verify
- [x] 在 `services/verifier/main.py` 中实现 Binding Consistency Check
- [x] verifier 侧重算：
  - [x] `c_q = H(q)`
  - [x] `sk_t = derive_sk_t(sigma_bytes, sn, epoch_id)`
  - [x] `witness_bytes = serialize_witness(witness)`
  - [x] `expected_binding_tag = HMAC(sk_t, c_q || w)`
- [x] 对 `binding_tag` 比较改为 `hmac.compare_digest(...)`
- [x] 增加 `req.witness is None` 的缺失分支拒绝
- [x] 增加 binding 验证异常兜底：
  - [x] 非法 base64 / 非法 witness / 非法 binding 材料统一返回业务拒绝
- [x] 新增 `scripts/test_day20_binding_verify.py`
- [x] 测试脚本从配置读取 `VERIFIER_URL`
- [x] 测试脚本增加 timeout，避免联调挂死
- [x] 测试脚本覆盖以下分支：
  - [x] 篡改 `q`
  - [x] 篡改 `b`
  - [x] 篡改 `w`
  - [x] 缺失 `witness`
  - [x] 合法请求 happy path

### Day 20 验收结果
- [x] Tampered `q` 被拒绝
- [x] Tampered `b` 被拒绝
- [x] Tampered `w` 被拒绝
- [x] Missing `witness` 被拒绝
- [x] 合法请求成功通过并执行
- [x] binding check 真实生效

### Day 20 结论
- [x] verifier 已检查 `BindConsistent`
- [x] 篡改 `q / b / w` 会拒绝
- [x] 缺失 `witness` 会拒绝
- [x] 合法请求仍可通过
- [x] Day 20 已完成

### Day 20 小收尾
- [ ] 将测试脚本中的失败分支进一步补充 `resp.text` 输出，便于未来排障
- [ ] 继续收口 issuer/client/verifier 中原始 `client_tag` 的日志脱敏
- [ ] 将 Day 20 结果同步进 binding / verifier 相关设计文档
## Day 21：本周联调
- [x] 调整 `RequestInstance` 模型以支持业务层联调场景：
  - [x] `ticket: Optional[Ticket] = None`
  - [x] `binding_tag: Optional[str] = None`
  - [x] `witness: Optional[RequestContext] = None`
- [x] 在模型注释中明确：
  - [x] Day 21 起为了支持业务层联调与场景化拦截测试，`ticket / binding_tag / witness` 允许为空
  - [x] verifier 必须显式做缺失校验

- [x] 在 `services/verifier/main.py` 中补齐精细化拒绝分支：
  - [x] 缺失票据 -> `Missing Ticket in request`
  - [x] 过期票据 -> `Ticket epoch ... has expired.`
  - [x] 缺失 witness -> `Missing Request Witness`
  - [x] 缺失 binding_tag -> `Missing Binding Tag`
  - [x] 篡改 binding -> `Binding Consistency Check Failed`

- [x] 新增 `scripts/test_day21_integration.py`
- [x] 脚本从配置读取：
  - [x] `VERIFIER_URL`
  - [x] `TIMEOUT`
- [x] 联调脚本增加断言，锁死业务契约，不只做打印

### Day 21 联调场景
- [x] Case 1：正常请求
- [x] Case 2：无票据请求
- [x] Case 3：过期票据
- [x] Case 4：篡改 binding 请求

### Day 21 验收结果
- [x] 正常请求 -> `SUCCESS`
- [x] 无票据请求 -> `REJECTED` + `Missing Ticket in request`
- [x] 过期票据 -> `REJECTED` + `expired`
- [x] 篡改 binding 请求 -> `REJECTED` + `Binding Consistency Check Failed`
- [x] 所有场景都被真实区分处理

### Day 21 结论
- [x] 本周联调已完成
- [x] Day 17–21 主线形成阶段性闭环
- [x] 当前已具备进入下一阶段（如审计闭环或更系统的回归脚本整理）的基础

### Day 21 小收尾
- [ ] 删除 `scripts/test_day21_integration.py` 中未使用的 `import time`
- [ ] 继续收口 issuer/client/verifier 中原始 `client_tag` 的日志脱敏
- [ ] 将 Day 21 联调结果同步进周总结 / 回归文档
### Day 22：Redis 状态表接入
- [x] 在 `services/verifier/state_manager.py` 中落地 Redis 状态表管理器
- [x] 明确 `UNUSED` 为逻辑默认态：
  - [x] Redis miss == `UNUSED`
  - [x] 不要求签发时由 Issuer 预写 Redis，避免与签发链耦合
- [x] 接入统一 YAML 配置读取：
  - [x] Redis `host / port / db`
  - [x] `ticket_state_prefix`
  - [x] Epoch `duration_sec / grace_window_sec`
- [x] 实现状态查询：
  - [x] `get_state(sn)` 返回 `UNUSED / PENDING / CONSUMED / FAILED`
- [x] 实现短时占位能力（作为 Day 23 提前实现的最小原子能力）：
  - [x] `try_lock(sn)` 使用 `nx=True` 将票据置为 `PENDING`
- [x] 实现终态写入：
  - [x] `mark_consumed(sn, epoch_id, ...)`
  - [x] `mark_failed(sn, epoch_id, ...)`
- [x] 实现 Epoch 关联 TTL：
  - [x] 终态记录 TTL 由 `epoch_id + grace_window + retention buffer` 推导
  - [x] 支持 `ttl_override_sec` 仅供测试/联调使用
- [x] 将 `state_manager` 改为懒初始化，避免 import 时即强依赖 Redis
- [x] 在 Verifier 中新增状态查询接口：
  - [x] `GET /api/v1/verifier/ticket_state/{sn}`
  - [x] 增加严格 `64-char hex` SN 校验
- [x] 新增 / 收口验收脚本：
  - [x] `scripts/test_day22_redis_state.py`

### Day 22 验收结果
- [x] Redis miss 时，状态逻辑默认返回 `UNUSED`
- [x] `PENDING` 原子占位成功
- [x] `CONSUMED` 终态写入成功
- [x] Redis 终态 TTL 可按 Epoch 规则推导
- [x] TTL 过期后，Redis key 被物理清理，逻辑状态回归 `UNUSED`
- [x] `GET /api/v1/verifier/ticket_state/{sn}` 可正常返回票据状态
- [x] 非法 SN 查询返回 `400 Bad Request`

### Day 22 结论
- [x] Day 22 的 Redis 状态表核心语义已落地
- [x] Day 22 的“verifier 可查询状态”验收已通过
- [x] 当前实现保持与既有主线一致，不引入对 Issuer 签发链的新耦合

### Day 22 小收尾
- [ ] 视需要将 `PENDING` 短锁 TTL 收口到 YAML 配置
- [ ] 视后续 Auditor 对账需求，再决定是否将 Redis value 从纯状态字符串升级为结构化 JSON
- [ ] 在 Day 23/24 中继续把 `try_lock()` 与主验证路径原子消费语义正式收口
### Day 23：原子核销
- [x] 复用 `services/verifier/state_manager.py` 中的 `try_lock(sn, lock_ttl_sec=...)`
- [x] 明确 Day 23 主目标：
  - [x] 用 Redis `SETNX` 语义实现 `UNUSED -> PENDING` 原子状态转换
  - [x] 保证同一 `SN` 不能被多个并发请求同时进入处理态
- [x] 新增并发验收脚本：
  - [x] `scripts/test_day23_concurrency.py`
- [x] 使用 `threading.Barrier` 实现统一起跑，增强并发竞争真实性
- [x] 测试前显式清理 Redis key，避免脏状态污染回归结果
- [x] 补充最终状态落点断言：
  - [x] 并发结束后票据状态必须稳定为 `PENDING`

### Day 23 验收结果
- [x] 50 个并发线程同时竞争同一 `SN`
- [x] 仅 1 个请求成功获取锁并进入处理态
- [x] 其余 49 个请求被原子拦截
- [x] 最终票据状态稳定为 `PENDING`

### Day 23 结论
- [x] Day 23 的 `UNUSED -> PENDING` 原子状态转换已通过并发验收
- [x] Day 23 的“并发 replay 只允许一次成功”验收已通过

### Day 23 小收尾
- [ ] 视需要将 `lock_ttl_sec` 收口到统一 YAML 配置
- [ ] 在 Day 24 中把当前原子占位与 verifier 主路径正式绑定
- [ ] 视需要补充多轮重复并发回归，验证结果稳定性

### Day 24：判定路径绑定原子核销
- [x] 确认 Verifier 主路径遵循以下顺序：
  - [x] 前置验证（缺失票据 / epoch / RSA 验签 / binding 校验）
  - [x] 原子占位：`UNUSED -> PENDING`
  - [x] 成功占位后才允许进入 PIR 主路径
- [x] 确认前置验证失败时不改变票据状态：
  - [x] 缺失票据 -> `REJECTED + UNUSED`
  - [x] 过期票据 -> `REJECTED + UNUSED`
  - [x] 篡改 binding -> `REJECTED + UNUSED`
- [x] 确认 PIR 成功后的状态流转：
  - [x] `PENDING -> CONSUMED`
  - [x] 返回 `SUCCESS + CONSUMED`
- [x] 确认 PIR 失败后的状态流转：
  - [x] `PENDING -> FAILED`
  - [x] 返回 `REJECTED + FAILED`
  - [x] `reason` 包含 burned 语义
- [x] 新增 Day 24 验收脚本：
  - [x] `scripts/test_day24_consume_semantics.py`
- [x] 用固定故障注入 payload 收口 Case 5：
  - [x] `trigger_failure_test`

### Day 24 验收结果
- [x] 正常请求 -> `SUCCESS + CONSUMED`
- [x] 无票据请求 -> `REJECTED + UNUSED`
- [x] 过期票据 -> `REJECTED + UNUSED`
- [x] 篡改绑定 -> `REJECTED + UNUSED`
- [x] PIR 后端失败 -> `REJECTED + FAILED`
- [x] Verifier 日志确认状态流转：
  - [x] `UNUSED -> PENDING -> CONSUMED`
  - [x] `UNUSED -> PENDING -> FAILED`

### Day 24 结论
- [x] Day 24 的“判定与消费语义一致”验收已通过
- [x] 当前票据状态机语义与主路径实现对齐：
  - [x] `UNUSED`：已签发但尚未进入处理流程
  - [x] `PENDING`：已通过前置验证并进入后端处理阶段
  - [x] `CONSUMED`：请求成功执行完成
  - [x] `FAILED`：已进入处理阶段，但后端失败或异常终止

### Day 24 小收尾
- [ ] 视需要补一个对 `/api/v1/verifier/ticket_state/{sn}` 的后查状态复核
- [ ] 视需要将 `lock_ttl_sec` 收口到 YAML 配置
- [ ] 继续推进 Day 25：tamper-evident 审计日志
### Day 25：tamper-evident 审计日志
- [x] 明确 Day 25 第一版采用链式 HMAC 审计日志
- [x] 审计日志至少覆盖以下字段：
  - [x] `sn`
  - [x] `query_commitment`
  - [x] `decision`
  - [x] `timestamp_ms`
  - [x] `prev_hash`
  - [x] `entry_mac`
- [x] 在 `configs/common/base.yaml` 中收口 Auditor 配置：
  - [x] `auditor.ledger_path`
  - [x] `auditor.hmac_secret`
- [x] 升级 `services/auditor/main.py`
  - [x] 启动时恢复链状态
  - [x] 使用 `lifespan` 托管初始化
  - [x] 读取最后一条非空账本记录恢复 `current_prev_hash`
  - [x] 使用 `threading.Lock()` 保护链式落账临界区
  - [x] 计算链式 `entry_mac`
  - [x] 顺序落盘 `audit_ledger.jsonl`
- [x] 明确 Day 25 第一版 MAC payload 契约：
  - [x] `sn | query_commitment | decision | timestamp_ms | prev_hash`
- [x] 升级 `scripts/test_day25_audit_chain.py`
  - [x] 增加 `timeout`
  - [x] 增加 `raise_for_status()`
  - [x] 验证真实账本完整性
  - [x] 使用副本文件模拟篡改
  - [x] 验证副本篡改会被发现
  - [x] 验证结束后清理副本，保持真实账本完好

### Day 25 验收结果
- [x] 正常生成 2 条真实审计记录
- [x] 真实账本完整性校验通过
- [x] 篡改副本中单条记录后，`entry_mac` 校验失败
- [x] 成功发现篡改行为
- [x] 真实账本保持完好未被污染

### Day 25 结论
- [x] Day 25 的链式 HMAC 审计日志已落地
- [x] Day 25 的“每条日志都能串成防篡改链”验收已通过

### Day 25 小收尾
- [ ] 视需要补一个按 `sn` 或 `sn + c_q` 的最小查询接口
- [ ] 视需要扩展为对更多拒绝分支也留审计记录
- [ ] 后续如进入更强威胁模型，再考虑密钥托管与多进程一致性
### Day 26：Auditor 查询接口
- [x] 在 `services/auditor/main.py` 中新增：
  - [x] `GET /api/v1/auditor/trace/{sn}`
- [x] 支持按 `SN` 查询单条审计记录
- [x] 支持按 `SN + expected_cq` 做一致性判定
- [x] 返回最小链上下文字段：
  - [x] `prev_hash`
  - [x] `entry_mac`
- [x] 为 `expected_cq` 增加 64-char hex 格式校验
- [x] 明确当前接口返回的是“当前记录的链上下文”，不是前后邻居完整记录
- [x] 明确当前原型阶段采用“单票据对应单条主审计记录，找到即停”的假设
- [x] 新增验收脚本：
  - [x] `scripts/test_day26_auditor_trace.py`
- [x] 验收脚本中对前置交易增加：
  - [x] `timeout`
  - [x] `raise_for_status()`
  - [x] `decision == SUCCESS` 断言

### Day 26 验收结果
- [x] 按 `SN` 查询成功
- [x] 能返回 `ledger_line`
- [x] 能返回 `prev_hash / entry_mac`
- [x] 按 `SN + 正确 c_q` 查询时，一致性判定为 `True`
- [x] 按 `SN + 伪造 c_q` 查询时，一致性判定为 `False`

### Day 26 结论
- [x] Day 26 的 Auditor 查询接口已落地
- [x] Day 26 的“Auditor 能追溯单条请求”验收已通过

### Day 26 小收尾
- [ ] 视需要补 `SN` 的 64-char hex 格式校验
- [ ] 视需要将“找到即停”扩展为多事件记录列表返回
- [ ] 继续推进 Day 27：最小争议验证闭环
### Day 27：最小争议验证闭环
- [x] 新增 Day 27 验收脚本：
  - [x] `scripts/test_day27_dispute_resolution.py`
- [x] 完成争议 1：前置拦截（Dropped Request）
  - [x] 返回明确 `reason`
  - [x] Verifier 状态保持 `UNUSED`
  - [x] 不产生终态审计记录
- [x] 完成争议 2：处理中重放（PENDING Collision）
  - [x] replay 被拒绝
  - [x] 原因命中 `PENDING / concurrent`
  - [x] Verifier 状态为 `PENDING`
  - [x] 首个请求最终成功并转入 `CONSUMED`
- [x] 完成争议 3：已核销重放（CONSUMED Collision）
  - [x] replay 被拒绝
  - [x] 原因命中 `CONSUMED`
  - [x] Verifier 状态为 `CONSUMED`
  - [x] Auditor 审计记录存在
- [x] 完成争议 4：后端崩溃与烧毁重放（FAILED Collision）
  - [x] 首次失败返回 `REJECTED + FAILED`
  - [x] replay 被拒绝
  - [x] 原因命中 `FAILED`
  - [x] Verifier 状态为 `FAILED`
  - [x] Auditor 审计记录存在
- [x] 为证据提取函数补充：
  - [x] `timeout`
  - [x] `raise_for_status()`
- [x] 锁死关键业务断言：
  - [x] Binding 失败原因
  - [x] 首个成功请求最终为 `SUCCESS + CONSUMED`
  - [x] 首次失败请求为 `REJECTED + FAILED + burned`

### Day 27 验收结果
- [x] 被 drop 的请求能解释原因，且状态保持 `UNUSED`
- [x] 进入 `PENDING` 的请求能查到处理中痕迹
- [x] 成功完成的请求能证明状态转为 `CONSUMED`
- [x] 后端失败或异常中断的请求能证明状态转为 `FAILED`
- [x] replay 请求能区分命中 `PENDING / CONSUMED / FAILED` 的不同原因
- [x] 三类争议均具备最小证据支撑

### Day 27 结论
- [x] Day 27 的最小争议验证闭环已通过
- [x] 当前系统已具备：
  - [x] 最小状态证据
  - [x] 最小审计证据
  - [x] 最小业务解释证据

### Day 27 小收尾
- [ ] 视需要把更多前置拒绝分支也纳入 Auditor 留痕
- [ ] 视需要把 PENDING 观察从 `sleep` 升级为轮询 state 接口
- [ ] 继续推进 Day 28：阶段重构
### Day 28：阶段重构
- [x] 对 `services/verifier/main.py` 完成阶段性重构
- [x] 将 verifier 主流程拆分为：
  - [x] `_run_precondition_check`
  - [x] `_run_crypto_verification`
  - [x] `execute_query` 编排器
- [x] 清理 verifier 逻辑，同时保持外部行为不变
- [x] 保持前置拒绝 API 契约不变：
  - [x] `Missing Ticket in request`
  - [x] `Invalid Ticket Signature`
  - [x] `Missing Request Witness`
  - [x] `Missing Binding Tag`
  - [x] `Binding Consistency Check Failed`
  - [x] `Invalid Binding Material`
- [x] 保持状态机主路径不变：
  - [x] `UNUSED -> PENDING -> CONSUMED`
  - [x] `UNUSED -> PENDING -> FAILED`
- [x] 保持关键状态流转日志不变
- [x] 保持审计投递仍由 Verifier 异步发起、由 Auditor 负责真实链式注入
- [x] `dispatch_audit_log()` 增加 `raise_for_status()`
- [x] `_run_crypto_verification()` 补回 issuer 公钥可用性兜底
- [x] `query_ticket_state()` 恢复完整错误文案：
  - [x] `Invalid SN format: must be 64-char hex`
- [x] `call_pir_server()` 恢复细粒度异常分类：
  - [x] `timeout`
  - [x] `http_error_<code>`
  - [x] `connection_error`
  - [x] `unknown_error`

### Day 28 验收结果
- [x] Day 27 争议闭环回归通过
- [x] Day 26 Auditor trace & cq consistency 回归通过
- [x] Day 25 tamper-evident audit chain 回归通过
- [x] Verifier / Auditor / PIR Server / Issuer 四服务协同链路稳定
- [x] 最终版 `services/verifier/main.py` 已在回归后确认稳定

### Day 28 结论
- [x] Day 28 的阶段重构已完成
- [x] 重构后内部结构更清晰
- [x] 重构后外部 API 契约未被破坏
- [x] 核心票据 / 验证 / 审计链路稳定

### Day 28 小收尾
- [ ] 后续可再考虑收口 `lock_ttl_sec` 到统一 YAML 配置
- [ ] 后续可再明确审计核心字段与快照字段的边界
- [ ] 进入下一阶段前，做一次总结构梳理
## Day 29：正式接入主候选 PIR
- [x] 将 `pir_server` 的 subprocess 桥接层收口为 JSON stdin/stdout 协议
- [x] 保留 `stub / subprocess` 双模式，不破坏既有回归路径
- [x] 完成 Go wrapper 二进制边界接入
- [x] 恢复并收口 Go wrapper 的边界验收分支：
  - [x] `fatal_crash_test`
  - [x] `bad_json_test`
  - [x] `status_error_test`
- [x] 在 `pir_engine/simplepir/cmd/json_bridge` 中建立主候选真实桥接入口
- [x] 对齐 SimplePIR `RunPIR` 真实调用链：
  - [x] `Init`
  - [x] `Setup`
  - [x] `Query`
  - [x] `Answer`
  - [x] `Recover`
- [x] 用固定小型 DB 做 Day 29 确定性基线：
  - [x] `numEntries = 1024`
  - [x] `vals[42] = 4242`
- [x] 完成 stdout 净化，避免底层 Go 输出污染 JSON 协议
- [x] 通过 Go wrapper 双重自验：
  - [x] `index == 42 -> 4242`
  - [x] `index != 42 -> 0`
- [x] 通过 Day 29（中）Go wrapper 四类异常路径验收
- [x] 通过 Day 29（下-2）确定性 PIR 红线验收：
  - [x] 固定索引 `42`
  - [x] 成功恢复固定真值 `4242`

### Day 29 结论
- [x] Python 控制层已能稳定驱动真实主候选 SimplePIR 核心计算
- [x] Day 29 主目标完成：系统已能实际调用真实 PIR 后端

### Day 29 后续衔接（留给 Day 31）
- [ ] 定义 `q -> PIR query` 的正式映射
- [ ] 定义 Python 与独立 PIR 后端之间的最终输入输出协议
- [ ] 收口输出解析与错误返回路径
- [ ] 评估是否将小型基线 DB / hint 初始化从“请求内构造”迁移为更正式的生命周期管理
## Day 31：请求实例与 PIR 输入对齐
- [x] 定义 `q -> PIR index` 的第一版映射规则：
  - [x] Python 侧使用 `SHA-256(query_payload) % DB_NUM_ENTRIES`
  - [x] 当前 `DB_NUM_ENTRIES = 1024`
- [x] 明确 Python -> Go 的输入协议字段：
  - [x] `request_id`
  - [x] `query_payload`
  - [x] `pir_input`
  - [x] `engine_request_type`
- [x] 明确 Go -> Python 的输出协议字段：
  - [x] `status`
  - [x] `result`
  - [x] `recovered_val`
  - [x] `error_type`
  - [x] `error_message`
  - [x] `engine_meta`
- [x] `engine_adapter.py` 已支持返回三元组：
  - [x] `result`
  - [x] `recovered_val`
  - [x] `engine_meta`
- [x] `/api/v1/pir/query` 已向上层返回：
  - [x] `data`
  - [x] `mapped_index`
  - [x] `recovered_val`
- [x] Go wrapper 已从固定基线 `42 -> 4242` 升级为动态可预测 DB：
  - [x] `vals[i] = i * 101`
- [x] Go wrapper 已完成动态自验：
  - [x] `expectedVal = queryIndex * 101`
- [x] 保留 Day 29 边界分支：
  - [x] `status_error_test`
  - [x] `fatal_crash_test`
  - [x] `bad_json_test`
- [x] 通过 Day 31 第一轮动态映射验收脚本：
  - [x] `query_apple`
  - [x] `query_banana`
  - [x] `user_12345`

### Day 31 结论
- [x] 请求实例已能驱动真实 PIR 查询
- [x] `q -> mapped_index -> recovered_val` 第一版链路已打通

### Day 31 后续收口
- [ ] 决定 Day 29 固定基线脚本是冻结保留，还是增加“固定基线模式”开关
- [ ] 收口 `DB_NUM_ENTRIES` / `NUM_ENTRIES` 的统一来源，避免双边手工漂移
- [ ] 进一步规范 `engine_meta` 字段
- [ ] 明确 Day 31 最终版错误码 / reason 文案
## Day 32：主链路联调
- [x] Verifier 已支持接收并透传 PIR Server 的结构化返回：
  - [x] `result_string`
  - [x] `mapped_index`
  - [x] `recovered_val`
- [x] `call_pir_server()` 已升级为返回四元组：
  - [x] `success`
  - [x] `payload_or_error`
  - [x] `mapped_index`
  - [x] `recovered_val`
- [x] Verifier 成功分支已将真实 PIR 结果写入 `PIRResponse.data`
- [x] Verifier 失败分支已保持：
  - [x] `PENDING -> FAILED`
  - [x] 返回失败 `reason`
- [x] Auditor 后台投递已继续工作，且当前未强行扩展 `mapped_index` 字段，避免模型阻塞主链
- [x] 新增并跑通 `scripts/test_day32_full_pipeline.py`
- [x] 全链路 Happy Path 联调通过：
  - [x] client 获取 ticket
  - [x] client 生成 binding
  - [x] verifier 放行
  - [x] pir_server 调真实 PIR
  - [x] verifier 返回真实 PIR 结果
- [x] 验收通过：
  - [x] `decision == SUCCESS`
  - [x] `mapped_index` 与预期一致
  - [x] `recovered_val` 与预期一致

### Day 32 结论
- [x] 合法请求已能返回真实 PIR 结果
- [x] Day 32 主链路联调完成

### Day 32 后续衔接
- [ ] Day 33：验证非法请求不会进入 PIR
- [ ] 进一步观察 auditor 后台投递日志是否稳定
- [ ] 视需要统一 `result_string / recovered_val / mapped_index` 的最终响应字段命名
## Day 33：非法请求不进入 PIR
- [x] 在 verifier 中新增轻量级内存 metrics：
  - [x] `total_requests`
  - [x] `blocked_before_pir`
  - [x] `pir_invoked`
- [x] 新增 `/api/v1/verifier/metrics` 接口
- [x] 在 verifier 主链中加入 PIR 前后探针日志：
  - [x] `[PIR_START]`
  - [x] `[PIR_END]`
- [x] 明确 `pir_invoked` 语义：
  - [x] 已穿过前置验证并开始调用底层 PIR 的请求数
  - [x] 包含执行过程报错的请求
- [x] 明确 `blocked_before_pir` 语义：
  - [x] precondition 拦截
  - [x] crypto verification 拦截
  - [x] `try_lock` 失败拦截
- [x] 新增并跑通 `scripts/test_day33_abuse_prevention.py`
- [x] 完成 Day 33 第一轮负例隔离验证：
  - [x] 1 个合法请求成功进入 PIR
  - [x] 1 个篡改 binding 请求被挡下
  - [x] 1 个缺失 ticket 请求被挡下
  - [x] 1 个 replay 请求被挡下
- [x] 最终 metrics 对账通过：
  - [x] `added_total == 4`
  - [x] `added_blocked == 3`
  - [x] `added_pir == 1`

### Day 33 结论
- [x] 非法请求不会触发 PIR 计算
- [x] Day 33 验收通过

### Day 33 后续衔接
- [ ] Day 34：整理功能性指标
- [ ] 决定是否把 verifier 内存 metrics 继续保留为调试接口
- [ ] 视需要把 `[PIR_START]/[PIR_END]` 探针日志格式进一步统一
## Day 34：第一轮功能性指标
- [x] 新增 `scripts/test_day34_functional_metrics.py`
- [x] 采用固定配比的 10 个请求进行功能性体检：
  - [x] 5 个正常请求
  - [x] 3 个 replay 请求
  - [x] 1 个 binding 篡改请求
  - [x] 1 个伪造签名请求
- [x] 复用 verifier `/metrics` 做功能性对账
- [x] 统计并输出以下指标：
  - [x] 正常成功率
  - [x] replay 拦截率
  - [x] binding 错误拦截率
  - [x] 签名伪造拦截率
  - [x] PIR 进入比例
- [x] 完成功能性报表打印
- [x] Day 34 第一轮指标验收通过：
  - [x] 正常成功率 = 100.00%（5/5）
  - [x] replay 拦截率 = 100.00%（3/3）
  - [x] binding 错误拦截率 = 100.00%（1/1）
  - [x] 签名伪造拦截率 = 100.00%（1/1）
  - [x] PIR 实际进入次数 = 5
  - [x] PIR 进入比例 = 50.00%

### Day 34 结论
- [x] 第一轮功能性指标整理完成
- [x] 当前系统在固定配比样本下表现稳定
- [x] 合法请求与非法请求的分流结果符合预期
### Day 35：缓冲 / 修复日
- [x] 收口 `common.models.PIRResponse.data` 强类型契约：
  - [x] 新增 `PIRResultPayload`
  - [x] 将 `data: Optional[Any]` 改为 `data: Optional[PIRResultPayload]`
- [x] 收口 verifier 成功返回的数据组装：
  - [x] 成功路径使用 `PIRResultPayload(...)` 实例化
  - [x] 保持 `reason` 文案不变，避免旧断言漂移
- [x] 收缩 `call_pir_server()` 类型注解：
  - [x] 从宽松 `Any` 收口为 `tuple[bool, str, Optional[int], Optional[int]]`
- [x] 补充成功分支防御性检查：
  - [x] 若 `success=True` 但 `mapped_index/recovered_val is None`，则按 malformed PIR response 处理
  - [x] 状态流转改为 `PENDING -> FAILED`
  - [x] 保持票据烧毁语义一致
- [x] 保持 Auditor 契约不扩面：
  - [x] `AuditRecord` 暂不增加 `mapped_index`
  - [x] audit payload 继续剔除 `mapped_index`
- [x] 运行 Day 34 功能性回归脚本：
  - [x] `python scripts/test_day34_functional_metrics.py`

### Day 35 验收结果
- [x] Day 34 功能性指标脚本在 Day 35 收口后仍通过
- [x] 正常请求成功率：`100% (5/5)`
- [x] replay 拦截率：`100% (3/3)`
- [x] binding 错误拦截率：`100% (1/1)`
- [x] 伪造签名拦截率：`100% (1/1)`
- [x] 预期进入 PIR 次数：`5`
- [x] 实际进入 PIR 次数：`5`
- [x] 固定样本配比下 PIR 进入比例：`50%`

### Day 35 结论
- [x] 本轮属于“小修收口”，未破坏既有主链
- [x] PIR bridge / verifier / metrics 口径保持一致
- [x] Day 35 已完成“修复 PIR 集成问题、清理 wrapper、稳定主链路”的目标

### Day 35 小收尾
- [ ] 视需要在报告或结果说明中注明：`PIR Entry Proportion = 50%` 仅表示固定 10 个样本配比下的结果，不代表一般流量分布
- [ ] 视需要补一条 malformed PIR response 的定向测试脚本或故障注入用例
- [ ] 视需要将 Day 35 的强类型契约同步到相关设计文档
### Day 38：eBPF 早期过滤规则
- [x] 继续保持 eBPF 第一版仅做轻量前置过滤，不下沉 Redis / blind ticket verify / binding verify / 原子核销
- [x] 在服务器上确认 Day 38 实现继续采用 BCC Python 绑定 + pyroute2 + TC ingress
- [x] 将 TC 过滤目标固定为：
  - [x] 仅看 TCP
  - [x] 仅看目标端口 `8002`
  - [x] 仅挂载到 `eth0 ingress`
- [x] 在 `scripts/tc_gateway.py` 中实现浅层指纹过滤：
  - [x] 以太网 / IPv4 / TCP 解析
  - [x] `ip->ihl >= 5` 防御性检查
  - [x] `tcp->doff >= 5` 防御性检查
  - [x] `payload[0:4] == "HACK"` 时执行 `TC_ACT_SHOT`
- [x] 在 `scripts/tc_gateway.py` 中实现轻量观测信号：
  - [x] 观测 `HTTP POST`
  - [x] 在前 96 字节窗口内扫描 `"ticket"` 关键词
  - [x] `"ticket"` 仅做 trace，不参与 drop 决策
- [x] 收口挂载脚本的工程细节：
  - [x] 检查 `eth0` 是否存在
  - [x] 清理旧 `clsact`
  - [x] 在退出时显式 detach 并打印 cleanup 日志
- [x] 新增外部测试脚本 `scripts/day38_test_client.py`
  - [x] 强制要求传入服务器 `eth0` IP
  - [x] 明确禁止默认 `127.0.0.1`
  - [x] 使用 Python socket 构造 `HACK...` 垃圾流量
  - [x] 使用 Python socket 构造标准 HTTP POST 测试流量
- [x] 服务器侧完成 Day 38 验收：
  - [x] `HACK...` 垃圾流量被 TC 真实丢弃
  - [x] 正常 HTTP POST 可穿过 TC 到达 verifier
  - [x] TC trace 中可观察到 `[TC DROP]` 与 `[TC OBSERVE]`
### Day 39：eBPF 与 verifier 协作
- [x] 新增并跑通 `scripts/test_day39_two_level_defense.py`
- [x] 完成 Day 39 两级防线联调四类流量验证：
  - [x] Case A：`HACK...` 垃圾流量命中 eBPF/TC 提前丢弃
  - [x] Case B：HTTP 候选流量穿过 eBPF，并在 verifier 中被业务拒绝
  - [x] Case C：真实 replay / double spend 被 verifier 状态机拦截
  - [x] Case D：合法流量穿透 fast path + full path，并成功进入真实 PIR
- [x] 验证两级职责边界未漂移：
  - [x] eBPF 只做明显非法流量早拒绝
  - [x] verifier 继续承担完整验证与 consume
- [x] 验证 verifier 仍依赖 Redis 状态机推进：
  - [x] `UNUSED -> PENDING -> CONSUMED`
  - [x] replay 命中 `CONSUMED`
- [x] 验证真实 PIR 后端在 Day 39 联调中成功被调用
- [x] Day 39 验收通过：两级架构联动成功

### Day 39 小收尾
- [ ] Auditor 服务当前未接通，verifier 日志仍出现 `Auditor report failed`
- [ ] 进入 Day 40：前置验证与状态表联动
### Day 40：前置验证与状态表联动
- [x] 保持 Redis / verifier 为唯一业务状态真相源
- [x] 保持 eBPF 第一版不表达 `UNUSED / PENDING / CONSUMED / FAILED`
- [x] 在 `scripts/tc_gateway.py` 中新增来源级短时 blocklist：
  - [x] 使用 `BPF_HASH(blocklist, u32, u64, 2048)`
  - [x] blocklist 仅对 `TCP dport=8002` 生效
  - [x] 内核态仅判定与执行，不做状态删除
- [x] 在 `tc_gateway.py` 中新增本机控制面：
  - [x] 监听 `127.0.0.1:9002/UDP`
  - [x] 接收 `BLOCK <ip> <duration_sec>` 指令
  - [x] 将 verifier 派生的短时封禁同步到 eBPF map
  - [x] 在用户态顺手清理过期条目
- [x] 在 `services/verifier/main.py` 中新增派生信号通道：
  - [x] 通过 `Request` 获取 `client_ip`
  - [x] 新增 `dispatch_l4_block_signal(...)`
  - [x] 仅在 `Ticket already CONSUMED` 分支派生短时 L4 block
  - [x] 不改变 Redis 原有业务决策与 consume 语义
- [x] 新增 `scripts/test_day40_derived_block.py`
  - [x] Case A：静态 `HACK` 指纹 drop
  - [x] Case B：候选 HTTP 流量进入 verifier 并被用户态拒绝
  - [x] Case C：replay 命中 `CONSUMED`，由 verifier 派生 block
  - [x] Case D：同源后续新请求在 8002 入口被 eBPF fast-path drop
- [x] Day 40 验收通过：
  - [x] verifier 仍通过 Redis 判定 replay / consume
  - [x] 控制面出现 `Derived Block Sync from verifier decision`
  - [x] TC trace 出现 `Derived Block: source IP matched short-term L4 blocklist`
  - [x] 新票仍可从 Issuer(8001) 正常获取
  - [x] 发往 Verifier(8002) 的同源后续请求被 fast-path 抑制
- [x] Auditor 在本轮联调中已接通并成功写入审计记录
### Day 41：前置验证效果测试
- [x] 新增 `scripts/test_day41_metrics.py`
- [x] 采用受控顺序执行四类流量，避免 Day 40 的 derived L4 block 污染前序统计：
  - [x] 正常流量
  - [x] 无票据流量
  - [x] 静态恶意指纹流量
  - [x] replay 流量
- [x] 通过 verifier `/metrics` 获取基线与最终指标
- [x] 统计以下指标：
  - [x] `total_requests` 增量
  - [x] `blocked_before_pir` 增量
  - [x] `pir_invoked` 增量
  - [x] `eBPF Gateway Drops (Approx)` 近似值
- [x] Day 41 验收通过：
  - [x] 5 次正常流量全部 `SUCCESS`
  - [x] 5 次无票据流量全部 `REJECTED / Missing Ticket in request`
  - [x] 5 次静态恶意指纹流量主要被 eBPF 前置拦截
  - [x] replay 原始消费成功，首个 replay 进入 verifier 被拒绝，后续 replay 主要被 eBPF derived block 抑制
- [x] Day 41 漏斗统计结果收口为：
  - [x] `Total Traffic Sent Attempts = 21`
  - [x] `HTTP Responses Received = 12`
  - [x] `Reached Verifier (L7) = 12`
  - [x] `Verifier Logic Blocks = 6`
  - [x] `Penetrated to PIR = 6`
  - [x] `eBPF Gateway Drops (Approx) = 9`
### Day 42：本周重构与留档
- [x] 新增 `docs/architecture_defense.md`
- [x] 完成“两级前置验证与防御架构”正式文档整理
- [x] 在文档中落地两张 Mermaid 图：
  - [x] 两级前置验证总览图
  - [x] Normal / Replay + Derived Block 时序图
- [x] 收口 Fast Path / Full Path 职责边界文档：
  - [x] 明确 eBPF / TC 为轻量、无业务状态的 Fast Path 执行器
  - [x] 明确 Verifier / Redis / PIR 为 Full Path 业务验证与状态机中心
  - [x] 明确 Redis 为 Source of Truth
  - [x] 明确 Derived Block 为 verifier 派生动作，而非 eBPF 自主业务决策
- [x] 在 `docs/architecture_defense.md` 中补充 Day 41 漏斗效果与统计口径说明
- [x] 在 `docs/sequence.md` 末尾追加架构文档引用说明
- [x] Day 42 验收通过：
  - [x] 两级前置验证图已留档
  - [x] fast path / full path 文档已留档
### Day 43：恶意客户端 replay 攻击
- [x] 新增 `scripts/test_day43_replay_attacks.py`
- [x] 覆盖两类 replay 攻击场景：
  - [x] 单票据串行重复请求
  - [x] 高并发 replay storm（20 线程）
- [x] 在并发阶段引入 `threading.Barrier`，保证多线程统一起跑
- [x] 为并发 replay 请求生成独立 `request_id`，便于日志区分与排障
- [x] 在脚本中增加配置检查，避免 `acquire_ticket()` 误打本地 loopback
- [x] Phase 1：串行 replay 验证通过
  - [x] 第一次请求 `SUCCESS`
  - [x] 第二次 replay 命中 `CONSUMED`
  - [x] 第三次 replay 被 eBPF derived L4 dampening 压制（TIMEOUT）
- [x] Phase 2：20 线程并发 replay storm 验证通过
  - [x] `SUCCESS = 1`
  - [x] `REJECTED_PENDING = 19`
  - [x] `REJECTED_CONSUMED = 0`
  - [x] `TIMEOUT = 0`
- [x] Day 43 验收通过：
  - [x] 只允许一次成功
  - [x] 未出现 double spend

### Day 44：批量滥用攻击
- [x] 新增 `scripts/test_day44_batch_abuse.py`
- [x] 支持可调压测参数：
  - [x] `--batch`
  - [x] `--concurrency`
- [x] 在每个 phase 中接入 verifier `/metrics`，同时输出：
  - [x] `total_requests` 增量
  - [x] `blocked_before_pir` 增量
  - [x] `pir_invoked` 增量
- [x] 在各 phase 之间加入冷却时间，降低前一轮尾流对后一轮结果的污染
- [x] 修复 Phase 2 污染问题：
  - [x] Phase 1 与 Phase 2 使用两批独立 ticket
  - [x] 确保密码学材料滥用测试基于 fresh unused tickets
- [x] 完成三类批量滥用测试：
  - [x] Phase 1：大量合法请求压测 full path
  - [x] Phase 2：伪签名 / 错误 binding 滥用请求
  - [x] Phase 3：无票据 / 缺 witness 候选请求
- [x] Day 44 验收通过：
  - [x] 合法洪峰 `100/100` 成功进入 PIR
  - [x] 伪签名 / 错误 binding `100/100` 在 verifier 前置拦截，`0` 进入 PIR
  - [x] 无票据 / 缺 witness `100/100` 在 verifier 前置拦截，`0` 进入 PIR
### Day 45：恶意 verifier 状态篡改测试
- [x] 新增 `scripts/test_day45_malicious_verifier.py`
- [x] 支持运行环境目标提示：
  - [x] 明确 Auditor 目标地址
  - [x] 明确 Redis 目标地址
  - [x] 提醒当前环境必须能直连目标 Redis / Auditor
- [x] 场景 A：幽灵核销（Ghost Consumption）验证通过
  - [x] 直接篡改 Redis 中票据状态为 `CONSUMED`
  - [x] 故意不向 Auditor 写入审计记录
  - [x] 通过外部对账发现：
    - [x] Redis = `CONSUMED`
    - [x] Auditor trace = `404`
- [x] 场景 B：承诺篡改（Commitment Tampering）预演通过
  - [x] 恶意写入篡改后的 `query_commitment`
  - [x] Auditor 成功入账
  - [x] 通过 `expected_cq` 查询得到 `cq_consistent = false`
- [x] Day 45 主验收通过：
  - [x] 能发现状态与日志不一致
- [x] Day 46 预演收获：
  - [x] Auditor trace 一致性字段可发现承诺篡改
### Day 46：恶意服务端伪造执行记录测试
- [x] 新增 `scripts/test_day46_malicious_audit.py`
- [x] 模拟跨证据源执行记录矛盾：
  - [x] Redis 执行真相为 `CONSUMED`
  - [x] Auditor 审计记录伪造为 `FAILED`
- [x] 在 `trace/{sn}` 查询中接入 `expected_cq`
- [x] 验证可发现：
  - [x] 状态矛盾
  - [x] `query_commitment` 关联矛盾
- [x] 模拟离线账本篡改：
  - [x] 复制账本副本
  - [x] 定位目标 `SN`
  - [x] 篡改 `query_commitment`
- [x] 实现基于 Day 25 契约的完整性校验：
  - [x] 校验 `prev_hash` 链连续性
  - [x] 校验 `entry_mac` 内容完整性
  - [x] 严格对齐 MAC payload：`sn|query_commitment|decision|timestamp_ms|prev_hash`

### Day 46 验收结果
- [x] 成功发现跨证据源最小一致性问题
- [x] 成功发现离线账本篡改导致的链断裂
- [x] Day 46 验收通过：`能发现最小一致性问题`

### Day 46 结论
- [x] 当前原型已具备“最小一致性发现”能力
- [x] 当前能力边界仍保持在：
  - [x] 最小争议验证
  - [x] 最小篡改留痕
- [x] 不扩展为完整 verifiable execution 机制
- 

## 当前项目状态总结 
- Issuer blind-sign 已跑通
- Client ticket acquisition 已跑通
- Verifier ticket signature verification 已跑通
- Day 11 Binding 校验已完成
- Day 12 Redis 原子防重放与状态流转已完成
- Day 12 生命周期 4 条关键分支已通过联调验收
- Day 13 blind-sign 全链路正反例已通过
- Day 13+ 第一阶段 Verifier -> PIR Server 网络桥接已落地
- Day 14 第一批 blind-sign / verify 核心单测已通过（6 passed）
- Day 16 admission primitive 第一版已落地并通过反例验收
- Day 17 blind ticket + admission 已整合进签票主链
- Day 18 epoch 时间窗已接入 Ticket 与 Verifier 验证路径
- Day 19 binding 生成已正式接入 RequestInstance 构造流程
- Day 20 verifier 侧 binding verify 已真实生效
- Day 21 本周联调已完成，happy path / missing ticket / expired ticket / tampered binding 已可真实区分
- Day 22 Redis 状态表与状态查询接口已收口
- Day 23 `UNUSED -> PENDING` 原子核销并发验收已通过
- Day 24 判定路径绑定原子核销已通过验收
- Day 25 tamper-evident 审计日志已通过验收
- Day 26 Auditor 查询接口已通过验收
- Day 27 最小争议验证闭环已通过验收
- Day 28 verifier 阶段重构已最终收口
- Day 29 真实主候选 PIR 已正式接入
- Day 31 请求实例与 PIR 输入对齐第一轮收口已完成
- Day 32 主链 happy path 已可返回真实 PIR 结果
- Day 33 非法请求不进入 PIR 的隔离验证已通过
- Day 34 第一轮功能性指标已可自动化产出并完成对账
- Day 35 缓冲 / 修复日收口完成，PIR 响应类型与 verifier 防御性检查已稳定落地
- Day 36 eBPF 第一版职责范围已固定
- Day 37 eBPF 环境搭建与最小 hello-ebpf 验证已完成
- Day 38 TC 挂载的第一版轻量前置过滤已打通
- Day 39 eBPF fast path 与 verifier full path 两级架构联动已验证成立
- Day 40 来源级短时 derived block 联动已成立
- Day 41 两级前置验证漏斗效果已完成第一轮量化测试
- Day 42 两级前置验证架构文档化与重构收口已完成
- Day 43 replay 攻击实验已完成，串行 replay 与并发 replay storm 下均只允许一次成功
- Day 44 batch abuse / full path 承压测试已完成，批量 abuse 请求未穿透到 PIR
- 当前项目已形成：blind-sign + admission + binding + verifier + PIR + audit + eBPF fast path 的阶段性闭环
- 当前审计已从本地日志存根推进到：链式 HMAC 留痕 + Auditor trace + 最小争议验证闭环
- 下一阶段重点：端到端周回归脚本 / 攻击实验扩展 / PIR 协议最终收口