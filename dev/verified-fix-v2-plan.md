# verified_fix_v2 - Executive Plan

## Executive Summary
sim_errors_v2 테이블에 저장된 에러 레코드(fix_worked=0)를 LLM이 물리 컨텍스트 기반으로 수정하고,
Docker 컨테이너에서 재실행하여 검증한 뒤 fix_worked=1로 업데이트하는 파이프라인.
기존 verified_fix_builder.py와 달리, v2는 실제 DB 레코드를 처리하며 물리적 근본 원인을
LLM 프롬프트에 포함하여 더 정확한 수정을 생성한다.

## 현재 상태
- sim_errors_v2: 12건 레코드, 모두 fix_worked=0
- 에러 타입: AttributeError(2), physics_error(2), SyntaxError(1), Harminv(1), FileNotFoundError(1), TypeError(1), RuntimeError(1), AssertionError(2), MPIDeadlockRisk(1)
- tools/verified_fix_builder.py 존재 (참고용 패턴)
- tools/live_runner.py - run_code() 함수로 Docker 실행
- api/diagnose_engine.py - parse_error(), check_mpi_deadlock_risk()

## 목표 상태
- tools/verified_fix_v2.py: CLI 도구 (--limit, --dry-run, --id 옵션)
- tools/test_verified_fix_v2.py: 5개 테스트 ALL PASSED
- sim_errors_v2에 fix_worked=1 레코드 1건 이상
- /api/diagnose 응답에 sim_error_v2 타입 포함 가능

## Phase 계획

### Phase 0: 문서화 (Plan/Context/Tasks)
- Plan, Context, Tasks 작성

### Phase 1: verified_fix_v2.py 구현
1.1 DB에서 fix_worked=0 레코드 조회
1.2 original_code 재실행 (에러 재현)
1.3 LLM 프롬프트 구성 (물리 컨텍스트 포함)
1.4 LLM 응답 파싱 (FIX_TYPE, FIX_DESCRIPTION, FIXED_CODE)
1.5 fixed_code Docker 재실행 검증
1.6 성공 시 DB 업데이트 (fix_worked=1)
1.7 CLI 인터페이스 (--limit, --dry-run, --id)

### Phase 2: test_verified_fix_v2.py 구현
2.1 TEST 1: fix_worked=0 레코드 확인
2.2 TEST 2: LLM 코드 생성 (1건)
2.3 TEST 3: Docker 재실행 검증
2.4 TEST 4: fix_worked=1 업데이트 확인
2.5 TEST 5: /api/diagnose에 sim_error_v2 포함 확인

### Phase 3: 검증 및 검색 연동
3.1 search_db()에 sim_errors_v2 조회 추가 (diagnose_engine.py)
3.2 전체 테스트 실행: python -X utf8 tools/test_verified_fix_v2.py

### Phase 4: Git 커밋

## 리스크
- 일부 에러 타입(physics_error, MPIDeadlockRisk)은 코드 수정으로 해결 안 될 수 있음
  → 이 경우 fix_worked=0 유지, 스킵
- Docker 재실행 timeout (120초): 긴 시뮬레이션은 짧은 코드로 제한
- LLM이 전체 코드를 반환하지 않을 수 있음 → 파싱 실패 처리

## 성공 기준
- test_verified_fix_v2.py: ALL PASSED (5/5)
- sim_errors_v2에 fix_worked=1 레코드 ≥ 1건
- /api/diagnose 응답에 sim_error_v2 출처 결과 포함
