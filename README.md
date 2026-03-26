# MEEP-KB — MEEP FDTD Knowledge Base

> MEEP FDTD 시뮬레이션을 위한 하이브리드 RAG 지식베이스 + 웹 인터페이스

## 주요 기능

| 기능 | 설명 |
|------|------|
| **KB Search** | 하이브리드 RAG (Graph + Vector + Keyword) 기반 MEEP 관련 검색 |
| **Concept Q&A** | "PML이 뭐야" 등 개념 질문 → 요약 + 실행 이미지 + 데모 코드 + 흔한 실수 TOP5 |
| **Diagnose** | MEEP 에러 코드 진단 및 수정 제안 (MPI deadlock 사전 검토 포함) |
| **Dict** | 개념(56개) / Patterns / Notebooks / Examples / Errors 사전 페이지 |

## 데이터 현황

| 테이블 | 건수 | 설명 |
|--------|------|------|
| `concepts` | 56개 | MEEP 핵심 개념 (데모 코드 + 실행 이미지 포함) |
| `sim_errors_v2` | 175건 | 실제 실행 에러 + 물리 원인 분석 + verified fix |
| `examples` | 616건 | MEEP 예제 코드 |
| `errors` | 519건 | GitHub Issues 기반 에러 케이스 |
| `docs` | 2497건 | 공식 문서 |

## API 엔드포인트

```
POST /api/chat       - 대화형 검색 (히스토리 포함, 개념 감지 자동)
POST /api/search     - 단순 검색
POST /api/diagnose   - MEEP 에러 진단
POST /api/concept    - 특정 개념 상세 조회
POST /api/mpi-check  - MPI deadlock 위험 사전 분석
GET  /dict           - Dictionary 웹 UI
GET  /               - 메인 채팅 UI
```

## 실행 방법

```bash
# Docker Compose로 실행
docker-compose up -d

# 또는 직접
cd api && uvicorn main:app --host 0.0.0.0 --port 7860
```

기본 포트: `7860` (Docker), 외부 접근: ngrok 또는 리버스 프록시

## 디렉토리 구조

```
meep-kb/
├── api/                    # FastAPI 백엔드
│   ├── main.py             # 메인 앱 (라우팅, 검색, 진단)
│   ├── concept_detector.py # 개념 감지기 (56개 MEEP 개념)
│   ├── diagnose_engine.py  # 에러 진단 엔진
│   ├── dict_page.py        # /dict 페이지 HTML 생성
│   ├── sim_router.py       # 검색 라우팅
│   └── sim_tracker.py      # 시뮬레이션 트래커
├── web/                    # 프론트엔드 (vanilla JS)
│   ├── index.html
│   ├── app.js
│   └── style.css
├── tools/                  # 데이터 수집/관리 스크립트
│   ├── kb_pipeline.py          # KB 자동화 파이프라인 (run→enrich→fix)
│   ├── run_concept_demos.py    # concepts 데모 코드 실행 + 이미지 수집
│   ├── generate_concepts_v2.py # LLM으로 개념 생성
│   ├── verified_fix_v2.py      # 에러→LLM수정→Docker검증 파이프라인
│   ├── physics_enricher.py     # 물리 원인 분석 자동화
│   ├── batch_live_runner.py    # 코드 배치 실행
│   ├── improve_demos.py        # 데모 이미지 품질 개선
│   └── ...
├── db/                     # SQLite DB + 결과 이미지
│   └── results/            # concept_*.png 실행 결과 이미지
├── docker-compose.yml
└── Dockerfile
```

## 기술 스택

- **Backend**: FastAPI + SQLite (ChromaDB RAG)
- **Frontend**: Vanilla JS + highlight.js
- **LLM**: Claude Sonnet (개념 생성, 에러 수정, 물리 분석)
- **Embedding**: BGE-M3 (1024차원)
- **Graph**: NetworkX (패턴 관계 그래프)
- **Execution**: Docker (meep-pilot-worker, MEEP 1.31.0)

## 주요 도구 사용법

```bash
# 개념 데모 이미지 재생성
python -u -X utf8 tools/run_concept_demos.py --all

# KB 파이프라인 (새 에러 데이터 → enrich → fix)
python -u -X utf8 tools/kb_pipeline.py --steps run,enrich,fix --limit 20

# 특정 개념 재생성
python -u -X utf8 tools/generate_concepts_v2.py --concept FluxRegion

# 이미지 품질 개선 (DFT 2-panel, snippet 재생성 등)
python -u -X utf8 tools/improve_demos.py --group A  # DFT 추가
python -u -X utf8 tools/improve_demos.py --group B  # snippet 재생성
python -u -X utf8 tools/improve_demos.py --group C  # 2-panel 확장
```
