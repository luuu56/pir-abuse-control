# Dev Log

## 2026-04-17

### 完成
- 项目迁移到 WSL Linux 文件系统
- 5 个服务统一 bootstrap
- common/config.py 与 common/logging_utils.py 完成
- Day 6 文档基本定稿：stack / blind_signature_choice / pir_backend_choice

### 当前状态
- 所有服务可通过模块方式启动
- 统一 YAML 配置与 logging 已接通

### 已验证通过
- issuer / verifier / client / pir_server / auditor 均可正常启动
- PyCharm 已连接 WSL 项目与对应解释器

### 遇到的问题
- 直接运行脚本路径会触发 common 包导入问题
- 已改为 python -m services.xxx.main 方式运行

### 下一步
- 完成 docs/object_model.md
- 完成 docs/api.md
- 完成 docs/sequence.md
## Day 8：Issuer 签发核心 API 打通
**日期**：[填写今日日期]

**完成内容**：
1. **密码学基座**：在 `services/issuer/crypto.py` 中实现了 `IssuerCryptoManager`，基于 `pycryptodome` 落地了 Textbook RSA 模幂运算（盲签核心）。
2. **API 骨架**：使用 FastAPI 搭建了 `/api/v1/issuer/challenge` 和 `/api/v1/issuer/issue` 接口。
3. **数据清洗与约束**：通过 Pydantic 锁死了公钥和签名的输出格式（无 `0x` 前缀、纯小写、左补零对齐 512 字符模长），并增加了对输入 `blinded_message` 的容错解析。

**关键决策/记录**：
* 明确了当前阶段每次启动都会重新生成 RSA 密钥，仅供联调使用，历史票据重启即失效。
* 明确了 Issuer 端只做边界检查，盲因子 $r$ 的可逆性由后续 Client 负责保证。
* ## Day 9：Client 盲签请求与去盲链路闭环
**日期**：2026-04-17 (示例)

**完成内容**：
1. **密码学健壮性**：在 `crypto.py` 中增加了输入校验及 `m < n` 边界检查；在 `main.py` 成功实现了本地验签逻辑 `pow(s, e, n) == m`，确保了去盲结果的准确性。
2. **Hex 解析修复**：修正了 `pad_len` 的获取逻辑，去除了 Issuer 返回值中可能存在的 `0x` 前缀干扰。
3. **配置解耦**：将 `ISSUER_URL` 接入 `base.yaml` 配置系统，增加了 HTTP 请求超时控制。

**关键记录**：
* 通过本地自验签确认，`SN || EpochID` 的拼接方式在盲签流程下工作正常。
* 下一步将开始 Verifier 侧的公钥验签实现，需要注意从 Ticket.sigma (Base64) 转换回 RSA 验签所需的整数格式。
* ## Day 10：Verifier 票据验签与端到端联调闭环
**日期**：[填写今日日期]

**完成内容**：
1. **单一事实来源**：在 `common/crypto_utils.py` 中抽象了 `encode_ticket_message`，彻底消除了 Client 和 Verifier 之间的双份编码实现，确保了跨服务契约同构。
2. **前置验证骨架**：在 `services/verifier/main.py` 实现了 `/execute` 接口，并增加了 Issuer 公钥拉取失败时的“毒缓存清空”机制。
3. **安全拦截强化**：实现了严格的 Base64 验证与签名大整数边界检查 (`1 <= s < n`)。
4. **回归测试脚本**：编写了 `scripts/test_day10_verifier.py`，分别针对 Happy Path、SN 篡改（合法 Hex 变异）和 Sigma 篡改（合法 Base64 变异）进行了自动化测试验证。

**关键决策**：
* 明确了当前阶段 `/execute` 返回的 `SUCCESS` 仅代表前置验证（Stub）通过。待后续集成 Redis 后，此语义将收紧为“全流程执行完毕”。
* 