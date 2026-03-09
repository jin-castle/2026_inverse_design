# MARL → Error DB 구현 태스크

## Phase 1: Solution Structurer (오늘, ~$1)

- [ ] **1-1** `tools/solution_structurer.py` 작성
  - errors 테이블에서 solution 있는 항목 읽기
  - Claude Haiku로 구조화 (원인/해결/코드)
  - sim_errors에 저장 (fix_worked=1)
  - 배치 처리 (--limit, --dry-run 옵션)

- [ ] **1-2** `/api/ingest/sim_error` 엔드포인트 추가 (main.py)
  - MARL 및 외부에서 직접 sim_errors에 POST 가능하도록

- [ ] **1-3** Solution Structurer 실행
  - 먼저 10개 dry-run으로 품질 확인
  - 전체 실행: 459개 중 solution 있는 것

- [ ] **1-4** 결과 검증 (sim_errors 300개+ 달성 확인)

---

## Phase 2: MARL → sim_errors 파이프라인 (오늘)

- [ ] **2-1** `marl_orchestrator.py` Stage 6 수정
  - 자동 수정 성공 시 → `/api/ingest/sim_error` POST
  - 포함 필드: error_type, error_message, original_code, fixed_code, fix_description
  - fix_worked=1 (검증됨)

- [ ] **2-2** `_store_sim_error_to_kb()` 함수 추가
  - 기존 `_store_error_to_kb()`와 별개
  - sim_errors 특화 필드 포함

- [ ] **2-3** MARL 테스트 실행
  - 의도적 에러 있는 간단한 스크립트로 테스트
  - sim_errors에 저장되는지 확인

---

## Phase 3: ErrorInjector (내일, Docker 필요)

- [ ] **3-1** `tools/error_injector.py` 작성
  - autosim/patterns/에서 패턴 로드
  - 버그 카탈로그 정의 (8종)
  - 각 패턴에 버그 삽입 → 새 스크립트 생성

- [ ] **3-2** Docker 실행 + traceback 캡처
  - 버그 삽입 코드 Docker에서 실행
  - stderr 캡처 → error_message 추출

- [ ] **3-3** LLM 자동 수정 + 검증
  - 원본 코드(버그 없는 것)가 정답
  - 에러 → 원본 비교로 fix_description 생성
  - fix_worked=1 저장

---

## Phase 4: diagnose_engine 벡터 검색 강화

- [ ] **4-1** `tools/embed_sim_errors.py` 작성
  - sim_errors 전체 → BGE-M3 임베딩
  - ChromaDB `sim_errors_v1` 컬렉션에 추가

- [ ] **4-2** `diagnose_engine.py` 벡터 검색 추가
  - `search_vector()`에 sim_errors_v1 컬렉션 포함
  - semantic similarity로 유사 에러 검색

---

## 완료 기준
- [ ] sim_errors verified 레코드 500개 이상
- [ ] MARL 실행 → 자동으로 sim_errors 저장 확인
- [ ] diagnose 웹에서 "DB 기반 답변" 비율 70%+ 달성
- [ ] 한국어 구조화된 해결책이 진단 결과에 표시

---

## 지금 시작: Phase 1-1 → 1-2 → 1-3
