# TODO — Vector DB (ChromaDB) 추가

**날짜:** 2026-02-22

- [x] 계획 제시 + Jin 컨펌
- [x] Step 1: ChromaDB + ONNX 임베딩 설치 (sentence-transformers 충돌 → ChromaDB 내장 EF로 전환)
- [x] Step 2: 임베딩 생성 + ChromaDB 적재 (3,193건, 143초)
- [x] Step 3: semantic_search.py CLI
- [x] Step 4: search.py --semantic 옵션 통합
- [x] Step 5: Skill 업데이트
- [x] 최종: 검색 동작 확인 ✅

## v2 개선본 (리뷰 기반)
- [x] 리뷰 서브에이전트 실행 → review_20260222.md 생성
- [x] semantic_search_v2.py: 한국어 쿼리 확장 (augment_query) + ⚠️경고 + 중복 제거
- [x] build_graph_v2.py: 역방향 엣지 + gradient 노드 + 한국어 alias + knowledge_graph_v2.pkl
- [x] graph_search_v2.py: 양방향 트래버설 + 한국어 alias 검색
- [x] search.py --semantic → v2로 업데이트
- [x] v1 vs v2 성능 검증: 한국어 유사도 +14~+26% 개선
