# batch-expand-context.md

## 환경

### 핵심 파일 경로
- **meep-kb 루트**: `C:\Users\user\projects\meep-kb\`
- **DB**: `C:\Users\user\projects\meep-kb\db\knowledge.db`
- **배치 도구**: `tools/batch_live_runner.py`
- **실행 도구**: `tools/live_runner.py`
- **에러 수집**: `tools/error_collector.py`
- **감사 보고서**: `tools/audit_report.json` (runnable 189건 목록)
- **테스트 스크립트**: `tools/test_batch_expand.py`

### 컨테이너
- **이름**: `meep-pilot-worker`
- **MEEP 버전**: 1.31.0
- **상태**: 실행 중

### DB 테이블
- `live_runs`: 실행 결과 저장 (code_hash UNIQUE)
- `sim_errors_v2`: 에러 상세 정보
- `examples`: 원본 예제 코드 616건

## 결정사항
1. Phase 1 timeout=60s → 대부분 예제 커버
2. Phase 2 timeout=90s → 나머지 처리
3. 중복 skip: code_hash UNIQUE 제약 활용

## 제약조건
- MPI 명령 포함 예제는 mpi_deadlock_risk로 분류
- adjoint 최적화 예제는 timeout 발생 예상
- Windows PowerShell에서 실행 (`;` 구분자 사용)

## SESSION PROGRESS

### 2026-03-25 Session 1
**시작**: 31건 완료 상태에서 시작
- live_runs: 31건 (success: 23, error: 7, mpi_deadlock_risk: 1)
- sim_errors_v2: 12건

**Phase 1 실행**: `python -X utf8 tools/batch_live_runner.py --source examples --limit 100 --timeout 60`
- 시작: 13:00 KST
- 결과: TBD

**Phase 2 실행**: `python -X utf8 tools/batch_live_runner.py --source examples --limit 89 --timeout 90`
- 결과: TBD

**최종 결과**: TBD
