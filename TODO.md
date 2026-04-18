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
- 当前审计仍为本地日志存根
- 下一阶段重点：Auditor HTTP 存根 + 审计闭环