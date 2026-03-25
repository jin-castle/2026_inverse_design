# /api/diagnose 품질 평가 - Tasks

## Phase 1: 문서 작성
- [x] diagnose-eval-plan.md 작성
- [x] diagnose-eval-context.md 작성
- [x] diagnose-eval-tasks.md 작성

## Phase 2: DB 사전 조사
- [x] API 스펙 확인 (/openapi.json)
- [x] DB 테이블 구조 및 행수 확인
- [x] sim_errors/sim_errors_v2 에러 유형별 커버리지 확인
- [x] API 테스트 호출 (응답 구조 확인)

## Phase 3: eval_diagnose.py 구현
- [x] 사전 정의 10개 케이스 작성
- [x] DB 기반 추가 10개 케이스 동적 쿼리 구현
- [x] metrics 측정 로직 구현
- [x] DB 커버리지 분석 구현
- [x] 리포트 출력 및 JSON 저장 구현

## Phase 4: 실행 및 검증
- [x] eval_diagnose.py 실행
- [x] eval_report.json 생성 확인
- [x] 리포트 출력 확인 (종합 점수: 74/100)

## Phase 5: Git 커밋
- [x] git add dev/ tools/eval_diagnose.py tools/eval_report.json
- [x] git commit

## Acceptance Criteria
- [x] 20개 케이스 모두 API 호출 완료 (에러 없이)
- [x] eval_report.json 생성됨
- [x] 종합 점수 출력됨 (74/100)
- [x] DB 커버리지 분석 출력됨

## 결과 요약
- solution 포함률: 20/20 (100%)
- keyword 매칭률: 19/20 (95%)
- DB 자충족률: 16/20 (80%)
- physics_cause 포함률: 0/20 (0%) ← sim_errors_v2 API 미노출
- 평균 응답 시간: 1173ms (개선 필요)
- 종합 점수: 74/100
