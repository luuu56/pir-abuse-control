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