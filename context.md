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
- Binding 验证
- Redis 原子防重放与票据生命周期流转
- Verifier -> PIR Server 的第一阶段网络桥接
- blind-sign 主链路的第一批核心单测与错误码 / API 收口

当前已完成：

- Issuer blind-sign API
- Issuer admission challenge / verify_admission / issue 内联 admission 校验
- Issuer 公钥真实接口：`GET /api/v1/issuer/public_key`
- Client blind / unblind 与 ticket acquisition
- Client 侧 admission -> blind issue -> unblind -> local verify 整合主链
- epoch 时间窗配置与统一 epoch 公共函数
- Ticket 中 `epoch_id` 的动态计算与有效性校验
- Verifier RSA signature verification
- Binding Tag 生成与校验
- Redis 原子防重放与票据生命周期流转
- PIR Server HTTP 适配层（Stub）
- Verifier 跨服务调用 PIR Server
- 审计本地日志存根
- blind-sign / verify 第一批核心单测

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

因此，当前项目已经从“本地 stub 语义的 verifier”进入“blind-sign 主链稳定、admission 第一版落地并已并入签票主链、epoch 时间窗已正式接入、生命周期状态机稳定、并可跨服务转发至 PIR Server”的阶段。

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

### 6. Issuer 公钥的当前约束
当前 Issuer 第一版为了简化原型：

- 服务启动时在内存中动态生成 RSA key pair
- 每次重启都会更换 key

因此当前 Client / Verifier 采取的策略是：

- 从 Issuer 真实网络接口获取公钥
- 不再依赖本地硬编码公钥 stub
- 若刷新失败，则拒绝继续基于旧 key 工作

这只是当前原型阶段策略，后续若进入稳定阶段需要考虑持久化或固定 key 管理。

---

## 四、当前 Verifier 的真实语义边界

当前 `/api/v1/verifier/execute` 已具备如下真实语义：

当前已做：

- 接收 `RequestInstance`
- 在最前面执行 epoch 快拒绝
- 提取并校验 `ticket`
- 校验 RSA 签名是否有效
- 校验 binding 是否一致
- 查询并推进 Redis 状态机
- 在进入后端执行前将票据原子推进为 `PENDING`
- 通过 HTTP 将合法请求转发至 `PIR Server`
- 根据 PIR Server 返回结果将票据推进为：
  - `CONSUMED`
  - `FAILED`

当前拒绝语义已明确：

- `PENDING`：表示 in-flight / 并发 replay
- `CONSUMED`：表示 double spend / replay after success
- `FAILED`：表示 burned ticket / replay after execution failure
- epoch 失效：请求在主验证前被业务拒绝
- 前置验证失败：请求被拒绝，但票据状态保持 `UNUSED`

当前审计语义：

- Verifier 已开始在本地组装审计分录存根
- 当前仅以日志形式留痕
- Auditor HTTP 投递尚未接入主链路

当前 blind-sign 语义：

- blind-sign 已成为唯一主线
- 不再保留普通签名占位路径
- 核心 blind-sign / verify 契约已开始由 `pytest` 单测稳定回归

当前仍未完全做完：

- Auditor 服务 HTTP 存根
- Verifier -> Auditor 的后台上报
- 审计查询接口
- 真实 Go SimplePIR 进程 / 微服务集成（当前仍为 Python stub adapter）

---

## 五、当前对象与请求模型状态

当前仍对齐既定对象模型：

### Ticket
- `t = (SN, sigma, EpochID)`

### RequestInstance
- `r = (q, t, b, w)`

当前 `RequestInstance` 已具备字段骨架：

- `request_id`
- `query_payload`
- `ticket`
- `binding_tag`
- `witness`

当前这些字段均已进入真实链路：

- `request_id`：用于请求跟踪
- `ticket`：用于 blind-sign 验签、epoch 校验与生命周期状态机
- `binding_tag`：用于 binding 一致性校验
- `witness`：用于 binding 材料规范化与验证

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

---

## 六、当前测试与验收状态

### 已通过的验证
1. Issuer API 可工作
2. Client 可成功获取合法 Ticket
3. Client 本地验签通过
4. Verifier 可对合法 Ticket 验签通过
5. Verifier 可拒绝篡改 `SN`
6. Verifier 可拒绝篡改 `sigma`
7. Binding 正反例已通过
8. Day 12 生命周期 4 条关键分支已通过
9. Day 13 blind-sign 全链路正反例已通过
10. Day 14 `tests/test_crypto_core.py` 已通过（6 passed）
11. Day 16 admission primitive 第一版反例验收已通过
12. Day 17 blind ticket + admission 整合链路已通过
13. Day 17+ 全链路烟雾测试已通过
14. Day 18 epoch 时间窗过期拒绝验收已通过

### 已有脚本 / 测试
- `scripts/test_ticket_flow.sh`
  - 验证 Day 9 ticket 获取链路
- `scripts/test_day10_verifier.py`
  - 验证 Day 10 verifier 正反例链路
- `scripts/test_day11_binding.py`
  - 验证 binding 正反例
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

---

## 七、当前最值得继续推进的方向

### 下一阶段：端到端联调 / 回归巩固（优先）
目标：

- 在主链刚刚完成 `blind ticket + admission + epoch` 收口的前提下，先巩固整体回归能力
- 避免在主链尚未稳定前过早引入更复杂的审计与兼容性逻辑

需要完成：

1. 继续完善端到端联调 / 回归脚本
2. 固化 Day 17+ / Day 18 主链的最小回归集合
3. 验证：
   - admission 缺失失败
   - challenge 重放失败
   - blind issue 正常成功
   - binding 正常成功
   - verifier 放行成功
   - PIR success / failure 分支均与状态机一致
   - epoch 过期分支被前置快拒绝
4. 保证主链刚打通时不被后续高级功能回归打坏

### 再下一阶段：Auditor / 审计闭环（第二阶段）
目标：

- 在不破坏当前已稳定的 blind-sign 主链路、admission 第一版、epoch 时间窗、生命周期状态机与 Verifier -> PIR Server 网络桥接的前提下
- 为放行 / 拒绝 / 核销结果增加可接收、可查询、可追溯的最小审计落点

需要完成：

1. 建立 `services/auditor/main.py`
2. 暴露 `/api/v1/auditor/report`
3. 将当前 `[Audit Stub]` 升级为后台 HTTP 上报
4. 明确 `AuditRecord` 字段与 `common.models` 对齐
5. 验证 Auditor 不可用时不影响 Verifier 主返回

### 再下一阶段：PIR 协议与真实后端收口（第三阶段）
目标：

- 将当前 Python stub adapter 逐步推进到真实 PIR 后端边界

需要完成：

1. 抽取 PIR 请求/响应公共模型
2. 明确 Python 控制层与 PIR 适配层的正式输入输出协议
3. 将当前 `pir_server` stub 与真实 Go SimplePIR 调用边界对接
4. 保持 `SUCCESS / FAILED` 与真实 PIR 执行结果绑定

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
- PIR 后端仍保持独立进程 / 微服务集成方向
- eBPF 仍只做轻量前置过滤
- 当前审计仍先走最小存根，再逐步接后台投递
- 项目继续优先“小修收口”，避免中途大重构

---

## 八、当前一句话状态总结

当前项目已完成：

- **Issuer blind-sign**
- **Client ticket acquisition**
- **Admission primitive 第一版**
- **blind ticket + admission 整合**
- **epoch 时间窗接入**
- **Verifier ticket signature verification**
- **Binding Tag verification**
- **Redis 原子防重放与生命周期状态机**
- **Verifier -> PIR Server 网络桥接（第一阶段）**
- **blind-sign / verify 第一批核心单测**

并已确认 Day 12 生命周期在跨服务模式下回归通过、Day 13 blind-sign 全链路联调完成、Day 14 第一批核心单测通过、Day 16 admission primitive 第一版反例验收通过、Day 17 blind ticket + admission 整合与 Day 17+ 全链路烟雾测试通过、Day 18 epoch 过期票据拒绝验收通过。

当前下一步应集中到：

- **端到端联调 / 回归巩固**
- **Auditor HTTP 存根与最小审计闭环**
- **PIR 适配层协议收口与真实后端边界对接**