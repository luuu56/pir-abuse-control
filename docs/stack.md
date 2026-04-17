# 全局技术栈与接口规范 (Technology Stack & API Style)

## 1. 核心语言与环境
* **语言**：Python 3.13 (当前开发环境)，原则上兼容 Python 3.10+。
* **底层系统**：前期开发和联调在 WSL2 (Ubuntu 22.04) 中完成；eBPF/XDP 与正式性能评估迁移至原生 Linux 环境。

## 2. 服务接口风格
* **控制层服务** (Issuer, Verifier, Auditor)：采用 **FastAPI + Uvicorn**，通过 **HTTP JSON** 进行 RESTful 通信。
* **数据执行层** (PIR Server ↔ 真实 PIR 引擎)：采用独立进程集成方式，根据后端实现选择 subprocess、本地 Socket 或 RPC。

## 3. 状态存储方案 (State Storage)
* **组件**：**Redis** (用于实现票据的原子核销，防御双花攻击)。

## 4. 细分服务依赖清单
* **common**: `PyYAML`, `pydantic`
* **issuer**: `fastapi`, `uvicorn`, `pycryptodome`
* **verifier**: `fastapi`, `uvicorn`, `pycryptodome`, `redis`
* **auditor**: `fastapi`, `uvicorn`, `redis`
* **client**: `requests`, `pycryptodome`
* **pir_server**: `fastapi`, `uvicorn` (`numpy` 仅限本地最小联调辅助)