# batch-expand-tasks.md

## Phase 0: 준비
- [x] 현재 상태 확인 (live_runs: 31건, sim_errors_v2: 12건)
- [x] Plan 작성 (batch-expand-plan.md)
- [x] Context 작성 (batch-expand-context.md)
- [x] Tasks 작성 (batch-expand-tasks.md)

## Phase 1: test_batch_expand.py 생성
- [x] `tools/test_batch_expand.py` 작성 (5개 테스트)

## Phase 2: 1차 배치 실행 (timeout 60초)
- [x] `python -X utf8 tools/batch_live_runner.py --source examples --limit 100 --timeout 60` 실행
- [x] 중간 통계 확인: 100건 처리 (27 success, 26 error, 12 timeout, 5 mpi_deadlock_risk, 30 skip)
- [x] 에러 유형 분포 확인

## Phase 3: 2차 배치 실행 (timeout 90초)
- [ ] `python -X utf8 tools/batch_live_runner.py --source examples --limit 89 --timeout 90` 실행
- [ ] 중간 통계 확인 (실행 완료 후)

## Phase 4: 검증
- [ ] `python -X utf8 tools/test_batch_expand.py` ALL PASSED 확인
- [ ] 최종 리포트 출력

## Phase 5: 완료
- [ ] Context SESSION PROGRESS 업데이트
- [ ] git commit

## Acceptance Criteria
- live_runs >= 150건
- success 비율 >= 50%
- sim_errors_v2 >= 10건
- test_batch_expand.py ALL PASSED
