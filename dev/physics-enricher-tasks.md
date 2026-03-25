# Physics Enricher - Tasks

## Phase 1: 계획 및 문서화
- [x] DB 현황 파악 (12개 레코드, 모두 비어있음)
- [x] physics-enricher-plan.md 작성
- [x] physics-enricher-context.md 작성
- [x] physics-enricher-tasks.md 작성 (이 파일)

## Phase 2: 구현
- [x] tools/physics_enricher.py 작성
  - [x] CLI argparse (--limit, --dry-run, --model)
  - [x] DB 쿼리: physics_cause 비어있는 레코드 조회
  - [x] PHYSICS_HINTS 딕셔너리
  - [x] LLM 프롬프트 빌더
  - [x] Anthropic API 호출 (claude-haiku-4-5 기본)
  - [x] 응답 파싱 (PHYSICS_CAUSE:, CODE_CAUSE:, ROOT_CAUSE_CHAIN:)
  - [x] DB UPDATE
  - [x] dry-run 모드 (DB 업데이트 없이 출력만)

## Phase 3: 검증
- [x] tools/test_physics_enricher.py 작성
  - [x] TEST 1: --dry-run 출력 확인
  - [x] TEST 2: 1건 실제 enrichment → physics_cause ≥ 50자
  - [x] TEST 3: code_cause ≥ 20자
  - [x] TEST 4: root_cause_chain JSON 파싱 가능
  - [x] TEST 5: UPDATE 후 DB 반영 확인
  - [x] TEST 6: --limit 5 → 5건 모두 채워짐
- [x] python -X utf8 tools/test_physics_enricher.py ALL PASSED (7/7)

## Phase 4: 전체 실행 및 완료
- [x] 전체 32개 레코드 enrichment 실행 (모두 채워짐)
- [x] 샘플 출력 확인
- [x] context.md SESSION PROGRESS 업데이트
- [x] git commit

## Acceptance Criteria

- ALL PASSED (test_physics_enricher.py)
- 12개 레코드 모두 physics_cause, code_cause 채워짐
- root_cause_chain JSON 파싱 가능
- git commit 완료
