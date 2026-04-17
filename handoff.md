# Session Handoff

## 当前项目状态
当前项目为 PIR 匿名抗滥用访问控制原型。

已完成：
- 项目迁移到 WSL Linux 文件系统
- Git 初始化与持续提交
- 各服务独立 `.venv`
- 5 个服务统一 bootstrap
- 统一 YAML 配置
- 统一 logging
- `common/config.py` 与 `common/logging_utils.py`
- Day 6 文档基本定稿

当前服务：
- issuer
- client
- verifier
- pir_server
- auditor

## 已确认不变的前提
- 主线：blind ticket -> admission -> binding -> verifier -> PIR -> audit
- blind signature：RSA blind signature
- PIR 后端：独立进程 / 微服务集成
- 状态机：UNUSED / PENDING / CONSUMED / FAILED
- eBPF 第一版：轻量前置过滤
- Python 服务：统一 YAML 配置 + logging

## 当前文档进度
已基本定稿：
- `docs/stack.md`
- `docs/blind_signature_choice.md`
- `docs/pir_backend_choice.md`

正在推进：
- `docs/object_model.md`
- `docs/api.md`
- `docs/sequence.md`

## 当前最推荐的下一步
1. 完成 `docs/object_model.md`
2. 完成 `docs/api.md`
3. 完成 `docs/sequence.md`
4. 落地 `common/models.py`
5. 再进入 FastAPI / blind signature / Redis / PIR 实现

## 当前不要做的事
- 不推翻当前主线
- 不换 blind signature 主方案
- 不把 PIR 后端改成进程内硬绑定
- 不提前把 eBPF 做复杂
- 不用 Mock PIR 作为最终评估后端
- 不跳过对象模型和 API 直接堆业务代码

## 新窗口首发建议
新窗口第一条消息附带：
- `context.md`
- 最近的 `devlog.md`
- 当前相关文档
- 当前相关代码
- 当前问题

并要求：
- 先复述当前项目状态
- 先确认不应改动的前提
- 再给修改建议