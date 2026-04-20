# eBPF/XDP Integration Scope & Boundary Definition

## 1. 架构定位 (Architectural Role)
在本 PIR 防滥用网关架构中，eBPF/XDP 被定位为 **前置的 L3/L4 及极轻量级 L7 早期启发式清洗中心**。
它的核心任务是阻断“明显非法的垃圾流量”，保护上层 Python Verifier。
* **挂载点优先级**：第一版优先尝试在网卡驱动层挂载 **XDP** 进行极速丢包；若受限于环境或 HTTP Payload 偏移量提取困难，则降级评估 TC (Traffic Control) 挂载点。

---

## 2. eBPF 职责边界：我们做什么 (In-Scope)
eBPF 程序仅执行时间复杂度为 $O(1)$ 或严格受控的有限窗口操作：

* **基础特征初筛 (Basic Fingerprinting)**：
    * 第一版仅对目标端口（如 8002）的 TCP 流量执行本原型定义的前置启发式过滤。
    * 非目标端口流量不属于本原型 eBPF 层的治理对象，默认不处理/放行。
* **浅层模式检查 (Shallow Pattern Check)**：
    * 在数据包的有限长度窗口内，进行极轻量的启发式字符串扫描（例如粗略寻找 `POST` 或局部核心 Key 的特征片段）。
    * **重要声明**：仅作为“明显非法流量”的早期启发式过滤，**不保证**完成完整的 HTTP 或 JSON 解析。对于跨包、分片、编码差异等复杂情况，一律默认放行给用户态处理。
* **预置黑名单阻断 (Static Denylist Fast-Drop)**：
    * 针对预置的已知恶意 IP (Denylist) 进行基于 eBPF Map 的快速丢包 (`XDP_DROP`)。
    * 第一版不将 eBPF 扩展成完整的速率限制器 (Rate Limiter) 或行为评分系统。

---

## 3. 严格禁止项：我们不做什么 (Out-of-Scope)
为了保证内核安全及避免陷入底层协议解析泥潭，以下逻辑 **严格禁止** 在 eBPF 中实现：

* **🚫 拒绝深度协议理解 (No Deep Protocol Parsing)**
    * 不做 TCP 流重组，不强求对 HTTP 报文和 JSON 树的深度解析与边界校验。
* **🚫 拒绝密码学与状态校验 (No Crypto & State Validation)**
    * 不做 RSA 盲签名验签与 HMAC 绑定校验。
    * 不连接 Redis，不进行票据防重放检查或原子核销。
* **🚫 拒绝动态复杂限流 (No Dynamic Rate Limiting)**
    * 不在内核态维护复杂的时间滑动窗口或滥用惩罚计分板。

---

## 4. 核心工程原则：Fail-Open / Fail-Safe
这是本层防御的最高指导原则：
**如果 eBPF 程序无法在常数或严格受控的时间内安全完成判断（例如遇到罕见的 TCP 分片、加密流量偏移、畸形包头），则必须默认放行 (`XDP_PASS`) 到用户态 Verifier，绝对不允许在内核侧编写复杂的补救或循环逻辑！**

---

## 5. 验收标准 (Acceptance Criteria)
当引入 eBPF 层后，系统的验收标准定义如下：
1. **垃圾流量早丢弃**：对命中 eBPF 浅层规则（如黑名单 IP，或单个数据包内明显不符 HTTP 基础特征的纯垃圾字节）的请求，应在内核早期被丢弃或阻断。
2. **用户态卸载**：上述被内核拦截的请求，不应进入用户态 Verifier 的完整业务处理路径（免除了框架路由、JSON 反序列化及后续复杂的计算成本）。
3. **合法流量无损 / 业务非法留给用户态**：
    * 格式正确、跨包情况复杂的合法请求，仍将顺利穿过 eBPF，由 Verifier 层接管最终的安全拦截或放行。
    * 格式正确但签名伪造、binding 错误、或命中 replay 状态的请求，也应继续穿过 eBPF，并在用户态 Verifier 中被拦截和记录。