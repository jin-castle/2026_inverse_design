# fix-batch-tasks.md — 작업 체크리스트

## Phase 1: 즉시 실행 가능 8건 처리
- [ ] tools/run_fix_batch_safe.py 작성
- [ ] python -X utf8 tools/run_fix_batch_safe.py 실행
- [ ] fix_worked=1 증가 확인

## Phase 2: 마크다운 정제 (code_cleaner.py)
- [ ] tools/code_cleaner.py 작성
  - [ ] # [MD] 블록 제거 로직
  - [ ] ```python ... ``` 블록 추출 로직
  - [ ] In [N]: 패턴 제거 로직
  - [ ] import meep 포함 확인
  - [ ] DB update 함수 (original_code_raw 컬럼 추가)
- [ ] ALTER TABLE sim_errors_v2 ADD COLUMN original_code_raw TEXT

## Phase 3: 정제 후 verified_fix_v2 재실행
- [ ] code_cleaner.py 정제 성공 IDs 추출
- [ ] verified_fix_v2 배치 실행
- [ ] fix_worked=1 25건 이상 달성 (최소 15건)

## Phase 4: 검증 테스트
- [ ] tools/test_fix_batch.py 작성
  - [ ] TEST 1: run_fix_batch_safe 실행 후 fix_worked=1 증가 확인
  - [ ] TEST 2: code_cleaner 샘플 정제 테스트
  - [ ] TEST 3: DB 업데이트 확인 (original_code_raw 보존)
  - [ ] TEST 4: 정제 후 verified_fix_v2 실행 fix_worked=1 추가
  - [ ] TEST 5: 최종 fix_worked=1 ≥ 15건
- [ ] python -X utf8 tools/test_fix_batch.py ALL PASSED

## Phase 5: Git 커밋
- [ ] git add dev/ tools/run_fix_batch_safe.py tools/code_cleaner.py tools/test_fix_batch.py
- [ ] git commit -m "feat: verified_fix_v2 배치 + code_cleaner - fix_worked=1 대량 확보"

## 수용 기준 (Acceptance Criteria)
- tools/run_fix_batch_safe.py: 8건 배치 실행 완료
- tools/code_cleaner.py: # [MD] 혼재 코드 정제 성공 ≥ 10건
- tools/test_fix_batch.py: ALL PASSED
- fix_worked=1 최종 건수 ≥ 15건
