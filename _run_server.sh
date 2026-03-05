#!/bin/bash
cd /mnt/c/Users/user/projects/meep-kb
export APP_DIR=/mnt/c/Users/user/projects/meep-kb
export ANTHROPIC_API_KEY=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

nohup python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8765 \
  </dev/null >>/root/meep-kb.log 2>&1 &
SERVER_PID=$!
disown $SERVER_PID
echo $SERVER_PID > /root/meep-kb.pid
echo "SERVER_PID=$SERVER_PID"
