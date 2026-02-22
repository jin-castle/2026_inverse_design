#!/bin/bash
# MEEP-KB 서버 시작 스크립트

set -e
cd /mnt/c/Users/user/projects/meep-kb

export ANTHROPIC_API_KEY="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"

echo "📦 패키지 설치 확인 중..."
pip3 install fastapi uvicorn[standard] -q

echo ""
echo "🚀 MEEP-KB 서버 시작"
echo "   포트: 8765"
echo "   URL:  http://localhost:8765"
echo "   UI:   http://localhost:8765/"
echo "   API:  http://localhost:8765/docs"
echo ""

uvicorn api.main:app \
  --host 0.0.0.0 \
  --port 8765 \
  --reload \
  --reload-dir api \
  --log-level info
