# meep-kb Hardening Context

## 핵심 파일 경로
- `C:\Users\user\projects\meep-kb\api\main.py` — FastAPI 앱 (ingest 엔드포인트)
- `C:\Users\user\projects\meep-kb\agent\coverage_checker.py` — LLM 사용 조건
- `C:\Users\user\projects\meep-kb\Dockerfile` — BGE-M3 prebuild
- `C:\Users\user\projects\meep-kb\docker-compose.yml` — 볼륨/포트
- `C:\Users\user\projects\meep-kb\.env` — ANTHROPIC_API_KEY, PORT

## 환경
- Docker compose: `meep-kb` 서비스, 8765:7860
- 볼륨: ./db, ./web, ./api
- 현재 graph pkl 위치: `db/knowledge_graph_v2.pkl` → ./db 볼륨 범위 내 ✅

## 결정사항
- Auth 방식: `X-Ingest-Key` 헤더 (Bearer 토큰 불필요, 내부 시스템)
- 환경변수명: `INGEST_API_KEY`
- coverage threshold: top_score ≥ 0.82 AND n ≥ 3 → db_only
- slowapi: `requirements.txt`에 추가
- BGE-M3 prebuild: Dockerfile에 RUN python -c "SentenceTransformer('BAAI/bge-m3')" 추가

## 주의사항
- startup()에 중복 except 블록 존재 (L97~L100 근처) → 제거
- INGEST_API_KEY 없으면 서버 시작 시 WARNING 출력 (강제 종료는 하지 않음, 로컬 개발 편의)
- rate limit은 X-Forwarded-For 헤더 기반 (ngrok 사용 시 실제 IP 파악 가능)
