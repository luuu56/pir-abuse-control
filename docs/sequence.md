# 完整业务时序与状态流转

1. **[Issuance]** Client 获取 `sigma`，组装 `t = (SN, sigma, EpochID)`。
2. **[Binding]** Client 派生 `sk_t`，计算 `c_q` 与 `b = HMAC(sk_t, c_q || w)`。
3. **[Request]** Client 发送带有 `request_id` 的 `r = (q, t, b, w)` 到 Verifier。
4. **[Pre-Verify]** Verifier 验证 `sigma` 与一致性。失败则返回 `REJECTED`。
5. **[Atomic Lock]** Verifier 检查 Redis 状态并执行原子流转 (SETNX SN PENDING)。冲突则 `REJECTED`。
6. **[Forward]** Verifier 调用 PIR Server: `POST /api/v1/pir/query(q)`。
7. **[Execute]** PIR Server 执行密集计算，返回结果。
8. **[Finalize]** Verifier 更新 Redis 状态 (`CONSUMED` 或 `FAILED`)。
   * **工程原则**：状态更新必须以幂等方式执行；若执行结果已返回但状态持久化失败，应记录高优先级审计异常并禁止静默成功。
9. **[Audit]** Verifier 异步发送审计元数据至 Auditor。
10. **[Response]** Verifier 返回结果给 Client。
11. 
---
> **体系化文档参考**：  
> 关于 Verifier 侧 L4/L7 两级协同防御的详细职责划分与联动细节，请参考 [两级前置验证与防御架构（architecture_defense.md）](architecture_defense.md)。