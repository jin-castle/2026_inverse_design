# GitHub Issues 전처리 강화 - Plan

## Executive Summary
sim_errors 테이블의 github_issue(242) + github_structured(151) = 393건에서
실행 가능한 MEEP 코드를 추출하고 runnable_issues.json으로 저장.
이전 분석: 코드 포함 60건이었으나 독립 실행 가능 0건 (의존성 문제).
강화된 전처리로 runnable + patchable 코드 추출 목표.

## 현재 상태 분석 (2026-03-25)

### DB 현황
- sim_errors: 393건 (github_issue: 242, github_structured: 151)
- original_code 컬럼: 모두 NULL (0건)
- context 컬럼에 코드 블록:
  - ```python 포함: 17건
  - ``` 포함(any): 124건
- root_cause 컬럼: ``` 포함 56건
- fix_applied 컬럼: ``` 포함 27건
- sim_errors_v2: 114건 (기존 데이터)

### 코드 소재
코드는 `context`, `root_cause`, `fix_applied` 컬럼에 마크다운 코드 블록으로 저장됨.
`original_code` 컬럼은 비어있음 → 코드 블록 파싱이 핵심.

## 목표 상태
- runnable_issues.json 생성: runnable ≥ 1건, patchable ≥ 5건
- sim_errors_v2에 research_notes 8개 패턴 삽입
- 전체 테스트 6개 통과

## Phase별 구현 계획

### Phase 1: SHOWCASE 문서 작성
- [x] Plan 작성
- [ ] Context 작성
- [ ] Tasks 작성

### Phase 2: github_preprocessor.py 구현
1. DB에서 393건 로드 (context + root_cause + fix_applied 전체 필드 활용)
2. 코드 블록 추출 (```python, ```, 4-space indent)
3. 의존성 분석 + COMMON_FIXES 적용
4. runability_score() 계산
5. runnable / patchable / not_runnable 분류
6. runnable_issues.json 출력

### Phase 3: ingest_research_notes.py 구현
1. meep-errors.md에서 8개 패턴 추출
2. sim_errors_v2 테이블에 INSERT
3. physics_cause, fix_worked=1 보장

### Phase 4: test_github_preprocess.py 작성
- 6개 테스트 케이스 검증

### Phase 5: git commit

## 리스크
- context 필드가 한국어 + 영어 혼합 → 코드 블록만 추출하면 무관
- 코드가 불완전한 snippet일 가능성 높음 → patchable로 분류
- runnable score 70 이상 달성이 어려울 수 있음 → 임계값 조정 가능

## 성공 기준
- [ ] runnable_issues.json 생성됨
- [ ] runnable 1건 이상 OR patchable 5건 이상
- [ ] sim_errors_v2에 8건 research_notes 삽입
- [ ] test 6개 모두 PASS
- [ ] git commit 완료
