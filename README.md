---
title: MEEP-KB
emoji: 🔬
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# MEEP-KB · 광학 시뮬레이션 지식베이스

MEEP / MPB / legume 관련 에러 디버깅, 코드 예제, 개념 검색을 위한 하이브리드 RAG 시스템.

## 기능

- **Hybrid RAG**: SQLite DB + ChromaDB 벡터 검색 + 지식 그래프
- **한국어/영어** 동시 지원
- **LLM 생성**: DB 커버리지 부족 시 Claude로 보완
- **대화형 인터페이스**: 멀티턴 채팅 지원

## 스택

- FastAPI + uvicorn
- sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`)
- ChromaDB (벡터 DB)
- NetworkX (지식 그래프)
- Anthropic Claude (생성 모델)

## 환경변수

| 변수 | 설명 |
|------|------|
| `ANTHROPIC_API_KEY` | Claude API 키 (필수) |
