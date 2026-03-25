# verified_fix_v2 - Tasks

## Phase 0: 문서화
- [x] Plan 작성 (verified-fix-v2-plan.md)
- [x] Context 작성 (verified-fix-v2-context.md)
- [x] Tasks 작성 (verified-fix-v2-tasks.md)

## Phase 1: verified_fix_v2.py 구현
- [x] 1.1 DB 조회: sim_errors_v2 WHERE fix_worked=0
- [x] 1.2 original_code 재실행 (에러 재현 확인)
- [x] 1.3 LLM 프롬프트 구성 (물리 컨텍스트 포함)
- [x] 1.4 LLM 응답 파싱 (FIX_TYPE / FIX_DESCRIPTION / FIXED_CODE)
- [x] 1.5 fixed_code Docker 재실행 검증
- [x] 1.6 성공 시 DB 업데이트 (fix_worked=1, fixed_code, code_diff, fix_description, fix_type)
- [x] 1.7 CLI 인터페이스 (--limit, --dry-run, --id)

## Phase 2: test_verified_fix_v2.py 구현
- [x] 2.1 TEST 1: sim_errors_v2 fix_worked=0 레코드 확인
- [x] 2.2 TEST 2: LLM 수정 코드 생성 (1건 테스트)
- [x] 2.3 TEST 3: Docker 재실행 검증
- [x] 2.4 TEST 4: fix_worked=1 업데이트 확인
- [x] 2.5 TEST 5: /api/diagnose 응답에 sim_error_v2 포함 확인

## Phase 3: 검증
- [x] 3.1 search_db()에 sim_errors_v2 조회 추가 (diagnose_engine.py에 이미 구현됨)
- [x] 3.2 실제 실행: python -X utf8 tools/verified_fix_v2.py --id 3 → fix_worked=1 성공
- [x] 3.3 전체 테스트: python -X utf8 tools/test_verified_fix_v2.py → ALL PASSED (5/5)

## Phase 4: Git 커밋
- [ ] 4.1 git add dev/ tools/verified_fix_v2.py tools/test_verified_fix_v2.py
- [ ] 4.2 git commit

## Acceptance Criteria
- [x] test_verified_fix_v2.py: 5/5 PASSED
- [x] sim_errors_v2에 fix_worked=1 레코드 ≥ 1건 (현재 3건)
- [x] /api/diagnose 응답에 sim_error_v2 출처 결과 포함 가능 (search_db에 구현됨)
