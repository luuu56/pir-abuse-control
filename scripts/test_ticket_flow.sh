#!/bin/bash
# scripts/test_ticket_flow.sh
# 作用：一键启动 Issuer 并运行 Client 走通完整的获取票据流程

echo "=== Starting Issuer Service ==="
source services/issuer/.venv/bin/activate
python -m services.issuer.main &
ISSUER_PID=$!

sleep 3 # 等待 FastAPI 启动

echo "=== Running Client ==="
source services/client/.venv/bin/activate
python -m services.client.main

echo "=== Cleaning up ==="
kill $ISSUER_PID
echo "Day 9 Flow Test Complete."
