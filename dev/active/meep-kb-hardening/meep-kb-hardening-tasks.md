# meep-kb Hardening Tasks

## Phase 1 — 🔴 즉시

### 1. Ingest 엔드포인트 인증
- [x] `api/main.py`에 `verify_ingest_key` FastAPI Dependency 추가
- [x] `/api/ingest/example` — Depends(verify_ingest_key) 추가
- [x] `/api/ingest/error` — Depends(verify_ingest_key) 추가
- [x] `/api/ingest/sim_error` — Depends(verify_ingest_key) 추가
- [x] `/api/ingest/result` — Depends(verify_ingest_key) 추가
- [x] `.env.example`에 `INGEST_API_KEY=your-secret-key` 추가
- [x] `.env`에 랜덤 키(48자) 생성 완료
- [ ] 검증: 키 없이 POST → 401, 키 있으면 → 200 (Docker 기동 후)

### 2. coverage_checker 조건 추가
- [x] `agent/coverage_checker.py` 수정
  - top_score ≥ 0.82 AND len ≥ 3 → db_only ✅
  - doc_lookup이고 top_score ≥ 0.70 AND len ≥ 2 → db_only ✅
  - 나머지 → use_generation=True ✅
- [x] 로컬 python 검증 4케이스 통과

## Phase 2 — 🟡 권장

### 3. startup 버그 수정
- [x] `api/main.py` startup() 내 중복 except Exception 블록 제거
- [x] `python -m py_compile` 통과

### 4. BGE-M3 Dockerfile 사전 다운로드
- [x] `Dockerfile`에 BGE-M3 prebuild RUN 추가
- [ ] 검증: docker build 시 모델 다운로드 완료 로그 (빌드 후 확인)

### 5. graph pkl → 볼륨 확인 및 Dockerfile COPY 정리
- [x] `db/knowledge_graph_v2.pkl` → `./db` 볼륨 범위 내 확인
- [x] Dockerfile에서 `COPY db/knowledge_graph_v2.pkl` 라인 제거
- [ ] 검증: 컨테이너 재시작 후 그래프 정상 로드 (Docker 기동 후)

## Phase 3 — 🟢 권장

### 6. Rate Limiting
- [x] `requirements.txt`에 `slowapi>=0.1.9` 추가
- [x] `api/main.py`에 Limiter 설정
- [x] /api/search, /api/chat: 10/minute
- [x] /api/diagnose: 5/minute
- [ ] 검증: 11번 연속 요청 시 429 반환 (Docker 기동 후)

## Acceptance Criteria
- [ ] 키 없는 ingest → 401 Unauthorized
- [ ] 고신뢰도 검색(score≥0.82, 3건) → mode: "db_only", elapsed 빠름
- [ ] startup 로그에 중복 에러 메시지 없음
- [ ] docker build 완료 후 BGE-M3 런타임 다운로드 없음
- [ ] 10req 초과 → 429 Too Many Requests
