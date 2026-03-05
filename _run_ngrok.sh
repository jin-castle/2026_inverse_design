#!/bin/bash
pkill -f "ngrok http 8765" 2>/dev/null || true
sleep 2

nohup ngrok http 8765 --log stdout \
  </dev/null >>/root/meep-kb-ngrok.log 2>&1 &
NGROK_PID=$!
disown $NGROK_PID
echo $NGROK_PID > /root/meep-kb-ngrok.pid
echo "NGROK_PID=$NGROK_PID"

# URL 추출 대기
sleep 6
URL=$(grep -o 'url=https://[^ ]*' /root/meep-kb-ngrok.log 2>/dev/null | tail -1 | sed 's/url=//')
echo "NGROK_URL=$URL"
