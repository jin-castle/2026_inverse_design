# AutoSim Error DB 컨텍스트
> 환경 정보, 기존 코드 현황, 결정 사항

## 기존 코드 현황

### autosim/ 디렉토리
- `patterns/` — 200+ MEEP 패턴 스크립트 (실제 MEEP import 포함)
- `runner.py` — 패턴 실행기 (subprocess 기반, 60초 타임아웃)
- `run_summary.json` — 실행 결과 (ok/timeout/error 상태)
- `common.py` — 공통 유틸리티

### autosim/runner.py 분석
```python
# 현재 구조
run_pattern(pattern_file, timeout=60) → {status, elapsed_s, outputs, error}
# status: "ok" | "timeout" | "error" | "import_error"
```
→ 이미 에러 캡처는 됨. **저장 로직이 없는 게 문제**

### api/diagnose_engine.py 현황
- 2단계: DB 검색 (keyword + vector) → LLM 폴백
- 검색 대상: `knowledge.db` patterns 테이블 (코드 패턴들)
- **문제**: sim_errors 테이블 없음, 에러-해결쌍 검색 없음

### db/knowledge.db 테이블 구조 (기존)
```
patterns    — autosim 패턴 (코드 + 설명)
examples    — MEEP 예제 코드 (실행 결과 포함)
issues      — GitHub issues (에러 + 해결)
feedback    — 사용자 피드백
```

### autosim/run_summary.json 현황
- 총 ~150개 패턴 실행 결과 존재
- status="error" 항목들: 에러 메시지 캡처됨 → **아직 DB에 저장 안됨**
- 이 데이터가 즉시 사용 가능한 첫 번째 소스!

---

## 실행 환경

| 환경 | 용도 | 제약 |
|------|------|------|
| Windows (현재) | 파이썬 실행, DB 조작 | MEEP 없음 |
| Docker (meep-pilot-worker) | MEEP 시뮬레이션 | port 3000 |
| SimServer (166.104.35.108) | MPI 128코어 시뮬레이션 | SSH 필요 |

**Phase 1 전략**: Windows에서 `run_summary.json`의 error 항목 즉시 수집
→ MEEP import 없이도 syntax/logic 오류 충분히 수집 가능

---

## 파일 경로

```
C:\Users\user\projects\meep-kb\
├── autosim/
│   ├── runner.py              ← 기존 실행기 (재활용)
│   ├── run_summary.json       ← 기존 실행 결과 (즉시 수집 가능)
│   └── patterns/             ← 200+ 패턴 스크립트
├── api/
│   ├── diagnose_engine.py    ← 개선 대상
│   └── main.py               ← API 라우터 (엔드포인트 추가)
├── db/
│   ├── knowledge.db          ← 새 테이블 추가
│   └── chroma/               ← 새 컬렉션 추가
└── [신규]
    ├── tools/
    │   ├── error_db_setup.py      ← sim_errors 테이블 생성
    │   ├── ingest_run_summary.py  ← run_summary.json → DB
    │   ├── llm_fixer.py           ← Claude API 자동 수정
    │   └── auto_runner.py         ← 자동 실행 + 축적 루프
    └── autosim-error-db-plan.md   ← (이미 작성)
```

---

## 기술 스택

- **DB**: SQLite (knowledge.db) + ChromaDB (벡터 검색)
- **임베딩**: BGE-M3 (기존 embeddings/embed_bgem3.py)
- **LLM**: Anthropic Claude API (환경변수 ANTHROPIC_API_KEY)
- **API**: FastAPI (api/main.py)
- **실행**: subprocess (Windows) / docker exec (Linux)

---

## 주요 결정사항

1. **즉시 활용**: `run_summary.json`의 error 항목들을 첫 번째 데이터 소스로 사용
2. **새 테이블**: `sim_errors` (기존 테이블 건드리지 않음)
3. **새 ChromaDB 컬렉션**: `sim_errors_v1` (기존 컬렉션 분리 유지)
4. **DiagnoseEngine 수정**: 기존 로직 유지 + sim_errors 검색 추가
5. **Docker 리빌드 불필요**: API 엔드포인트는 볼륨 마운트로 적용
6. **LLM Fixer**: 수동 검증 가능한 형태로 먼저 생성, 나중에 자동화

---

## 환경변수 (.env)
```
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
APP_DIR=/app                   ← Docker 내부 경로
```

## API 현재 주소
- 로컬: http://localhost:8000
- ngrok: https://rubi-unmirrored-corruptibly.ngrok-free.dev
