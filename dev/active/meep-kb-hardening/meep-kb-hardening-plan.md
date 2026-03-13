# meep-kb Hardening Plan

**날짜**: 2026-03-13
**상태**: In Progress

## Executive Summary
배포 전 보안/비용/안정성 취약점 4개를 우선 수정.
Ingest 인증 → coverage 조건 → BGE-M3 prebuild → graph 마운트 → startup 버그 → rate limit 순서.

## Phase 1 — 🔴 즉시 (보안/비용)
1. **Ingest 엔드포인트 인증** (`api/main.py`)
   - FastAPI Dependency로 `X-Ingest-Key` 헤더 검증
   - 환경변수 `INGEST_API_KEY` (없으면 서버 시작 거부)
   - 적용 대상: `/api/ingest/example`, `/api/ingest/error`, `/api/ingest/sim_error`, `/api/ingest/result`

2. **coverage_checker 조건 추가** (`agent/coverage_checker.py`)
   - top_score ≥ 0.82 AND results ≥ 3 → db_only (LLM 생략)
   - top_score ≥ 0.70 AND results ≥ 2 AND intent=doc_lookup → db_only
   - 나머지 → use_generation=True (기존 동작 유지)
   - 예상 LLM 호출 감소: ~60%

## Phase 2 — 🟡 권장 (안정성)
3. **startup duplicate except 버그 수정** (`api/main.py`)
   - search_executor 주입 try/except 중복 블록 제거

4. **BGE-M3 Dockerfile 사전 다운로드** (`Dockerfile`)
   - 빌드 시 캐시 → 런타임 다운로드 제거

5. **knowledge_graph_v2.pkl 볼륨 마운트** (`docker-compose.yml`)
   - `./db:/app/db` 이미 있음 → pkl도 db/ 하위로 이동 확인
   - 현재 위치: `db/knowledge_graph_v2.pkl` → 이미 볼륨 범위 내
   - Dockerfile COPY 제거 (볼륨으로 충분)

## Phase 3 — 🟢 권장 (트래픽)
6. **Rate Limiting** (`api/main.py`)
   - `slowapi` 라이브러리 사용
   - /api/search, /api/chat: 10req/min per IP
   - /api/diagnose: 5req/min per IP

## 성공 기준
- [ ] ingest 엔드포인트가 키 없으면 401 반환
- [ ] score 높은 쿼리는 LLM 호출 없이 DB 결과만 반환
- [ ] startup 로그에 중복 에러 없음
- [ ] Docker 빌드 시 BGE-M3 다운로드 완료
- [ ] rate limit 초과 시 429 반환
