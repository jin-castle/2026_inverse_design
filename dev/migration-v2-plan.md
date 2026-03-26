# migration-v2-plan.md — sim_errors 구 데이터 v2 마이그레이션

## Executive Summary
기존 sim_errors 테이블에서 검증된 데이터(error_injector 50건 + marl_auto 3건)를
sim_errors_v2 5계층 구조로 변환. Docker 실행 없이 DB + LLM API만 사용.

## 현재 상태
- sim_errors: error_injector 50건, marl_auto 3건 (fix_worked=1, 검증 완료)
- sim_errors_v2: 114건 총 (fix_worked=1: 15건)
- SCORE_BY_SOURCE['error_injector'] = 0.88 (상향 예정: 0.93)

## 목표 상태
- sim_errors_v2에 53건 추가 (총 167건)
- fix_worked=1: 68건 (기존 15 + 신규 53)
- physics_cause 10건 이상 LLM 채우기
- SCORE_BY_SOURCE['error_injector'] = 0.93

## 구현 계획

### Phase 1: 문서 작성 (plan/context/tasks)
- dev/migration-v2-plan.md ✓
- dev/migration-v2-context.md
- dev/migration-v2-tasks.md

### Phase 2: migrate_to_v2.py 구현
위치: tools/migrate_to_v2.py

핵심 함수:
- infer_run_mode(code) → adjoint/forward/normalization/eigenmode_solve/harminv
- infer_dim(code) → 2 or 3
- infer_device_type(code) → waveguide/beamsplitter/grating/ring_resonator/general
- infer_error_class(error_type, msg) → code_error/physics_error/numerical_error/config_error
- infer_symptom(msg, error_type) → T>100%/NaN/T=0/diverged/wrong_mode
- infer_fix_type(error_type, fix_desc) → code_only/physics_understanding/parameter_tune/structural
- extract_physics_context(code) → {resolution, pml_thickness, fcen, ...}
- extract_cell_size(code) → JSON string
- extract_trigger_code(code, msg) → 관련 코드 스니펫
- make_diff(original, fixed) → unified diff string

중복 방지: code_hash (SHA-256) UNIQUE → skip if exists

### Phase 3: physics_cause LLM 채우기
physics_enricher.enrich_pending() 호출 (source='error_injector' 조건 추가)
모델: haiku → 품질 미달 시 sonnet 재시도

### Phase 4: SCORE_BY_SOURCE 업데이트
api/diagnose_engine.py의 SCORE_BY_SOURCE['error_injector'] = 0.93

### Phase 5: 검증 (test_migrate_v2.py)
- TEST 1: v2에 53건 삽입 확인
- TEST 2: fix_worked=1 건수 = 68건
- TEST 3: 핵심 필드 누락 없음
- TEST 4: code_hash 중복 없음
- TEST 5: physics_cause 10건 이상 채워짐

### Phase 6: git commit

## 리스크
- code_hash 중복: 이미 v2에 있는 error_injector 데이터 → skip
- original_code 없음: code_hash = SHA256("") → 중복 없으면 그대로 진행
- API rate limit: haiku 사용, 53건 순차 처리

## 성공 기준
1. sim_errors_v2 총 167건 (또는 기존 114 + 53 - 중복)
2. fix_worked=1: 68건 이상
3. physics_cause: 신규 레코드 10건 이상 채워짐
4. test_migrate_v2.py 5개 테스트 모두 통과
