# batch-expand-plan.md

## Executive Summary
examples 테이블 616건 중 독립 실행 가능한 189건 전체를 순차 실행하여
live_runs + sim_errors_v2에 최대한 많은 실행 데이터를 수집한다.

## 현재 상태 (2026-03-25)
- live_runs: 31건 (success: 23, error: 7, mpi_deadlock_risk: 1)
- sim_errors_v2: 12건
- 목표 대상: 189건 - 31건 = 158건 (code_hash 중복 자동 skip)

## 목표 상태
- live_runs: 189건 이상
- 성공률: 50% 이상 (94건+)
- sim_errors_v2: 10건 이상 (에러 패턴 학습용)

## 실행 전략

### Phase 1: 1차 배치 (timeout 60초, limit 100)
```bash
python -X utf8 tools/batch_live_runner.py --source examples --limit 100 --timeout 60
```
- 이미 실행된 31건은 code_hash UNIQUE 제약으로 자동 skip
- 대부분 예제는 30초 내 완료 → 60초면 충분
- adjoint 최적화 등 무거운 예제는 timeout으로 skip

### Phase 2: 2차 배치 (timeout 90초, limit 89)
```bash
python -X utf8 tools/batch_live_runner.py --source examples --limit 89 --timeout 90
```
- Phase 1에서 skip된 나머지 처리
- timeout 90초로 좀 더 여유

### 중복 방지
- batch_live_runner.py에서 code_hash UNIQUE 제약으로 자동 skip
- 이미 실행된 코드는 재실행 없이 skip_duplicate로 처리됨

## 에러 유형별 예상 분포
| 에러 유형 | 예상 비율 | 비고 |
|---------|---------|------|
| import_error | 30% | meep 미설치 환경에서 import 실패 |
| runtime_error | 25% | 실행 중 오류 (파라미터, 경계조건 등) |
| timeout | 20% | adjoint 최적화 등 장시간 실행 |
| syntax_error | 10% | 코드 문법 오류 |
| success | 15% | 정상 완료 |

## 성공 기준
- [ ] live_runs >= 150건
- [ ] success 비율 >= 50%
- [ ] sim_errors_v2 >= 10건
- [ ] test_batch_expand.py ALL PASSED

## 예상 소요 시간
- Phase 1: ~30분 (100건 × 평균 18초)
- Phase 2: ~20분 (89건 × 평균 13초, 이미 실행된 것 skip)
- 총: 약 40~50분
