# Concept API Tasks

## Phase 1: DB 설계 + 생성
- [ ] `tools/setup_concepts.py` 작성
- [ ] concepts 테이블 생성 확인
- [ ] concepts_fts 가상 테이블 생성 확인

## Phase 2: LLM 개념 생성
- [ ] `tools/generate_concepts.py` 작성
- [ ] ANTHROPIC_API_KEY 로드 확인
- [ ] PML 개념 생성 테스트
- [ ] 15개 전체 개념 생성
- [ ] DB 저장 확인

## Phase 3: API 구현
- [ ] `api/concept_detector.py` 작성
- [ ] `api/main.py`에 ConceptRequest 모델 추가
- [ ] `/api/concept` 엔드포인트 추가
- [ ] `/api/search` concept 섹션 추가

## Phase 4: 검증
- [ ] `tools/test_concept_api.py` 작성
- [ ] TEST 1: 테이블 생성 확인
- [ ] TEST 2: PML 개념 데이터 확인
- [ ] TEST 3-4: API 응답 확인 (Docker 필요)
- [ ] TEST 5: concept_detector 단위 테스트
- [ ] TEST 6: 15개 개념 count 확인
- [ ] TEST 7: /api/search concept 섹션 확인 (Docker 필요)

## Phase 5: Docker 배포
- [ ] docker cp api/main.py
- [ ] docker cp api/concept_detector.py
- [ ] docker restart
- [ ] 로그 확인

## Phase 6: git
- [ ] git add
- [ ] git commit

## Acceptance Criteria
- concepts 테이블에 15개 행 존재
- 각 행: summary 50자+, explanation에 $수식$ 포함, demo_code에 "import meep" 포함
- /api/concept POST → 200 OK, matched_concept 필드 존재
- detect_concept("pml 두께") == "PML"
