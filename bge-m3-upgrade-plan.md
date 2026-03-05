# BGE-M3 임베딩 업그레이드 계획서

## 개요

meep-kb의 벡터 검색 품질을 높이기 위해 현재 경량 임베딩 모델을 고성능 모델로 교체한다.

---

## 1. 현재 상태 (AS-IS)

| 항목 | 현재 값 |
|------|---------|
| 모델 | `paraphrase-multilingual-MiniLM-L12-v2` |
| 임베딩 차원 | **384** |
| 모델 크기 | ~120MB |
| ChromaDB | errors(594), examples(601), patterns(116), docs(2000) |
| 문제점 | 경량 모델이라 기술 문서 검색 정밀도 낮음 |

---

## 2. BGE-M3란?

**BAAI/bge-m3** (Beijing Academy of AI, 2024)

### 핵심 특징

| 특징 | 설명 |
|------|------|
| **Multi-lingual** | 100개 이상 언어 동시 지원 (한국어/영어/중국어 등) |
| **Multi-granularity** | 단어 하나 ~ 8192 토큰 긴 문서까지 모두 처리 |
| **Multi-functionality** | Dense + Sparse(BM25-like) + ColBERT 방식 3가지 동시 지원 |
| 임베딩 차원 | **1024** (현재 384 → 2.67배) |
| 모델 크기 | ~570MB |
| 특화 | 기술/과학 문서 검색에서 특히 강함 |

### 왜 meep-kb에 적합한가?

```
현재 검색 문제:
- "adjoint gradient가 NaN이 나와요" → 관련 패턴 못 찾음
- "3D SOI mode converter efficiency" → 유사 문서 누락

BGE-M3 이후:
- 의미 기반 검색 정밀도 향상 (MTEB 벤치마크 SOTA)
- 기술 용어 + 자연어 쿼리 혼합도 잘 처리
- 영어로 번역된 patterns DB와 시너지 극대화 ← 방금 한 작업과 연결!
```

### 3가지 검색 모드 (선택 가능)

```python
# Dense: 의미 유사도 (기본, 현재와 동일 방식)
model.encode("adjoint optimization MEEP")

# Sparse: 키워드 기반 (BM25 대체)
model.encode(..., return_sparse=True)

# ColBERT: 토큰 수준 정밀 매칭 (가장 정확, 가장 느림)
model.encode(..., return_colbert_vecs=True)
```

---

## 3. 업그레이드 계획 (TO-DO)

### Phase 1: 환경 준비 (30분)
- [ ] Docker 컨테이너 내 `FlagEmbedding` 패키지 설치
  ```bash
  pip install FlagEmbedding
  ```
- [ ] BGE-M3 모델 다운로드 (~570MB, HuggingFace)
- [ ] GPU/CPU 사용 가능 여부 확인 (CPU fallback 준비)

### Phase 2: 임베딩 재구축 (1~2시간)
- [ ] ChromaDB 기존 컬렉션 백업
- [ ] 새 임베딩 함수 작성 (`embeddings/embed_bgem3.py`)
  ```python
  from FlagEmbedding import BGEM3FlagModel
  model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)
  ```
- [ ] 4개 컬렉션 전체 재임베딩
  - docs (2000개) → 약 10~20분
  - examples (601개) → 약 3~5분
  - errors (594개) → 약 3~5분
  - patterns (116개) → 약 1분
- [ ] ChromaDB dim 불일치 방지: 기존 컬렉션 삭제 후 재생성 (384→1024 변경)

### Phase 3: 코드 교체 (30분)
- [ ] `query/` 디렉토리의 검색 코드에서 임베딩 함수 교체
- [ ] API 엔드포인트 테스트
- [ ] hybrid RAG (ChromaDB + SQLite FTS) 동작 확인

### Phase 4: 검증 (30분)
- [ ] 검색 품질 비교 테스트 5개 쿼리
  - `"adjoint gradient NaN"`
  - `"3D SOI slab TE mode source setup"`
  - `"binarization not converging"`
  - `"MPI parallel MEEP run"`
  - `"PhC bandgap waveguide"`
- [ ] 응답 속도 측정 (CPU 기준 허용치: <2초/쿼리)

---

## 4. 리스크 및 대응

| 리스크 | 대응 |
|--------|------|
| 모델 용량 (570MB) | Docker 볼륨 공간 확인 먼저 |
| CPU 속도 느림 | `use_fp16=True`, batch_size 조정 |
| ChromaDB dim 충돌 | 기존 컬렉션 완전 삭제 후 재생성 |
| API 코드 호환성 | 기존 `embed_multilingual.py` 유지 (롤백용) |

---

## 5. 예상 효과

| 항목 | Before | After |
|------|--------|-------|
| 임베딩 품질 (MTEB) | ~50점대 | ~65점대 |
| 검색 정밀도 | 보통 | 높음 |
| 기술 문서 처리 | 약함 | 강함 |
| 쿼리 길이 제한 | ~512 토큰 | 8192 토큰 |

---

## 6. 파일 구조

```
meep-kb/
├── embeddings/
│   ├── embed_multilingual.py     # 기존 (백업용 유지)
│   └── embed_bgem3.py            # 신규 작성
├── query/
│   └── search.py                 # 임베딩 함수 교체
└── db/
    └── chroma/                   # 재임베딩 후 갱신
```

---

*작성: 포비 | 2026-03-03*
