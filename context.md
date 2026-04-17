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

当前项目已经完成从 **Issuer -> Client -> Verifier** 的第一段闭环，且已经通过端到端联调验证。

当前已完成：
### Day 1：开发环境搭建
已完成：

- 项目开发环境已迁移到 **WSL Linux 文件系统**
- 当前主目录位于：
  - `/home/lu56/pir-abuse-control`
- 已确认：
  - Python 可正常运行
  - Git 可正常运行
  - PyCharm 已连接到 WSL 项目目录
  - 运行解释器已指向各服务自己的 `.venv`

当前环境分层约定：

- 前期开发与联调：WSL2 Ubuntu
- 后续 eBPF/XDP 与正式性能评估：原生 Linux / 远程服务器

### Day 2：项目初始化与 Git 建仓
已完成：

- Git 仓库初始化完成
- 基础目录结构完成
- `.gitignore` 已建立
- `README.md`、`TODO.md`、`devlog.md` 已建立
- 项目已经开始持续 commit

当前目录结构主干已固定为：

- `common/`
- `services/`
  - `issuer/`
  - `client/`
  - `verifier/`
  - `pir_server/`
  - `auditor/`
- `experiments/`
- `configs/`
- `scripts/`
- `logs/`
- `results/`
- `docs/`

### Day 3：环境隔离
已完成：

- 各服务独立 `.venv` 已创建：
  - `services/issuer/.venv`
  - `services/client/.venv`
  - `services/verifier/.venv`
  - `services/pir_server/.venv`
  - `services/auditor/.venv`
  - `experiments/.venv`
- 各服务 `requirements.txt` 已建立
- 当前所有服务均以“模块独立环境”的方式运行

当前工程约束：

- 不同服务不得长期混用同一 Python 环境
- 依赖安装应尽量写回各自 `requirements.txt`

### Day 4：PyCharm 接入 WSL 工程
已完成：

- PyCharm 已切换到 WSL Linux 文件系统中的项目目录
- 当前工程不再使用 Windows 盘路径 `E:\...` 作为主开发视图
- 至少 `issuer / verifier / client` 等服务已能在 PyCharm 中通过各自解释器正常运行
- 模块运行方式已统一为：

```bash
python -m services.issuer.main
python -m services.client.main
python -m services.verifier.main
python -m services.pir_server.main
python -m services.auditor.main
```
当前约束：

- 不再推荐直接执行脚本路径 `python services/xxx/main.py`
- 统一使用 `python -m services.xxx.main` 以避免包导入路径漂移

### Day 5：统一配置与日志骨架

已完成：

- 已建立统一配置文件：
  - `configs/common/base.yaml`
- 已建立公共模块：
  - `common/config.py`
  - `common/logging_utils.py`
- 所有核心服务已统一接入：
  - YAML 配置读取
  - 标准 logging 输出
- 当前各服务 bootstrap 已统一，并已成功生成对应日志文件

当前固定工程约束：

- 所有 Python 服务都必须使用统一 YAML 配置
- 所有 Python 服务都必须使用统一 logging 格式
- 公共配置与日志初始化逻辑统一复用 `common/` 下模块
- 不允许各服务后续各自私建独立的配置/日志风格

### Day 6：关键技术选型定稿

以下文档已经基本定稿：

1. `docs/blind_signature_choice.md`

已确认：

- 第一版 blind signature 固定为 RSA blind signature
- 第一版基于 `pycryptodome` 提供 RSA 基础能力
- 盲化、签发、去盲、验证流程由项目侧自行落地
- 完整验签逻辑位于用户态 Verifier
- eBPF 层不承担非对称加密验签

2. `docs/pir_backend_choice.md`

已确认：

- 主候选 PIR 后端：**SimplePIR**
- 备选：Spiral 或轻量级真实 PIR baseline
- Mock PIR 仅允许用于前期控制链联调
- **Mock PIR 严禁**作为最终实验或论文评估后端
- PIR 后端采用：
  - 独立进程 / 微服务集成
  - 由 `pir_server` 通过 subprocess / 本地 Socket / RPC 调用

3. `docs/stack.md`

已确认：

- 当前开发语言：Python 3.13
- 控制层服务：FastAPI + Uvicorn
- 状态存储：Redis
- 控制层通信：HTTP JSON
- 数据执行层：PIR 独立进程集成
- `common`、`issuer`、`verifier`、`client`、`pir_server`、`auditor` 的依赖边界已基本明确

### Day 7：对象模型、接口和时序草案对齐

当前 Day 7 文档已进入“接近定稿/持续收口”状态，主要包括：

1. `docs/object_model.md`

已逐步对齐的核心对象：

- Ticket：`t = (SN, sigma, EpochID)`
- RequestInstance：`r = (q, t, b, w)`
- 状态机：
  - UNUSED
  - PENDING
  - CONSUMED
  - FAILED
- 绑定语义：
  - `c_q = H(q)`
  - `b = HMAC(sk_t, c_q || w)`

2. `docs/api.md`

已逐步对齐的服务边界：

- Issuer
- Verifier
- PIR Server
- Auditor

3. `docs/sequence.md`

已逐步明确的执行链：

- Issuance
- Binding
- Request
- Pre-Verify
- Atomic Lock
- Forward
- Execute
- Finalize
- Audit
- Response

4. `common/models.py`

已开始承接工程级对象定义，用于后续 FastAPI / schema / verifier 逻辑实现。
### Day 8：Issuer Blind-Sign API**
   - `services/issuer/crypto.py` 已完成
   - `services/issuer/main.py` 已完成
   - `/api/v1/issuer/challenge` 可返回 `challenge + epoch_id + public_key`
   - `/api/v1/issuer/issue` 可对 blinded message 执行 textbook RSA 模幂签名

 ### Day 9：Client Blind/Unblind & Ticket 获取**
   - `services/client/crypto.py` 已完成
   - `services/client/main.py` 已完成
   - 已实现：
     - `SN` 生成
     - `SN || EpochID` 编码
     - 盲因子 `r` 生成
     - blind / issue / unblind
     - 本地验签 `pow(s, e, n) == m`
   - 可成功组装 `Ticket(sn, sigma, epoch_id)`

 ### Day 10：Verifier 票据验签**
   - `common/crypto_utils.py` 已新增
   - `services/verifier/crypto.py` 已完成
   - `services/verifier/main.py` 已完成
   - Verifier 启动时可从 Issuer 拉取并缓存公钥
   - `/api/v1/verifier/execute` 当前已实现 **RSA 签名验证前半段**
   - 端到端正反例联调已通过：
     - 合法 Ticket -> `SUCCESS`
     - 篡改 `SN` -> `REJECTED`
     - 篡改 `sigma` -> `REJECTED`

### 

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

当前 `/api/v1/verifier/execute` 的实现仍是 **Day 10 stub 版本**：

已做：

- 接收 `RequestInstance`
- 提取 `ticket`
- 校验 RSA 签名是否有效

未做：

- Binding Tag 验证
- Redis 原子防重放
- 状态流转
- PIR 转发
- Auditor 写入

因此当前返回：

- `SUCCESS`

只表示：

- **票据签名验证通过**

并不表示：

- 绑定验证已通过
- 票据已消费
- PIR 已执行成功

后续必须用完整流程替换当前 stub 语义。

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

### 下一阶段：Day 11 - Binding 验证
目标：

- 开始让 `binding_tag` 与 `query_payload / witness / ticket` 产生真实约束

需要完成：

1. 明确 `sk_t` 的工程派生方式
2. 实现 `query_commitment = H(q)`
3. 明确 Witness 的规范化序列化方式
4. 实现 `binding_tag = HMAC(sk_t, c_q || w)`
5. 在 Verifier 中加入 binding 校验

### 再下一阶段：Day 12 - Redis 状态机与防重放
目标：

- 从“只验签”进入“可消费 ticket 的 verifier”

需要完成：

1. 接入 Redis
2. 实现 `SETNX SN PENDING`
3. 明确状态流转：
   - `UNUSED -> PENDING`
   - `PENDING -> CONSUMED`
   - `PENDING -> FAILED`
4. 明确拒绝语义：
   - `PENDING` -> in-flight / replay
   - `CONSUMED` -> double spend
   - `FAILED` -> burned ticket

---

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

并已通过 Day 10 正反例端到端联调。

当前下一步应集中到：

- **Binding Tag 验证**
- **Redis 原子防重放与状态流转**