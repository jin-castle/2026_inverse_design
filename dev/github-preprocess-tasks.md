# GitHub Issues 전처리 강화 - Tasks

## Phase 1: SHOWCASE 문서 ✅
- [x] github-preprocess-plan.md 작성
- [x] github-preprocess-context.md 작성
- [x] github-preprocess-tasks.md 작성 (이 파일)

## Phase 2: github_preprocessor.py 구현
- [ ] DB 연결 및 393건 로드 (context + root_cause + fix_applied)
- [ ] extract_code_blocks() 구현
  - [ ] ```python ... ``` 추출
  - [ ] ``` ... ``` (meep/mp 포함된 것) 추출
  - [ ] 4-space indent 블록 추출
- [ ] apply_common_fixes() 구현 (COMMON_FIXES 패치)
- [ ] patch_code() 구현 (import meep 추가, plt.show 제거 등)
- [ ] runability_score() 구현 (5개 플래그, score 합산)
- [ ] classify() 구현 (runnable/patchable/not_runnable)
- [ ] runnable_issues.json 출력

## Phase 3: ingest_research_notes.py 구현
- [ ] meep-errors.md 8개 패턴 정의 (KNOWN_ERRORS 리스트)
- [ ] sim_errors_v2에 INSERT (중복 방지: source='research_notes')
- [ ] physics_cause, fix_worked=1 포함 확인

## Phase 4: test_github_preprocess.py 작성
- [ ] TEST 1: github_preprocessor.py 실행 → runnable_issues.json 생성
- [ ] TEST 2: runnable 1건 이상 OR patchable 5건 이상 확인
- [ ] TEST 3: patchable 코드에 common_import 치환 적용 확인
- [ ] TEST 4: runability_score() 정확도 (import meep 없는 코드 → score<70)
- [ ] TEST 5: ingest_research_notes.py → sim_errors_v2에 8건 삽입 확인
- [ ] TEST 6: 삽입된 8건 모두 fix_worked=1, physics_cause 있음 확인

## Phase 5: 검증 실행
- [ ] python tools/github_preprocessor.py 실행
- [ ] python tools/ingest_research_notes.py 실행
- [ ] python tools/test_github_preprocess.py 실행
- [ ] 모든 테스트 PASS 확인

## Phase 6: Git Commit
- [ ] git add dev/ tools/github_preprocessor.py tools/ingest_research_notes.py tools/test_github_preprocess.py tools/runnable_issues.json
- [ ] git commit -m "feat: GitHub Issues 전처리 강화 + research_notes KB 반영"

## Acceptance Criteria
- runnable_issues.json 생성됨 (유효한 JSON)
- has_code > 0, patchable > 0 (최소한)
- sim_errors_v2에 source='research_notes' 8건 존재
- 8건 모두 fix_worked=1, physics_cause IS NOT NULL
- 테스트 6개 모두 PASS
