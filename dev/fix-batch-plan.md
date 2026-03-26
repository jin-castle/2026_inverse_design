# fix-batch-plan.md — verified_fix_v2 배치 실행 계획

## Executive Summary
sim_errors_v2 테이블의 fix_worked=0 레코드(103건)에 대해 verified_fix_v2 파이프라인을 대규모 배치 실행하여 fix_worked=1 건수를 현재 11건에서 25건 이상으로 늘린다.

## 현재 상태
- sim_errors_v2 총 건수: 114건 (ID 1~114)
- fix_worked=1: 11건
- fix_worked=0: 103건
  - 즉시 실행 가능 (마크다운 없음): [4, 11, 38, 43, 52, 58, 65, 67] → 8건
  - # [MD] 혼재 코드: 31건 → code_cleaner 정제 필요
  - 기타 skip (Timeout/MPIDeadlockRisk/Unknown 등): 나머지

## 목표 상태
- fix_worked=1 총 건수: **25건 이상** (14건 추가 목표)
- 마크다운 혼재 코드 정제 스크립트 (code_cleaner.py) 완성
- 배치 테스트 (test_fix_batch.py) ALL PASSED

## Phase별 계획

### Phase 1: 즉시 실행 가능 8건 처리
- `tools/run_fix_batch_safe.py` 작성 및 실행
- 대상: [4, 11, 38, 43, 52, 58, 65, 67]
- 타임아웃: 각 180s, capture_output=False

### Phase 2: 마크다운 혼재 코드 정제
- `tools/code_cleaner.py` 작성
- # [MD] 주석 + 마크다운 텍스트에서 실행 가능한 MEEP 코드 추출
- DB 업데이트: original_code_raw 컬럼 추가, 원본 보존

### Phase 3: 정제된 코드로 verified_fix_v2 재실행
- code_cleaner 성공한 레코드 ID 추출
- verified_fix_v2 배치 실행
- 목표: 총 fix_worked=1 25건 이상

### Phase 4: 검증 테스트
- `tools/test_fix_batch.py` 작성
- ALL PASSED 확인

### Phase 5: Git 커밋

## 리스크
- verified_fix_v2 내부 Docker exec blocking → timeout=180s 필수
- LLM API rate limit → 배치 간 sleep(2) 추가
- # [MD] 패턴 코드: 마크다운 텍스트와 파이썬 코드가 혼재 → 정제 로직 필요

## 성공 기준
- tools/run_fix_batch_safe.py 정상 실행 완료
- tools/code_cleaner.py: 샘플 정제 테스트 통과
- tools/test_fix_batch.py: ALL PASSED
- fix_worked=1 총 건수 ≥ 15건 (이상적으로 25건)
