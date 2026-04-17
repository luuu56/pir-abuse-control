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

## 进行中 / 下一步

### Day 11：Binding 验证
- [ ] 明确 `sk_t` 的工程派生实现
- [ ] 实现 `query_commitment = H(q)`
- [ ] 实现 Witness 规范化序列化
- [ ] 实现 `binding_tag = HMAC(sk_t, c_q || w)`
- [ ] 在 Verifier 中加入 binding 校验
- [ ] 增加正反例：
  - [ ] 正确 binding 通过
  - [ ] 篡改 `query_payload` 被拒绝
  - [ ] 篡改 `witness` 被拒绝
  - [ ] 篡改 `binding_tag` 被拒绝

### Day 12：Redis 防重放与状态流转
- [ ] 接入 Redis
- [ ] 实现 `SETNX SN PENDING`
- [ ] 实现状态流转：
  - [ ] `UNUSED -> PENDING`
  - [ ] `PENDING -> CONSUMED`
  - [ ] `PENDING -> FAILED`
- [ ] 明确拒绝分支：
  - [ ] `PENDING` -> in-flight / replay
  - [ ] `CONSUMED` -> double spend
  - [ ] `FAILED` -> burned ticket
- [ ] 增加状态机联调测试

### Day 13+：Auditor / PIR 串联
- [ ] 定义审计记录写入时机
- [ ] 完成 Verifier -> Auditor 的 report 接口打通
- [ ] 接入 PIR Server stub
- [ ] 将当前 verifier stub success 替换为真实 PIR 转发结果
- [ ] 完成 `SUCCESS / FAILED` 与 PIR 执行结果绑定

---

## 小收口（非阻塞）
- [ ] 将 FastAPI `@app.on_event("startup")` 逐步替换为 lifespan
- [ ] 测试脚本统一从配置读取 URL / timeout
- [ ] 补充 `devlog.md`：记录 Day 9 / Day 10 正反例联调结论
- [ ] 将 Day 10 已验证的 Ticket 编码与 sigma 编码约定同步到文档
- [ ] 增加 verifier 单元测试（纯函数级验签测试）

---

## 当前项目状态总结
- Issuer blind-sign 已跑通
- Client ticket acquisition 已跑通
- Verifier ticket signature verification 已跑通
- Day 10 已通过端到端正反例验收
- 下一阶段重点：Binding + Redis 原子防重放