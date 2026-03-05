#!/bin/bash
# MEEP-KB 서버 + ngrok 터널 시작 스크립트
# 사용법: bash /mnt/c/Users/user/projects/meep-kb/start.sh

set -e

PROJ=/mnt/c/Users/user/projects/meep-kb
LOG_SERVER=/root/meep-kb.log
LOG_NGROK=/root/meep-kb-ngrok.log
PID_SERVER=/root/meep-kb.pid
PID_NGROK=/root/meep-kb-ngrok.pid

# ── 기존 프로세스 정리 ────────────────────────────────────────────────
echo "[start.sh] 기존 프로세스 정리..."
fuser -k 8765/tcp 2>/dev/null || true
pkill -f "ngrok http 8765" 2>/dev/null || true
sleep 2

# ── FastAPI 서버 시작 (세션 완전 분리) ───────────────────────────────
echo "[start.sh] FastAPI 서버 시작 중..."
cd "$PROJ"
setsid env \
  APP_DIR="$PROJ" \
  ANTHROPIC_API_KEY="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" \
  python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8765 \
  >> "$LOG_SERVER" 2>&1 &
echo $! > "$PID_SERVER"
echo "[start.sh] FastAPI PID: $(cat $PID_SERVER)"

# ── 서버 준비 대기 ────────────────────────────────────────────────────
echo "[start.sh] 서버 준비 대기 중 (최대 30초)..."
for i in $(seq 1 30); do
  sleep 1
  if curl -sf http://localhost:8765/api/status > /dev/null 2>&1; then
    echo "[start.sh] ✅ FastAPI 서버 준비 완료 (${i}초)"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "[start.sh] ❌ 서버 시작 실패. 로그 확인: $LOG_SERVER"
    exit 1
  fi
done

# ── ngrok 터널 시작 ───────────────────────────────────────────────────
echo "[start.sh] ngrok 터널 시작 중..."
setsid ngrok http 8765 --log stdout \
  >> "$LOG_NGROK" 2>&1 &
echo $! > "$PID_NGROK"
echo "[start.sh] ngrok PID: $(cat $PID_NGROK)"

# ngrok URL 추출 대기
sleep 5
NGROK_URL=$(grep -o 'url=https://[^ ]*' "$LOG_NGROK" 2>/dev/null | tail -1 | sed 's/url=//')

echo ""
echo "============================================="
echo "  MEEP-KB 서버 실행 중!"
echo "  FastAPI : http://localhost:8765"
echo "  외부 URL: ${NGROK_URL:-'(ngrok 로그 확인 필요)'}"
echo "============================================="
echo ""
echo "상태 확인: curl http://localhost:8765/api/status"
echo "로그 확인: tail -f $LOG_SERVER"
echo "ngrok URL: grep 'url=' $LOG_NGROK"
