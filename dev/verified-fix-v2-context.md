# verified_fix_v2 - Context

## 핵심 파일 경로
- **구현 대상**: `C:\Users\user\projects\meep-kb\tools\verified_fix_v2.py`
- **테스트**: `C:\Users\user\projects\meep-kb\tools\test_verified_fix_v2.py`
- **DB**: `C:\Users\user\projects\meep-kb\db\knowledge.db`
- **참고 코드**:
  - `tools/verified_fix_builder.py` — LLM fix + Docker 재실행 패턴
  - `tools/live_runner.py` — run_code(code, timeout) → RunResult
  - `tools/error_collector.py` — collect_v2() 함수
  - `api/diagnose_engine.py` — check_mpi_deadlock_risk(), parse_error()
  - `api/main.py` — /api/diagnose 엔드포인트

## 환경
- MEEP 실행 컨테이너: `meep-pilot-worker` (meep 1.31.0, 실행 중)
- API: `http://localhost:8765`
- ANTHROPIC_API_KEY: `.env` 파일에서 로드
- Python: `python -X utf8` 필수 (Windows UTF-8 환경)

## DB 스키마 (sim_errors_v2)
```sql
id, run_mode, run_stage, iteration, mpi_np, device_type,
wavelength_um, resolution, pml_thickness, cell_size, dim,
uses_adjoint, uses_symmetry,
error_class, error_type, error_message, traceback_full, symptom,
trigger_code, trigger_line, physics_cause, code_cause, root_cause_chain,
fix_type, fix_description, original_code, fixed_code, code_diff,
fix_worked, source, meep_version, run_time_sec, code_length, code_hash, created_at
```

## 현재 데이터 상태 (2026-03-25)
- 총 12건, 모두 fix_worked=0
- 에러 유형: AttributeError, physics_error, SyntaxError, Harminv, FileNotFoundError, TypeError, RuntimeError, AssertionError, MPIDeadlockRisk

## LLM 설정
- 모델: claude-sonnet-4-6 (claude-3-5-sonnet-20241022)
- max_tokens: 2000
- API key: dotenv에서 로드

## 결정사항
1. **에러 재현 확인**: original_code를 먼저 실행해서 에러가 재현되는지 확인
   - 재현 실패 시: skip (이미 수정된 코드거나 환경 문제)
2. **physics_error 처리**: error_class='physics_error'인 경우도 LLM에게 물리적 해석 요청
3. **fix_worked 업데이트 조건**:
   - Docker 재실행 결과 status='success' → fix_worked=1
   - status='error' 또는 timeout → fix_worked=0 유지
4. **search_db 연동**: diagnose_engine.py의 search_db()에서 sim_errors_v2도 조회하도록 추가

## 주의사항
- `docker cp` + `docker exec` 패턴 사용 (live_runner.py 참고)
- code_diff는 unified diff 형식 (difflib 사용)
- root_cause_chain은 JSON 문자열 → dict 파싱해서 LLM 프롬프트에 readable하게

## SESSION PROGRESS
- [2026-03-25] 초기 설정 완료
  - Plan/Context/Tasks 작성
  - DB 상태 확인: 12건 fix_worked=0
  - verified_fix_v2.py 구현 완료
  - test_verified_fix_v2.py 구현 완료
  - diagnose_engine.py search_db()에 sim_errors_v2 연동 추가
  - ALL TESTS PASSED
  - Git 커밋 완료
