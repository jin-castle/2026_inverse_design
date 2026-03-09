# AutoSim Error DB 구현 태스크
> 체크리스트 형태 — 완료시 [x] 체크

## Phase 1: 즉시 수집 (DB 기반 없이도 오늘 가능)

### Step 1: DB 스키마 확장
- [x] `tools/error_db_setup.py` 작성
  - knowledge.db에 `sim_errors` 테이블 생성
  - 컬럼: id, error_type, error_msg, error_context, original_code, fixed_code, fix_description, fix_keywords, pattern_name, verified, source, created_at
  - ChromaDB `sim_errors_v1` 컬렉션 초기화
- [ ] 스크립트 실행해서 테이블 생성 확인

### Step 2: run_summary.json 즉시 수집
- [x] `tools/ingest_errors_to_sim.py` 작성 및 실행 (255개 수집)

### Step 3: DiagnoseEngine 개선 (DB 검색 강화)
- [x] `api/diagnose_engine.py` 수정
  - 컬럼명 버그 수정 (title→error_msg, url→source_url)
  - FTS 검색 추가
  - sim_errors 검색 추가
- [x] 로컬 테스트 완료 (0건→5건)
- [x] Docker 컨테이너 반영 완료

### Step 4: API 엔드포인트 추가
- [x] `api/main.py`에 `/api/diagnose` POST 엔드포인트 추가 (완전 동작 확인)
  - body: {error_type, error_msg, error_context, original_code, fixed_code, fix_description, pattern_name, verified}
  - sim_errors 테이블 + ChromaDB에 저장
  - 반환: {id, message}
- [ ] `/api/stats/errors` GET 엔드포인트 추가
  - 에러 타입별 수집 현황 반환
  - verified True/False 구분

---

## Phase 2: LLM 자동 수정 (SimServer 또는 Docker 필요)

### Step 5: LLM Fixer
- [ ] `tools/llm_fixer.py` 작성
  - sim_errors에서 verified=False 항목 읽기
  - Claude API: 원본코드 + 에러 → 수정코드 + 설명 생성
  - 프롬프트 템플릿:
    ```
    MEEP 코드에서 오류가 발생했습니다.
    [원본 코드]
    [에러 메시지]
    1. 오류 원인 분석
    2. 수정된 코드 (```python 블록)
    3. 수정 설명 (한국어, 2-3문장)
    4. 검색 키워드 (JSON 배열, 5개)
    ```
  - 생성된 fix를 sim_errors 테이블 업데이트
- [ ] 배치 실행: verified=False 항목 50개씩 처리

### Step 6: Verifier (선택적)
- [ ] `tools/verifier.py` 작성
  - fixed_code를 subprocess로 실행 (syntax check)
  - 성공 시 verified=True 업데이트
  - 실제 MEEP 실행은 SimServer 연동 후 (Phase 3)
- [ ] LLM Fixer + Verifier 파이프라인 연동

### Step 7: Auto Runner (새 패턴 추가)
- [ ] `tools/auto_runner.py` 작성
  - autosim/patterns/ 스캔 → 아직 run_summary에 없는 패턴 발견
  - subprocess로 실행 → 에러 캡처
  - 자동으로 ingest_run_summary 흐름 타기
  - cron 스케줄 지원 (--schedule 옵션)

---

## Phase 3: 품질 향상 + 웹 UI

### Step 8: ChromaDB 임베딩 추가
- [ ] `tools/embed_sim_errors.py` 작성
  - sim_errors 테이블 → BGE-M3 임베딩 → ChromaDB `sim_errors_v1`
  - diagnose_engine에서 벡터 검색도 sim_errors_v1 포함

### Step 9: 진단 UI 개선
- [ ] `web/diagnose.js` 업데이트
  - "오류-해결쌍 기반 제안" 카드 UI
  - verified 배지 표시 ("검증됨" / "참고용")
  - 피드백 버튼: "이 해결책이 도움됐나요?"
- [ ] `web/index.html` 진단 탭 UI 개선

### Step 10: 커버리지 대시보드 (선택)
- [ ] `/api/stats/coverage` 엔드포인트
  - 에러 타입별: {type, count, verified_count}
  - 커버리지 % (전체 중 solved 비율)
- [ ] 웹에 간단한 stats 표시

---

## 완료 기준
- [ ] sim_errors 테이블에 100+ 레코드 (run_summary 수집만으로도 가능)
- [ ] diagnose_engine이 에러 타입 매칭 시 DB 결과 반환
- [ ] 웹 UI에서 오류-해결쌍 결과 표시 확인
- [ ] Phase 2: 50+ verified 레코드

---

## 지금 바로 시작: Step 1 → Step 2 → Step 3 순서
