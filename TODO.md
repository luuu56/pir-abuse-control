# 原型开发任务清单 (TODO)

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

- [x] **Day 6：关键技术选型定稿**
  - [x] 产出 `docs/blind_signature_choice.md` (确立 RSA 盲签为主线方案，Verifier 用户态验签边界)
  - [x] 产出 `docs/pir_backend_choice.md` (确立 SimplePIR 主候选与备选方案，严格限制 Mock 引擎用途)
  - [x] 产出 `docs/stack.md` (确立 FastAPI + Redis 技术栈与按服务划分的依赖规范)

- [x] **Day 7：核心对象模型与状态机定稿**
  - [x] 产出 `docs/object_model.md` (确立票据四状态终态约束，明确 `sk_t` 派生规则及 `w` 的序列化约束)
  - [x] 产出 `docs/api.md` (统一 `/api/v1/` 风格与服务边界)
  - [x] 产出 `docs/sequence.md` (更新系统全链路时序与持久化异常处理原则)
  - [x] 落地 `common/models.py` (基于 Pydantic 建立 `Ticket`, `RequestInstance`, `AuditRecord` 等工业级模型)

## 第 2 周：基础控制链路实现

- [x] **Day 8：Issuer 盲签 API 骨架**
  - [x] 引入 `pycryptodome`，在 `services/issuer/crypto.py` 中落地 Textbook RSA 模幂运算基座
  - [x] 实现 `/api/v1/issuer/challenge` 和 `/api/v1/issuer/issue` 路由
  - [x] 统一 `blinded_message` 和签名输出的 Hex 规范化约束 (无 `0x` 前缀、小写、左补零)
- [x] Day 9：Client 盲化请求与去盲 (完成 SN+Epoch 绑定盲化、本地自验签、修正 hex 补齐逻辑)
- [x] Day 10：Verifier 票据验签与前置验证骨架 (完成公钥动态获取、同构重组验证、异常拦截及端到端联调脚本)
- [ ] Day 11：票据绑定机制 (c_q 和 binding tag 的计算与验证)