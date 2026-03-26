# migration-v2-tasks.md — 마이그레이션 태스크 체크리스트

## Phase 1: 문서 작성
- [x] migration-v2-plan.md 작성
- [x] migration-v2-context.md 작성
- [x] migration-v2-tasks.md 작성

## Phase 2: migrate_to_v2.py 구현
- [ ] tools/migrate_to_v2.py 작성
  - [ ] infer_run_mode() 구현
  - [ ] infer_dim() 구현
  - [ ] infer_device_type() 구현
  - [ ] infer_error_class() 구현
  - [ ] infer_symptom() 구현
  - [ ] infer_fix_type() 구현
  - [ ] extract_physics_context() 구현
  - [ ] extract_cell_size() 구현
  - [ ] extract_trigger_code() 구현
  - [ ] make_diff() 구현
  - [ ] 메인 마이그레이션 루프 구현 (53건 처리)
  - [ ] 중복 방지 (code_hash EXISTS 체크)

## Phase 3: 마이그레이션 실행
- [ ] python -X utf8 tools/migrate_to_v2.py 실행
- [ ] 53건 삽입 확인

## Phase 4: physics_cause LLM 채우기
- [ ] physics_enricher.enrich_pending() 호출
- [ ] 10건 이상 채워짐 확인

## Phase 5: SCORE_BY_SOURCE 업데이트
- [ ] api/diagnose_engine.py에서 error_injector 0.88 → 0.93 수정

## Phase 6: 검증 (test_migrate_v2.py)
- [ ] tools/test_migrate_v2.py 작성
- [ ] TEST 1: 53건 삽입 확인
- [ ] TEST 2: fix_worked=1 = 68건
- [ ] TEST 3: 핵심 필드 누락 없음
- [ ] TEST 4: code_hash 중복 없음
- [ ] TEST 5: physics_cause 10건 이상

## Phase 7: git commit
- [ ] git add dev/ tools/migrate_to_v2.py tools/test_migrate_v2.py
- [ ] git commit -m "feat: sim_errors 구 데이터 53건 v2 마이그레이션 (error_injector+marl_auto)"

## Acceptance Criteria
1. sim_errors_v2 fix_worked=1 ≥ 68건
2. code_hash 중복 없음
3. physics_cause 채워진 신규 레코드 ≥ 10건
4. test_migrate_v2.py 5개 테스트 모두 PASS
