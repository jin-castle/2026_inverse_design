# /api/diagnose 품질 평가 - Plan

## Executive Summary
meep-kb DB에 쌓인 데이터가 /api/diagnose 엔드포인트를 통해 실제로 유용한 진단을 
제공하는지 체계적으로 측정한다. 20개 eval case로 정확도, 커버리지, 응답 시간을 측정.

## 현재 상태
- API: http://localhost:8765/api/diagnose (POST, `{code, error, n}`)
- DB: knowledge.db (15.9MB)
  - errors: 596 rows (GitHub issues 기반)
  - sim_errors: 519 rows (error_injector 기반, fix_worked 포함)
  - sim_errors_v2: 114 rows (physics_cause, root_cause_chain 포함)
  - live_runs: 190 rows
- DB 강점: EigenMode(28), Divergence(59), MPIError(51), Adjoint(16), PML(19)
- DB 약점: sim_errors_v2에서 Timeout(40/0), Unknown(29/1) fix_worked=0

## 목표 상태
- tools/eval_diagnose.py: 20개 케이스 자동 실행
- tools/eval_report.json: 결과 저장
- 리포트: solution 포함률, keyword 매칭률, DB 자충족률, 에러 유형별 커버리지 출력

## 평가 케이스 설계 (20개)
- 사전 정의 10개: EigenMode, Divergence, MPIError×2, PML×2, Adjoint, ImportError, NumericalError, General, MPI_deadlock
- DB 기반 추가 10개: sim_errors에서 error_type별로 대표 케이스 추출

## API 응답 구조
```json
{
  "error_info": {"detected_types": [...], "primary_type": "...", ...},
  "suggestions": [
    {
      "type": "sim_error|error|pattern|doc",
      "title": "...",
      "cause": "...",
      "solution": "...",
      "code": "...",
      "score": 0.88,
      "source": "...",
      "physics_cause": "...",  // sim_errors_v2
      "root_cause_chain": "..."  // sim_errors_v2
    }
  ]
}
```

## 측정 지표
1. top1_score: 첫 번째 suggestion의 score
2. has_solution: solution 필드 있음
3. solution_covers_keyword: expected_keywords 중 1개 이상 포함
4. db_sufficient: mode=db_only 또는 db_only_low_confidence
5. has_physics_cause: physics_cause 포함
6. has_root_cause_chain: root_cause_chain 포함
7. response_time_ms: 응답 시간

## 성공 기준
- solution 포함률 ≥ 80%
- keyword 매칭률 ≥ 60%
- 평균 응답 시간 ≤ 500ms
