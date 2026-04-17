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

- Binding 验证
- Redis 原子防重放与票据生命周期流转
- Verifier -> PIR Server 的第一阶段网络桥接

当前已完成：

- Issuer blind-sign API
- Client blind / unblind 与 ticket acquisition
- Verifier RSA signature verification
- Binding Tag 生成与校验
- Redis 原子防重放与票据生命周期流转
- PIR Server HTTP 适配层（Stub）
- Verifier 跨服务调用 PIR Server
- 审计本地日志存根

当前 Day 12 生命周期在跨服务模式下已再次通过 4 条关键验收：

1. 并发冲突命中 `PENDING`
2. PIR 执行失败后票据转 `FAILED`
3. 正常执行后票据转 `CONSUMED`
4. 前置验证失败不吞票，票据保持 `UNUSED`

因此，当前项目已经从“本地 stub 语义的 verifier”进入“可将合法请求跨服务转发至 PIR Server，并基于真实远端结果推进状态”的阶段。


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

### 4. Issuer 公钥的当前约束
当前 Issuer 第一版为了简化原型：

- 服务启动时在内存中动态生成 RSA key pair
- 每次重启都会更换 key

因此当前 Verifier 采取的策略是：

- 启动时主动向 Issuer 拉取公钥
- 本地缓存 `(n, e)`
- 若刷新失败，则清空缓存，避免带着旧 key 工作

这只是当前原型阶段策略，后续若进入稳定阶段需要考虑持久化或固定 key 管理。

---

## 四、当前 Verifier 的真实语义边界

当前 `/api/v1/verifier/execute` 已具备如下真实语义：

当前已做：

- 接收 `RequestInstance`
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
- 前置验证失败：请求被拒绝，但票据状态保持 `UNUSED`

当前审计语义：

- Verifier 已开始在本地组装审计分录存根
- 当前仅以日志形式留痕
- Auditor HTTP 投递尚未接入主链路

当前仍未完全做完：

- Auditor 服务 HTTP 存根
- Verifier -> Auditor 的后台上报
- 审计查询接口
- 真实 Go SimplePIR 进程 / 微服务集成（当前仍为 Python stub adapter）

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

但当前阶段真正生效的只有：

- `request_id`
- `ticket`

`binding_tag` 和 `witness` 将在 Day 11 开始进入真实验证逻辑。

---

## 六、当前测试与验收状态

### 已通过的验证
1. Issuer API 可工作
2. Client 可成功获取合法 Ticket
3. Client 本地验签通过
4. Verifier 可对合法 Ticket 验签通过
5. Verifier 可拒绝篡改 `SN`
6. Verifier 可拒绝篡改 `sigma`

### 已有脚本
- `scripts/test_ticket_flow.sh`
  - 用于验证 Day 9 ticket 获取链路
- `scripts/test_day10_verifier.py`
  - 用于验证 Day 10 verifier 正反例链路

---

## 七、当前最值得继续推进的方向

### 下一阶段：Auditor / 审计闭环（第二阶段）
目标：

- 在不破坏当前已稳定的 Verifier -> PIR Server 主链路的前提下
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

以下内容已经通过文档、实现与联调逐步固化，短期内不应轻易推翻：

- blind signature 第一版使用 RSA blind signature
- 主线仍为 `blind ticket -> admission -> binding -> verifier -> PIR -> audit`
- ticket 结构仍为 `t = (SN, sigma, EpochID)`
- ticket 被签消息编码仍为 `SN || EpochID`
- 状态机仍为 `UNUSED / PENDING / CONSUMED / FAILED`
- PIR 后端仍保持独立进程 / 微服务集成方向
- eBPF 仍只做轻量前置过滤
- 当前审计仍先走最小存根，再逐步接后台投递
- 项目继续优先“小修收口”，避免中途大重构

## 八、当前不应轻易改动的部分

以下内容已经通过文档与联调逐步固化，短期内不应轻易推翻：

- blind signature 第一版使用 RSA blind signature
- ticket 结构仍为 `t = (SN, sigma, EpochID)`
- ticket 被签消息编码仍为 `SN || EpochID`
- `sigma` 仍以 Base64 形式存储于 Ticket
- Verifier 当前先做前置验证，再逐步接 Binding / Redis / PIR
- PIR 后端仍保持独立服务方向
- eBPF 仍只做轻量前置过滤
- 项目继续优先“小修收口”，避免中途大重构

---

## 九、当前一句话状态总结

当前项目已完成：

- **Issuer blind-sign**
- **Client ticket acquisition**
- **Verifier ticket signature verification**
- **Binding Tag verification**
- **Redis 原子防重放与生命周期状态机**
- **Verifier -> PIR Server 网络桥接（第一阶段）**

并已确认 Day 12 生命周期在跨服务模式下回归通过。

当前下一步应集中到：

- **Auditor HTTP 存根与最小审计闭环**
- **PIR 适配层协议收口与真实后端边界对接**