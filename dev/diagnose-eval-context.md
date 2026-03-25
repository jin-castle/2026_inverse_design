# /api/diagnose 품질 평가 - Context

## 환경
- API base URL: http://localhost:8765
- DB path: C:/Users/user/projects/meep-kb/db/knowledge.db
- Python: C:/Python313/python.exe
- 작업 디렉토리: C:/Users/user/projects/meep-kb

## API 스펙 (확인 완료)
- Endpoint: POST /api/diagnose
- Request body: `{"code": str, "error": str, "n": int=5}`
- Response: `{"error_info": {...}, "suggestions": [...]}`

## DB 테이블 현황
| 테이블 | 행수 | 주요 컬럼 |
|--------|------|----------|
| errors | 596 | error_msg, cause, solution, source_type |
| sim_errors | 519 | error_type, fix_worked, root_cause, fix_description |
| sim_errors_v2 | 114 | physics_cause, root_cause_chain, error_type, fix_worked |
| live_runs | 190 | error_type, T_value, R_value |
| examples | 616 | title, code, description |
| docs | 2497 | section, content |

## sim_errors DB 커버리지 (사전 조사)
### 풍부한 에러 유형 (sim_errors, fix_worked=1 많음)
- General: 160/160 fixed
- Divergence: 59/59 fixed
- MPIError: 51/51 fixed
- EigenMode: 28/28 fixed
- Adjoint: 16/16 fixed
- PML: 17/19 fixed

### 약한 에러 유형 (sim_errors_v2 기준)
- Timeout: 40 total, 0 fixed
- Unknown: 29 total, 1 fixed
- NumericalError: 16 total, 6 fixed (sim_errors도 16/0)

## eval_diagnose.py 위치
- C:/Users/user/projects/meep-kb/tools/eval_diagnose.py

## 결과물 위치
- C:/Users/user/projects/meep-kb/tools/eval_report.json

## 주의사항
- API가 실행 중이어야 함 (localhost:8765)
- PowerShell에서 python으로 실행
- DB 추가 10개 케이스는 스크립트에서 동적으로 쿼리

## 결정사항
- mode 필드가 API 응답에 없는 경우: suggestions[0].source로 판단
  - "sim_errors:..." → db_only
  - "github" or "errors" → db_only (FTS 매칭)
  - 없으면 db_only_low_confidence
