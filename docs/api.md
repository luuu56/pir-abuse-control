# API 规范 v1 (RESTful Style)

## 1. Issuer Service (`/api/v1/issuer`)
* **POST `/challenge`**: 客户端申请准入挑战。
* **POST `/issue`**: 客户端提交准入证明与盲化消息。Issuer 验证通过后进行盲签。

## 2. Verifier Service (`/api/v1/verifier`)
* **POST `/execute`**: 核心入口。验签 -> 验绑定 -> 原子流转 -> 转发请求 -> 核销返回。

## 3. PIR Server (Internal API, `/api/v1/pir`)
* **POST `/query`**: 纯执行接口。

## 4. Auditor Service (`/api/v1/auditor`)
* **GET `/tickets/{sn}`**
  * **职责**: 获取票据状态与相关审计记录（当前状态及可用历史摘要）。
* **POST `/verify-commitment`**: 验证 `(c_q, b, w)` 的一致性。
* **POST `/report`**: Verifier 异步提交审计分录。