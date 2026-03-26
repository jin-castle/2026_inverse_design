# Concept API Context

## 핵심 파일 경로
- 루트: `C:\Users\user\projects\meep-kb\`
- DB: `C:\Users\user\projects\meep-kb\db\knowledge.db`
- API: `C:\Users\user\projects\meep-kb\api\main.py`
- 새 파일:
  - `tools/setup_concepts.py` - DB 테이블 생성
  - `tools/generate_concepts.py` - LLM 개념 생성
  - `tools/test_concept_api.py` - 검증 테스트
  - `api/concept_detector.py` - 개념 감지기

## 환경
- Python: 3.x (Windows, C:\Users\user\projects\meep-kb\)
- ANTHROPIC_API_KEY: .env에서 로드 (sk-ant-api03-...)
- API 포트: 8765 (Docker 컨테이너)
- DB 경로: 로컬은 `C:\Users\user\projects\meep-kb\db\knowledge.db`

## 기존 DB 스키마 확인 필요
- errors 테이블 존재
- examples 테이블 존재
- docs 테이블 존재
- concepts 테이블 없음 → 생성 필요

## LLM 설정
- 모델: claude-sonnet-4-6
- API: anthropic Python SDK
- 개념당 1 API 호출 (15회)

## Docker 배포
- 컨테이너: meep-kb-meep-kb-1
- 볼륨 마운트: db/knowledge.db가 공유됨
- main.py는 docker cp로 배포

## 결정사항
- concepts 테이블은 로컬 DB에 직접 생성 (볼륨 공유)
- FTS5 가상 테이블로 전문 검색 지원
- result_status 기본값: "pending" (Docker 실행 전)
- 개념 감지는 키워드 매칭 우선, FTS 보조

## SESSION PROGRESS
- 2026-03-25: 초기 구현 시작
