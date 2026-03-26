# Concept API Plan

## Executive Summary
meep-kb에 `/api/concept` 엔드포인트를 추가하여 "PML이 뭐야?" 같은 MEEP 개념 질문에
물리 설명 + 데모 코드 + (미리 생성된) 실행 결과를 반환하는 개념 사전 기능 구현.

## 현재 상태
- `/api/search`, `/api/diagnose`, `/api/chat` 엔드포인트 존재
- concepts 테이블 없음
- 개념 설명 기능 없음

## 목표 상태
- `concepts` 테이블 + FTS 인덱스 생성
- 15개 핵심 MEEP 개념 LLM 생성 후 DB 저장
- `/api/concept` POST 엔드포인트 구현
- `concept_detector.py` 개념 감지기 구현
- `/api/search` 응답에 concept 섹션 포함

## Phase별 계획

### Phase 1: DB 설계 + 생성
- `tools/setup_concepts.py` 작성
- SQLite concepts 테이블 + FTS5 가상 테이블 생성
- 기존 knowledge.db에 적용

### Phase 2: 15개 개념 LLM 생성
- `tools/generate_concepts.py` 작성
- claude-sonnet-4-6 API 호출 (ANTHROPIC_API_KEY)
- 파싱 → concepts 테이블 INSERT

### Phase 3: API 구현
- `api/concept_detector.py` 작성
- `api/main.py`에 `/api/concept` 엔드포인트 추가
- `/api/search` 응답에 concept 섹션 추가

### Phase 4: 검증
- `tools/test_concept_api.py` 작성
- ALL PASSED 확인

### Phase 5: Docker 배포
- docker cp + docker restart

### Phase 6: git commit

## 리스크
- LLM API 응답 파싱 실패 → 파싱 fallback 로직 필요
- Docker 컨테이너가 없으면 배포 스킵

## 성공 기준
- concepts 테이블에 15개 개념 모두 생성
- /api/concept 응답 200 OK
- test_concept_api.py ALL PASSED
