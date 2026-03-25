# kb_pipeline.py — 태스크 체크리스트

## Phase 1: 기존 파일 리팩터링

- [x] **1-1.** `physics_enricher.py`에 `enrich_pending(limit, model)` 함수 추가
  - 기존 `get_records()`, `enrich_record()`, `update_record()` 재사용
  - 반환: `{total, success, failed}`
  - 기존 `main()` 유지 (CLI 깨지지 않음)

- [x] **1-2.** `verified_fix_v2.py`에 `fix_pending(limit, skip_markdown)` 함수 추가
  - 기존 `run_pipeline()` 래퍼
  - `skip_markdown=True`이면 마크다운 코드 skip 후 통계 반환
  - 반환: `{total, fixed, failed, skipped}`

## Phase 2: kb_pipeline.py 구현

- [x] **2-1.** 파일 골격 작성 (imports, argparse, main)
- [x] **2-2.** `clean_code(code)` 함수 구현
  - ` ```python ... ``` ` 블록 추출
  - `In [N]:` / `Out[N]:` 제거
  - `## 헤더` 제거
  - 연속 빈줄 정리
  - `import meep` 포함 여부 확인
- [x] **2-3.** `is_markdown_mixed(code)` 헬퍼 구현
- [x] **2-4.** Step 1 실행 로직 (batch_live_runner.run_batch 호출)
- [x] **2-5.** Step 2 실행 로직 (physics_enricher.enrich_pending 호출)
- [x] **2-6.** Step 3 실행 로직 (verified_fix_v2.fix_pending 호출)
- [x] **2-7.** 드라이런 모드 구현
- [x] **2-8.** 리포트 출력 형식 구현
- [x] **2-9.** DB 현황 쿼리 및 출력

## Phase 3: 테스트 스크립트

- [x] **3-1.** `tools/test_kb_pipeline.py` 작성
  - TEST 1: `--dry-run` → 에러 없음
  - TEST 2: `--steps enrich --dry-run` → 대상 목록 출력
  - TEST 3: `--steps fix --fix-limit 3` → fix_worked=1 증가 확인
  - TEST 4: `--steps run,enrich --source examples --limit 3` → 실행
  - TEST 5: DB 현황 출력 정상

## Phase 4: 검증 및 완료

- [x] **4-1.** `python -X utf8 tools/test_kb_pipeline.py` → ALL PASSED (23/23)
- [ ] **4-2.** git add + commit

## Acceptance Criteria

- 모든 테스트 PASSED
- `--dry-run` 에러 없음
- `--steps` 선택적 실행 동작
- 리포트 형식 명세 준수
- 기존 CLI (physics_enricher, verified_fix_v2) 깨지지 않음
