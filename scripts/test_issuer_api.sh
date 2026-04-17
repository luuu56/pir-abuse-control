#!/bin/bash
# scripts/test_issuer_api.sh
# 作用：启动 Issuer 并通过 curl 测试盲签接口是否正常响应

echo "=== Starting Issuer Service ==="
source services/issuer/.venv/bin/activate
python -m services.issuer.main &
ISSUER_PID=$!

# 等待服务启动
sleep 3

echo "=== Testing /issue endpoint with curl ==="
curl -X POST "http://127.0.0.1:8001/api/v1/issuer/issue" \
     -H "Content-Type: application/json" \
     -d '{"blinded_message": "0x1a2b3c", "admission_proof": "dummy_proof"}'
echo -e "\n"

echo "=== Cleaning up ==="
kill $ISSUER_PID
echo "Done."
