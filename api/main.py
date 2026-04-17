#!/usr/bin/env python3
"""
MEEP-KB FastAPI 백엔드 (Hybrid RAG)

포트: 8765
"""

import sys, os, time, sqlite3, pickle, json
from pathlib import Path
from typing import Optional, List, Any

from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# ── 경로 설정 ─────────────────────────────────────────────────────────────────
BASE = Path(os.environ.get("APP_DIR", "/app"))
sys.path.insert(0, str(BASE / "agent"))
sys.path.insert(0, str(BASE / "query"))

DB_PATH    = BASE / "db/knowledge.db"
CHROMA_DIR = BASE / "db/chroma"
GRAPH_PATH = BASE / "db/knowledge_graph_v3.pkl"

# ── Ingest 인증 키 ────────────────────────────────────────────────────────────
_INGEST_API_KEY = os.environ.get("INGEST_API_KEY", "")
if not _INGEST_API_KEY:
    print("[WARNING] INGEST_API_KEY 환경변수가 설정되지 않았습니다. /api/ingest/* 엔드포인트가 무인증 상태입니다.")

def verify_ingest_key(x_ingest_key: str = Header(default="")):
    """Ingest 엔드포인트 전용 API 키 검증 Dependency"""
    if not _INGEST_API_KEY:
        return  # 키 미설정 시 경고만 (로컬 개발 편의)
    if x_ingest_key != _INGEST_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Ingest-Key header")

# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── FastAPI 앱 ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="MEEP-KB Hybrid RAG API",
    description="MEEP 지식베이스 검색 API (DB 직출력 + LLM 생성 하이브리드)",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 전역 캐시 (startup에서 로드) ──────────────────────────────────────────────
_cache: dict = {
    "model":  None,
    "chroma": None,
    "graph":  None,
    "ready":  False,
}


@app.on_event("startup")
async def startup():
    """서버 시작 시 모델/DB/그래프 사전 로드"""
    # ── fastembed 시맨틱 인덱스 구축 (비동기 백그라운드로 실행) ──────────────────
    print("[startup] fastembed 시맨틱 인덱스 구축 중...")
    try:
        import sys as _sys, asyncio, concurrent.futures
        # /app/api 경로 우선 설정 (diagnose_engine과 같은 경로)
        if "/app/api" not in _sys.path:
            _sys.path.insert(0, "/app/api")
        from semantic_search import build_index
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            n_indexed = await loop.run_in_executor(pool, build_index)
        # 전역 캐시에 모듈 참조 저장 → search_vector에서 동일 인스턴스 접근
        import semantic_search as _sem_mod
        _cache["semantic_module"] = _sem_mod
        # diagnose_engine에도 직접 주입 (sys.path 충돌 방지)
        try:
            import sys as _sys2
            if "diagnose_engine" in _sys2.modules:
                _sys2.modules["diagnose_engine"]._SEM_MOD = _sem_mod
                print(f"[startup] ✅ diagnose_engine._SEM_MOD 주입 완료")
            else:
                import diagnose_engine as _de
                _de._SEM_MOD = _sem_mod
                print(f"[startup] ✅ diagnose_engine 로드 후 주입 완료")
        except Exception as _inj_e:
            print(f"[startup] ⚠️ _SEM_MOD 주입 실패: {_inj_e}")
        print(f"[startup] ✅ 시맨틱 인덱스 완료: {n_indexed}개 레코드 (index_size={_sem_mod.index_size()})")
    except Exception as e:
        print(f"[startup] ⚠️ 시맨틱 인덱스 실패: {e}")

    print("[startup] sentence-transformers 모델 로딩...")
    try:
        from sentence_transformers import SentenceTransformer
        _cache["model"] = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        print("[startup] ✅ 모델(384) 로드 완료")
        # examples/errors/docs 컬렉션은 bge-m3 (1024차원) 사용
        _cache["model_1024"] = SentenceTransformer("BAAI/bge-m3", device="cpu")
        print("[startup] ✅ 모델(1024/bge-m3) 로드 완료")
    except Exception as e:
        print(f"[startup] ⚠️ 모델 로드 실패: {e}")

    print("[startup] ChromaDB 연결 중...")
    try:
        import chromadb
        _cache["chroma"] = chromadb.PersistentClient(path=str(CHROMA_DIR))
        print("[startup] ✅ ChromaDB 연결 완료")
    except Exception as e:
        print(f"[startup] ⚠️ ChromaDB 연결 실패: {e}")

    print("[startup] 지식 그래프 로딩...")
    try:
        with open(GRAPH_PATH, "rb") as f:
            _cache["graph"] = pickle.load(f)
        nodes = _cache["graph"].number_of_nodes()
        edges = _cache["graph"].number_of_edges()
        print(f"[startup] ✅ 그래프 로드 완료 (노드 {nodes}, 엣지 {edges})")
    except Exception as e:
        print(f"[startup] ⚠️ 그래프 로드 실패: {e}")

    # search_executor의 전역 캐시에 주입
    # ChromaDB 컬렉션(errors/docs/examples)은 BAAI/bge-m3 (1024-dim)으로 인덱싱됨
    # → model_1024를 주입해야 dimension mismatch 해결
    try:
        import search_executor as se
        se._model  = _cache.get("model_1024") or _cache.get("model")  # bge-m3 우선
        se._client = _cache["chroma"]
        se._graph  = _cache["graph"]
        model_name = "bge-m3(1024)" if _cache.get("model_1024") else "MiniLM(384)"
        print(f"[startup] ✅ search_executor 캐시 주입 완료 (model={model_name})")
    except Exception as e:
        print(f"[startup] ⚠️ search_executor 캐시 주입 실패: {e}")

    _cache["ready"] = True
    print("[startup] 🚀 MEEP-KB 서버 준비 완료")


# ── 요청/응답 모델 ─────────────────────────────────────────────────────────────
class SearchRequest(BaseModel):
    query: str
    n: int = 5


class ChatMessage(BaseModel):
    role: str       # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    n: int = 5


# ── 핵심 검색 로직 ─────────────────────────────────────────────────────────────
def _run_search(query: str, n: int = 5) -> dict:
    """검색 + coverage 판단 + 필요시 generation"""
    from intent_analyzer  import analyze
    from search_router    import route
    from search_executor  import execute
    from coverage_checker import check_coverage
    from generator        import generate

    t0 = time.time()

    # 1. 의도 분석
    intent = analyze(query, use_llm=True, verbose=False)

    # 2. 라우팅
    plan = route(intent, n=n)

    # 3. DB 검색
    results = execute(plan, query, intent)

    # 4. Coverage 판단
    coverage = check_coverage(intent, results)

    # 5. 모드 결정 + 생성
    elapsed_ms = int((time.time() - t0) * 1000)
    methods_used = plan.methods

    if coverage["use_generation"]:
        gen = generate(query, intent, results)
        mode = "generation"
        answer = gen["answer"]
        hallucination_warning = True
        warning_message = gen["warning_message"]
    else:
        mode = "db_only"
        answer = None
        hallucination_warning = False
        warning_message = None

    # results를 JSON 직렬화 가능하게 정리
    clean_results = []
    for r in results:
        clean_results.append({
            "source":   r.get("source", ""),
            "type":     r.get("type", ""),
            "score":    round(float(r.get("score", 0)), 3),
            "title":    r.get("title", ""),
            "category": r.get("category", ""),
            "cause":    r.get("cause", ""),
            "solution": r.get("solution", ""),
            "url":      r.get("url", ""),
            "code":     r.get("code", ""),
        })

    response = {
        "intent": {
            "type":            intent.get("intent", "unknown"),
            "lang":            intent.get("lang", "en"),
            "confidence":      round(float(intent.get("confidence", 0)), 2),
            "keywords":        intent.get("keywords", []),
            "pipeline_hit":      intent.get("pipeline_hit", False),
            "pipeline_category": intent.get("pipeline_category", None),
            "pipeline_stage":    intent.get("pipeline_stage", None),
            "pipeline_stage_idx": intent.get("pipeline_stage_idx", 0),
        },
        "mode":          mode,
        "results":       clean_results,
        "answer":        answer,
        "methods_used":  methods_used,
        "elapsed_ms":    elapsed_ms,
        "coverage":      {
            "sufficient":    coverage["sufficient"],
            "reason":        coverage["reason"],
            "use_generation": coverage["use_generation"],
        },
        "hallucination_warning": hallucination_warning,
        "warning_message": warning_message,
    }

    return response


# ── 엔드포인트 ─────────────────────────────────────────────────────────────────
@app.post("/api/search")
@limiter.limit("10/minute")
async def search(request: Request, req: SearchRequest):
    """단순 검색 (히스토리 없음) + 개념 섹션 포함"""
    result = _run_search(req.query, req.n)

    # 개념 감지 및 concept 섹션 추가
    try:
        import sys as _sys
        _sys.path.insert(0, str(BASE / "api"))
        from concept_detector import detect_concept, is_concept_question

        detected = detect_concept(req.query)
        if detected and is_concept_question(req.query):
            conn = sqlite3.connect(str(DB_PATH), timeout=10)
            row = conn.execute(
                "SELECT name, name_ko, summary, demo_code FROM concepts WHERE name=?",
                (detected,)
            ).fetchone()
            conn.close()
            if row:
                result["concept"] = {
                    "matched": row[0],
                    "name_ko": row[1],
                    "summary": row[2],
                    "demo_code": row[3],
                }
    except Exception:
        pass  # concept 섹션 추가 실패해도 기본 검색 결과는 반환

    return result


@app.post("/api/chat")
@limiter.limit("10/minute")
async def chat(request: Request, req: ChatRequest):
    """대화형 검색 (히스토리 포함)"""
    # 히스토리를 쿼리에 컨텍스트로 추가 (최근 2턴)
    query = req.message
    if req.history:
        recent = req.history[-4:]  # 최근 4개 메시지
        ctx_parts = []
        for msg in recent:
            role = "사용자" if msg.role == "user" else "AI"
            ctx_parts.append(f"{role}: {msg.content[:100]}")
        ctx = "\n".join(ctx_parts)
        # 컨텍스트를 쿼리 앞에 붙여서 의도 분석에 활용
        enriched_query = f"[이전 대화:\n{ctx}\n]\n현재 질문: {query}"
    else:
        enriched_query = query

    result = _run_search(enriched_query, req.n)

    # ── 개념 감지 → concept 섹션 추가 (풍부한 데이터) ──────────────────────
    try:
        import sys as _sys
        _sys.path.insert(0, str(BASE / "api"))
        from concept_detector import detect_concept, is_concept_question, get_concept_confidence

        detected = detect_concept(query)
        if detected:
            confidence = get_concept_confidence(query, detected)
            conn = sqlite3.connect(str(DB_PATH), timeout=10)
            row = conn.execute("""
                SELECT name, name_ko, summary, explanation, demo_code, demo_description,
                       result_images, common_mistakes, related_concepts, difficulty, category
                FROM concepts WHERE name=?
            """, (detected,)).fetchone()

            # FTS fallback — 이름이 DB에 없으면 full-text 검색
            if not row:
                row = conn.execute("""
                    SELECT name, name_ko, summary, explanation, demo_code, demo_description,
                           result_images, common_mistakes, related_concepts, difficulty, category
                    FROM concepts
                    WHERE LOWER(name) LIKE LOWER(?)
                       OR LOWER(name_ko) LIKE LOWER(?)
                    LIMIT 1
                """, (f"%{detected}%", f"%{detected}%")).fetchone()

            conn.close()
            if row:
                import json as _json
                try:
                    mistakes = _json.loads(row[7] or "[]")
                except:
                    mistakes = []
                try:
                    related = _json.loads(row[8] or "[]")
                except:
                    related = []

                result["concept"] = {
                    "matched":       row[0],
                    "name_ko":       row[1],
                    "summary":       row[2],
                    "explanation":   row[3],
                    "demo_code":     row[4],
                    "demo_description": row[5],
                    "result_images": row[6],
                    "common_mistakes": mistakes,
                    "related_concepts": related,
                    "difficulty":    row[9],
                    "category":      row[10],
                    "confidence":    confidence,
                }
    except Exception as _ce:
        pass  # concept 실패해도 기본 검색 결과 반환

    # 히스토리 업데이트
    new_history = list(req.history)
    new_history.append({"role": "user", "content": req.message})

    # 어시스턴트 응답 요약
    if result["answer"]:
        assistant_content = result["answer"][:300] + "..."
    elif result["results"]:
        titles = [r["title"] for r in result["results"][:3]]
        assistant_content = f"DB 검색 결과 {len(result['results'])}건: " + ", ".join(titles)
    else:
        assistant_content = "관련 자료를 찾지 못했습니다."

    new_history.append({"role": "assistant", "content": assistant_content})
    result["history"] = new_history

    return result


@app.get("/api/status")
async def status():
    """DB 상태 정보"""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        db_errors   = conn.execute("SELECT COUNT(*) FROM errors").fetchone()[0]
        db_examples = conn.execute("SELECT COUNT(*) FROM examples").fetchone()[0]
        db_docs     = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        conn.close()
    except Exception:
        db_errors = db_examples = db_docs = -1

    graph = _cache.get("graph")
    if graph:
        graph_nodes = graph.number_of_nodes()
        graph_edges = graph.number_of_edges()
    else:
        graph_nodes = graph_edges = -1

    return {
        "db_errors":   db_errors,
        "db_examples": db_examples,
        "db_docs":     db_docs,
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
        "server_ready": _cache.get("ready", False),
    }


# ── 정적 파일 서빙 ────────────────────────────────────────────────────────────
# 실행 결과 이미지 서빙 (항상)
RESULTS_DIR = BASE / "db/results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/results", StaticFiles(directory=str(RESULTS_DIR)), name="results")

WEB_DIR = BASE / "web"
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/")
    async def root():
        return FileResponse(str(WEB_DIR / "index.html"))
else:
    @app.get("/")
    async def root():
        return {"message": "MEEP-KB API 서버 가동 중", "docs": "/docs"}


@app.get("/dict", response_class=HTMLResponse)
async def pattern_dictionary():
    """MEEP-KB Pattern Dictionary — readthedocs 스타일 HTML 사전 페이지"""
    sys.path.insert(0, str(BASE / "api"))
    import importlib
    import dict_page
    importlib.reload(dict_page)
    return HTMLResponse(content=dict_page.generate_html(), status_code=200)


@app.get("/eidl", response_class=HTMLResponse)
async def eidl_repository():
    """EIDL 연구실 GitHub 레포지토리 전체 정리 페이지"""
    sys.path.insert(0, str(BASE / "api"))
    import importlib
    import eidl_page
    importlib.reload(eidl_page)
    return HTMLResponse(content=eidl_page.generate_eidl_html(), status_code=200)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765, reload=False)


# ── 시뮬레이션 예제 저장 시스템 ──────────────────────────────────────────────

class IngestExampleRequest(BaseModel):
    title: str
    code: str
    description: str
    tags: str = ""
    source_repo: str = "local_notebook"
    author: str = "jin"
    file_path: str = ""


@app.post("/api/ingest/example")
async def ingest_example(req: IngestExampleRequest, _: None = Depends(verify_ingest_key)):
    """Jupyter 노트북 시뮬레이션 예제를 meep-kb에 저장 (SQLite + ChromaDB)"""
    import uuid, datetime as dt

    # 1. SQLite 저장
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.execute(
            "INSERT INTO examples (title, code, description, tags, source_repo, author, file_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                req.title[:500],
                req.code[:10000],
                req.description[:3000],
                req.tags[:500],
                req.source_repo[:200],
                req.author[:100],
                req.file_path[:500],
                dt.datetime.now().isoformat(),
            )
        )
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()
    except Exception as e:
        return {"ok": False, "error": f"SQLite: {e}"}

    # 2. ChromaDB 벡터 저장 (bge-m3 1024차원 사용)
    chroma_ok = False
    chroma_err = None
    try:
        client = _cache.get("chroma")
        model  = _cache.get("model_1024") or _cache.get("model")
        if client and model:
            col  = client.get_or_create_collection("examples")
            text = f"TITLE: {req.title}\nTAGS: {req.tags}\nDESC: {req.description}\nCODE:\n{req.code[:2000]}"
            emb  = model.encode(text).tolist()
            col.add(
                ids=[f"example_{row_id}_{uuid.uuid4().hex[:8]}"],
                embeddings=[emb],
                documents=[text[:3000]],
                metadatas=[{
                    "source":      req.source_repo,
                    "type":        "example",
                    "title":       req.title,
                    "tags":        req.tags,
                    "author":      req.author,
                    "created_at":  dt.datetime.now().isoformat(),
                }],
            )
            chroma_ok = True
    except Exception as e:
        chroma_err = str(e)

    return {
        "ok":          True,
        "sqlite_id":   row_id,
        "chroma_ok":   chroma_ok,
        "chroma_error": chroma_err,
        "message":     f"예제 저장 완료 (id={row_id}, title='{req.title}')",
    }


# ── 시뮬레이션 에러 누적 시스템 ──────────────────────────────────────────────

class IngestErrorRequest(BaseModel):
    error_msg: str
    solution: str
    cause: str = ""
    category: str = "runtime"
    code: str = ""
    stage: str = ""
    tags: str = ""
    source_type: str = "simulation_log"


# ── sim_errors 직접 저장 (MARL 자동 수정 결과 포함) ──────────────────────────

class IngestSimErrorRequest(BaseModel):
    error_type: str                        # "MPIError", "Divergence" 등
    error_message: str                     # 실제 traceback/에러 메시지
    original_code: str = ""               # 오류 발생 코드
    fixed_code: str = ""                  # 수정된 코드
    fix_description: str = ""            # 한국어 수정 설명
    root_cause: str = ""                  # 근본 원인
    context: str = ""                     # 추가 컨텍스트
    fix_keywords: str = "[]"             # JSON 배열 문자열
    pattern_name: str = ""               # 패턴/프로젝트 이름
    source: str = "marl_auto"            # 데이터 출처
    fix_worked: int = 1                   # 검증 여부 (1=확인됨)
    project_id: str = ""
    meep_version: str = ""


@app.post("/api/ingest/sim_error")
async def ingest_sim_error(req: IngestSimErrorRequest, _: None = Depends(verify_ingest_key)):
    """
    MARL 자동 수정 결과 + ErrorInjector + Solution Structurer 결과를
    sim_errors 테이블에 직접 저장.
    verified(fix_worked=1) 항목은 /api/diagnose에서 즉시 활용.
    """
    import uuid, datetime as dt
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        run_id = f"{req.source}_{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO sim_errors
              (run_id, project_id, error_type, error_message, meep_version,
               context, root_cause, fix_applied, fix_worked,
               fix_description, fix_keywords, pattern_name, source,
               original_code, fixed_code, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            req.project_id or "unknown",
            req.error_type[:100],
            req.error_message[:2000],
            req.meep_version[:20] or "",
            req.context[:500],
            req.root_cause[:300],
            (req.fix_description or req.fixed_code)[:300],
            req.fix_worked,
            req.fix_description[:1000],
            req.fix_keywords[:500],
            req.pattern_name[:200],
            req.source[:50],
            req.original_code[:5000],
            req.fixed_code[:5000],
            "draft" if req.fixed_code else "low",
            dt.datetime.now().isoformat(),
        ))
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    # ChromaDB 벡터 저장
    chroma_ok = False
    try:
        import uuid as _uuid, datetime as _dt
        client = _cache.get("chroma")
        model  = _cache.get("model") or _cache.get("model_1024")
        if client and model:
            col  = client.get_or_create_collection("sim_errors_v1")
            text = (
                f"ERROR: {req.error_message[:500]}\n"
                f"CAUSE: {req.root_cause[:200]}\n"
                f"FIX: {req.fix_description[:400]}"
            )
            emb  = model.encode(text).tolist()
            col.add(
                ids=[f"sime_{row_id}_{_uuid.uuid4().hex[:6]}"],
                embeddings=[emb],
                documents=[text[:2000]],
                metadatas=[{
                    "error_type":  req.error_type,
                    "source":      req.source,
                    "fix_worked":  str(req.fix_worked),
                    "created_at":  _dt.datetime.now().isoformat(),
                }],
            )
            chroma_ok = True
    except Exception:
        pass

    return {
        "ok": True,
        "id": row_id,
        "chroma_ok": chroma_ok,
        "message": f"sim_error 저장 완료 (id={row_id}, type={req.error_type}, verified={req.fix_worked})",
    }


@app.post("/api/ingest/error")
async def ingest_error(req: IngestErrorRequest, _: None = Depends(verify_ingest_key)):
    """시뮬레이션 에러+해결책을 meep-kb에 저장 (SQLite + ChromaDB)"""
    import uuid, datetime as dt

    # 1. SQLite 저장
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        cause_text = req.cause + (f" [stage:{req.stage}]" if req.stage else "")
        conn.execute(
            "INSERT INTO errors (error_msg, category, cause, solution, source_url, source_type, verified) VALUES (?, ?, ?, ?, ?, ?, 1)",
            (req.error_msg[:3000], req.category, cause_text[:500], req.solution[:3000], "", req.source_type)
        )
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()
    except Exception as e:
        return {"ok": False, "error": f"SQLite: {e}"}

    # 2. ChromaDB 벡터 저장
    chroma_ok = False
    chroma_err = None
    try:
        client = _cache.get("chroma")
        model = _cache.get("model")
        if client and model:
            col = client.get_or_create_collection("errors")
            text = f"CODE: {req.code[:500]}\nERROR: {req.error_msg}\nCAUSE: {req.cause}\nSOLUTION: {req.solution}"
            emb = model.encode(text).tolist()
            col.add(
                ids=[f"sim_error_{row_id}_{uuid.uuid4().hex[:8]}"],
                embeddings=[emb],
                documents=[text[:2000]],
                metadatas=[{"source": "simulation_log", "type": "error",
                            "category": req.category, "stage": req.stage,
                            "tags": req.tags, "created_at": dt.datetime.now().isoformat()}],
            )
            chroma_ok = True
    except Exception as e:
        chroma_err = str(e)

    # 실시간 임베딩 인덱스 갱신 (confidence high/medium인 경우만)
    try:
        from semantic_search import add_to_index
        add_to_index(row_id)
    except Exception:
        pass

    return {"ok": True, "sqlite_id": row_id, "chroma_ok": chroma_ok,
            "chroma_error": chroma_err,
            "message": f"저장 완료 (id={row_id}, stage={req.stage or 'unknown'})"}


# ── sim_errors_unified 통합 저장 시스템 ──────────────────────────────────────

class IngestSimErrorUnifiedRequest(BaseModel):
    # ── 기존 IngestSimErrorRequest 13개 필드 ──────────────────────────────────
    error_type: str                        # "MPIError", "Divergence" 등
    error_message: str                     # 실제 traceback/에러 메시지
    original_code: str = ""               # 오류 발생 코드
    fixed_code: str = ""                  # 수정된 코드
    fix_description: str = ""            # 한국어 수정 설명
    root_cause: str = ""                  # 근본 원인
    context: str = ""                     # 추가 컨텍스트
    fix_keywords: str = "[]"             # JSON 배열 문자열
    pattern_name: str = ""               # 패턴/프로젝트 이름
    source: str = "marl_auto"            # 데이터 출처
    fix_worked: int = 1                   # 검증 여부 (1=확인됨)
    project_id: str = ""
    meep_version: str = ""
    # ── 실행 컨텍스트 ────────────────────────────────────────────────────────
    run_mode: str = ""
    run_stage: str = ""
    iteration: int = 0
    mpi_np: int = 1
    device_type: str = "general"
    wavelength_um: float = 0.0
    resolution: int = 0
    pml_thickness: float = 0.0
    cell_size: str = ""                   # JSON
    dim: int = 2
    uses_adjoint: int = 0
    uses_symmetry: int = 0
    run_mode_meta: str = ""
    # ── 에러 분류 ────────────────────────────────────────────────────────────
    error_class: str = ""
    traceback_full: str = ""
    # ── 증상 ─────────────────────────────────────────────────────────────────
    symptom: str = ""
    symptom_numerical: str = ""
    symptom_behavioral: str = ""
    symptom_error_pattern: str = ""
    # ── 원인 체인 ────────────────────────────────────────────────────────────
    physics_cause: str = ""
    code_cause: str = ""
    root_cause_chain: str = ""            # JSON
    trigger_code: str = ""
    trigger_line: str = ""
    # ── 수정 ─────────────────────────────────────────────────────────────────
    fix_type: str = ""
    original_code_raw: str = ""
    code_diff: str = ""
    verification_criteria: str = ""
    diagnostic_snippet: str = ""
    # ── 메타 ─────────────────────────────────────────────────────────────────
    code_hash: str = ""
    code_length: int = 0
    run_time_sec: float = 0.0


def _ensure_sim_errors_unified_table(conn: sqlite3.Connection):
    """sim_errors_unified 테이블이 없으면 자동 생성"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sim_errors_unified (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            origin_table        TEXT    DEFAULT 'pipeline',
            origin_id           INTEGER,
            source              TEXT    DEFAULT '',
            run_mode            TEXT    DEFAULT '',
            run_stage           TEXT    DEFAULT '',
            iteration           INTEGER DEFAULT 0,
            mpi_np              INTEGER DEFAULT 1,
            device_type         TEXT    DEFAULT 'general',
            wavelength_um       REAL    DEFAULT 0.0,
            resolution          INTEGER DEFAULT 0,
            pml_thickness       REAL    DEFAULT 0.0,
            cell_size           TEXT    DEFAULT '',
            dim                 INTEGER DEFAULT 2,
            uses_adjoint        INTEGER DEFAULT 0,
            uses_symmetry       INTEGER DEFAULT 0,
            run_mode_meta       TEXT    DEFAULT '',
            error_class         TEXT    DEFAULT '',
            error_type          TEXT    DEFAULT '',
            error_message       TEXT    DEFAULT '',
            traceback_full      TEXT    DEFAULT '',
            symptom             TEXT    DEFAULT '',
            symptom_numerical   TEXT    DEFAULT '',
            symptom_behavioral  TEXT    DEFAULT '',
            symptom_error_pattern TEXT  DEFAULT '',
            physics_cause       TEXT    DEFAULT '',
            code_cause          TEXT    DEFAULT '',
            root_cause          TEXT    DEFAULT '',
            root_cause_chain    TEXT    DEFAULT '',
            trigger_code        TEXT    DEFAULT '',
            trigger_line        TEXT    DEFAULT '',
            fix_type            TEXT    DEFAULT '',
            fix_description     TEXT    DEFAULT '',
            fix_keywords        TEXT    DEFAULT '[]',
            fix_applied         TEXT    DEFAULT '',
            original_code       TEXT    DEFAULT '',
            original_code_raw   TEXT    DEFAULT '',
            fixed_code          TEXT    DEFAULT '',
            code_diff           TEXT    DEFAULT '',
            fix_worked          INTEGER DEFAULT 1,
            verification_criteria TEXT  DEFAULT '',
            diagnostic_snippet  TEXT    DEFAULT '',
            pattern_name        TEXT    DEFAULT '',
            project_id          TEXT    DEFAULT '',
            run_id              TEXT    DEFAULT '',
            code_hash           TEXT    DEFAULT '',
            code_length         INTEGER DEFAULT 0,
            run_time_sec        REAL    DEFAULT 0.0,
            meep_version        TEXT    DEFAULT '',
            created_at          TEXT
        )
    """)
    conn.commit()


@app.post("/api/ingest/sim_error_unified")
async def ingest_sim_error_unified(req: IngestSimErrorUnifiedRequest, _: None = Depends(verify_ingest_key)):
    """
    통합 시뮬레이션 에러 저장 엔드포인트.
    sim_errors_unified 테이블(주)과 sim_errors 테이블(백패드)에 동시 저장.
    ChromaDB sim_errors_unified 컬렉션에 벡터 저장.
    """
    import uuid, datetime as dt

    run_id = f"{req.source}_{uuid.uuid4().hex[:8]}"
    now    = dt.datetime.now().isoformat()

    # ── 1. sim_errors_unified 테이블에 저장 (필수) ───────────────────────────
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        _ensure_sim_errors_unified_table(conn)
        conn.execute("""
            INSERT INTO sim_errors_unified (
                origin_table, source,
                run_mode, run_stage, iteration, mpi_np, device_type,
                wavelength_um, resolution, pml_thickness, cell_size,
                dim, uses_adjoint, uses_symmetry, run_mode_meta,
                error_class, error_type, error_message, traceback_full,
                symptom, symptom_numerical, symptom_behavioral, symptom_error_pattern,
                physics_cause, code_cause, root_cause, root_cause_chain,
                trigger_code, trigger_line,
                fix_type, fix_description, fix_keywords, fix_applied,
                original_code, original_code_raw, fixed_code, code_diff,
                fix_worked, verification_criteria, diagnostic_snippet,
                pattern_name, project_id, run_id,
                code_hash, code_length, run_time_sec, meep_version, created_at
            ) VALUES (
                'pipeline', ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?
            )
        """, (
            req.source[:50],
            req.run_mode[:50], req.run_stage[:50], req.iteration, req.mpi_np, req.device_type[:50],
            req.wavelength_um, req.resolution, req.pml_thickness, req.cell_size[:200],
            req.dim, req.uses_adjoint, req.uses_symmetry, req.run_mode_meta[:500],
            req.error_class[:100], req.error_type[:100], req.error_message[:5000], req.traceback_full[:5000],
            req.symptom[:500], req.symptom_numerical[:500],
            req.symptom_behavioral[:500], req.symptom_error_pattern[:500],
            req.physics_cause[:500], req.code_cause[:500],
            req.root_cause[:300], req.root_cause_chain[:1000],
            req.trigger_code[:1000], req.trigger_line[:200],
            req.fix_type[:100], req.fix_description[:1000], req.fix_keywords[:500],
            (req.fix_description or req.fixed_code)[:300],
            req.original_code[:5000], req.original_code_raw[:5000],
            req.fixed_code[:5000], req.code_diff[:5000],
            req.fix_worked, req.verification_criteria[:500], req.diagnostic_snippet[:2000],
            req.pattern_name[:200], req.project_id or "unknown", run_id,
            req.code_hash[:64], req.code_length, req.run_time_sec, req.meep_version[:20] or "", now,
        ))
        unified_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()
    except Exception as e:
        return {"ok": False, "id": None, "chroma_ok": False, "message": f"sim_errors_unified INSERT 실패: {e}"}

    # ── 2. sim_errors 백패드 저장 (실패해도 무시) ────────────────────────────
    try:
        conn2 = sqlite3.connect(str(DB_PATH), timeout=10)
        conn2.execute("""
            INSERT INTO sim_errors
              (run_id, project_id, error_type, error_message, meep_version,
               context, root_cause, fix_applied, fix_worked,
               fix_description, fix_keywords, pattern_name, source,
               original_code, fixed_code, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            req.project_id or "unknown",
            req.error_type[:100],
            req.error_message[:2000],
            req.meep_version[:20] or "",
            req.context[:500],
            req.root_cause[:300],
            (req.fix_description or req.fixed_code)[:300],
            req.fix_worked,
            req.fix_description[:1000],
            req.fix_keywords[:500],
            req.pattern_name[:200],
            req.source[:50],
            req.original_code[:5000],
            req.fixed_code[:5000],
            now,
        ))
        conn2.commit()
        conn2.close()
    except Exception:
        pass  # 백패드 실패는 무시

    # ── 3. ChromaDB sim_errors_unified 컬렉션에 벡터 저장 ───────────────────
    chroma_ok = False
    try:
        client = _cache.get("chroma")
        model  = _cache.get("model_1024") or _cache.get("model")
        if client and model:
            col  = client.get_or_create_collection("sim_errors_unified")
            text = (
                f"ERROR: {req.error_message[:500]}\n"
                f"CAUSE: {req.root_cause[:200]}\n"
                f"SYMPTOM: {req.symptom_numerical} {req.symptom_behavioral}\n"
                f"FIX: {req.fix_description[:400]}"
            )
            emb = model.encode(text).tolist()
            col.add(
                ids=[f"seu_{unified_id}_{uuid.uuid4().hex[:6]}"],
                embeddings=[emb],
                documents=[text[:3000]],
                metadatas=[{
                    "error_type":   req.error_type,
                    "source":       req.source,
                    "run_mode":     req.run_mode,
                    "resolution":   str(req.resolution),
                    "fix_worked":   str(req.fix_worked),
                    "created_at":   now,
                }],
            )
            chroma_ok = True
    except Exception:
        pass

    return {
        "ok":       True,
        "id":       unified_id,
        "chroma_ok": chroma_ok,
        "message":  f"sim_error_unified 저장 완료 (id={unified_id}, type={req.error_type})",
    }


# ── 실행 결과 저장 ─────────────────────────────────────────────────────────────

class IngestResultRequest(BaseModel):
    example_id: int
    result_images_b64: List[str] = []   # base64 인코딩 PNG 배열
    result_stdout: str = ""
    result_run_time: float = 0.0
    result_executed_at: str = ""
    result_status: str = "success"      # success/failed/timeout/skip


@app.post("/api/ingest/result")
async def ingest_result(req: IngestResultRequest, _: None = Depends(verify_ingest_key)):
    """run_examples.py가 실행한 결과를 DB + 이미지 파일로 저장"""
    import base64 as b64mod, datetime as dt

    RESULTS_DIR = BASE / "db/results"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # 이미지 저장
    saved_paths = []
    for i, b64str in enumerate(req.result_images_b64):
        img_name = f"example_{req.example_id}_{i:02d}.png"
        img_path = RESULTS_DIR / img_name
        try:
            img_data = b64mod.b64decode(b64str)
            img_path.write_bytes(img_data)
            saved_paths.append(str(img_path))
        except Exception as e:
            print(f"[ingest_result] 이미지 저장 실패 id={req.example_id} i={i}: {e}")

    executed_at = req.result_executed_at or dt.datetime.now().isoformat()

    # DB 업데이트
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.execute(
            """UPDATE examples SET
               result_images=?, result_stdout=?, result_run_time=?,
               result_executed_at=?, result_status=?
               WHERE id=?""",
            (
                json.dumps(saved_paths),
                req.result_stdout[:5000],
                req.result_run_time,
                executed_at,
                req.result_status,
                req.example_id,
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        return {"ok": False, "error": f"DB: {e}"}

    return {
        "ok":          True,
        "example_id":  req.example_id,
        "images_saved": len(saved_paths),
        "status":      req.result_status,
    }


# ── 예제 목록 조회 ─────────────────────────────────────────────────────────────

@app.post("/api/examples/list")
async def examples_list():
    """run_examples.py 용 예제 목록 반환"""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        rows = conn.execute(
            "SELECT id, title, code, result_status FROM examples ORDER BY id"
        ).fetchall()
        conn.close()
        return [
            {"id": r[0], "title": r[1] or "", "code": r[2] or "", "result_status": r[3] or "pending"}
            for r in rows
        ]
    except Exception as e:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# /api/mpi-check  — MPI deadlock 사전 검토 엔드포인트
# ══════════════════════════════════════════════════════════════════════════════

class MpiCheckRequest(BaseModel):
    code: str = ""


@app.post("/api/mpi-check")
@limiter.limit("60/minute")
async def mpi_check(request: Request, req: MpiCheckRequest):
    """
    MEEP 코드에서 MPI deadlock 유발 가능 패턴을 사전 검토.
    mpirun 실행 전에 호출하여 위험도와 권장 조치를 반환.

    risk_level: none | low | medium | high
    safe_to_run: false이면 반드시 코드 수정 후 실행
    """
    import sys as _sys
    _sys.path.insert(0, str(BASE / "api"))
    from diagnose_engine import check_mpi_deadlock_risk

    code = req.code.strip()
    if not code:
        return {"risk_level": "none", "safe_to_run": True, "issues": [], "recommendations": ["코드가 없습니다."]}

    result = check_mpi_deadlock_risk(code)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# /api/diagnose  — 코드 + 에러 진단 엔드포인트
# ══════════════════════════════════════════════════════════════════════════════

class DiagnoseRequest(BaseModel):
    code:  str = ""
    error: str = ""
    n:     int = 5


@app.post("/api/diagnose")
@limiter.limit("60/minute")
async def diagnose(request: Request, req: DiagnoseRequest):
    """
    MEEP 코드 + 에러 메시지를 받아 진단 결과 반환.
    1단계: 에러 파싱 + DB 검색 (FTS + sim_errors)
    2단계: 벡터 검색
    3단계: DB 부족 시 LLM 폴백
    """
    import sys as _sys
    _sys.path.insert(0, str(BASE / "api"))

    from diagnose_engine import (
        parse_error, search_db, search_vector,
        extract_physics_context, check_physics_issues,
        build_physics_diagnosis_prompt,
        extract_fixed_code,
        check_mpi_deadlock_risk,
        diagnose as _diagnose_full,
    )

    code  = req.code.strip()
    error = req.error.strip()

    # ── -1. 개념/물리 질문 감지 → /api/search로 라우팅 ──────────────────────────
    # error 필드에 에러 메시지가 아닌 질문/개념이 입력된 경우 처리
    _concept_signals = (
        error.endswith("?") or
        any(error.lower().startswith(kw) for kw in
            ("what ", "how ", "why ", "when ", "which ", "explain ", "describe ",
             "what is", "how do", "how to", "what are", "how does",
             "무엇", "어떻게", "왜", "언제", "설명해", "차이", "차이점",
             "difference", "compare", "best practice", "recommend")) or
        (not any(err in error for err in
                 ("Error", "error", "Exception", "Traceback", "Warning",
                  "NaN", "diverge", "timeout", "assert", "failed", "cannot",
                  "AttributeError", "TypeError", "ValueError", "RuntimeError",
                  "ModuleNotFoundError", "ImportError", "SyntaxError")) and
         len(error) > 10 and not code)  # 코드도 없고 에러패턴도 없으면 개념 질문
    )

    if _concept_signals:
        # 개념 질문 → search_executor + LLM 경로로 처리
        try:
            search_result = _run_search(error, n=req.n)
            raw_results   = search_result.get("results", [])
            # _run_search가 생성한 LLM 답변 우선 사용
            concept_answer = search_result.get("answer") or ""
        except Exception as _se:
            raw_results    = []
            concept_answer = ""

        # LLM으로 개념 답변 생성 (search에서 답변 못 했을 때만)
        if not concept_answer:
            try:
                import anthropic as _ant
                import os as _os
                _ant_key = _os.environ.get("ANTHROPIC_API_KEY", "")
                if _ant_key:
                    _cli = _ant.Anthropic(api_key=_ant_key)
                    _msg = _cli.messages.create(
                        model="claude-haiku-4-5",
                        max_tokens=600,
                        messages=[{"role": "user", "content":
                            f"You are a MEEP FDTD simulation expert. Answer concisely in the same language as the question:\n\n{error}\n\n"
                            f"Focus on practical MEEP usage with code examples if relevant."}]
                    )
                    concept_answer = _msg.content[0].text
            except Exception as _llm_e:
                concept_answer = f"[LLM 오류: {str(_llm_e)[:100]}]"

        suggestions = []
        for r in raw_results[:req.n]:
            try:
                score = float(r.get("score", 0.5))
            except (TypeError, ValueError):
                score = 0.5
            suggestions.append({
                "title":    r.get("title", r.get("category", "")),
                "cause":    r.get("snippet", r.get("cause", r.get("content", ""))[:400]),
                "solution": r.get("solution", r.get("url", "")),
                "code":     r.get("code", ""),
                "score":    score,
                "source":   r.get("source", "docs"),
                "type":     "concept",
            })

        return {
            "is_concept_question": True,
            "query":        error,
            "llm_answer":   concept_answer,
            "suggestions":  suggestions,
            "top_score":    suggestions[0]["score"] if suggestions else 0,
            "db_sufficient":bool(suggestions),
            "physics_issues": [],
            "mpi_risk":     None,
        }

    # ── 0. MPI deadlock 사전 검토 (코드 있을 때만) ──────────────────────────
    mpi_check_result = None
    if code:
        mpi_check_result = check_mpi_deadlock_risk(code)

    # ── 1. 에러 정보 파싱 ────────────────────────────────────────────────────
    error_info = parse_error(code, error)
    phys_ctx   = extract_physics_context(code)
    physics_issues = check_physics_issues(code, phys_ctx)

    # ── 2. DB 검색 ───────────────────────────────────────────────────────────
    db_results = search_db(error_info, code, error, n=req.n)

    # ── 3. 벡터 검색 ─────────────────────────────────────────────────────────
    query_for_vector = f"{error_info['primary_type']} {error[:200]} {' '.join(error_info['meep_keywords'][:3])}"
    vec_results = search_vector(
        query_for_vector, n=3,
        model=_cache.get("model") or _cache.get("model_1024"),
        client=_cache.get("chroma"),
    )

    # 결합 + 중복 제거
    seen = set()
    combined = []
    for r in db_results + vec_results:
        key = (r.get("title","") + r.get("cause",""))[:80]
        if key not in seen:
            seen.add(key)
            combined.append(r)
    combined.sort(key=lambda x: x.get("score", 0), reverse=True)

    top_score    = combined[0]["score"] if combined else 0
    db_sufficient = top_score >= 0.65 and len(combined) >= 2

    # ── 4. LLM 폴백 (DB 부족 시) ─────────────────────────────────────────────
    llm_result = {"available": False, "answer": ""}
    if not db_sufficient and (code or error):
        try:
            import anthropic, os
            api_key = os.environ.get("ANTHROPIC_API_KEY","")
            if api_key:
                prompt = build_physics_diagnosis_prompt(
                    code, error, error_info, combined[:3], phys_ctx,
                    physics_issues=physics_issues,
                )
                client_llm = anthropic.Anthropic(api_key=api_key)
                msg = client_llm.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}],
                )
                answer_text = msg.content[0].text
                llm_result = {
                    "available": True,
                    "answer": answer_text,
                    "fixed_code": extract_fixed_code(answer_text, code),
                }
        except Exception as e:
            llm_result = {"available": False, "answer": "", "error": str(e)}

    # fixed_code: LLM 우선, 없으면 DB에서
    fixed_code = llm_result.get("fixed_code")
    if not fixed_code:
        for r in combined:
            if r.get("code") and len(r["code"]) > max(len(code) * 0.3, 100):
                fixed_code = r["code"]
                break

    # 단계별 진단 프레임워크
    from diagnose_engine import detect_stage
    stages = detect_stage(code, error)
    diagnostic_stages = stages[:2] if stages else []
    primary_stage = stages[0] if stages else None

    return {
        "error_info":        error_info,
        "suggestions":       combined[:req.n],
        "db_sufficient":     db_sufficient,
        "top_score":         round(top_score, 3),
        "physics_context":   phys_ctx,
        "physics_issues":    physics_issues,
        "fixed_code":        fixed_code,
        "llm_result":        llm_result,
        "mpi_check":         mpi_check_result,
        "db_count":          len(db_results),
        "vec_count":         len(vec_results),
        "diagnostic_stages": diagnostic_stages,
        "primary_stage":     primary_stage,
    }


# ══════════════════════════════════════════════════════════════════════════════
# /api/diagnose/fix-and-run  — 수정 코드 생성 + Docker 실행 검증
# ══════════════════════════════════════════════════════════════════════════════

class FixAndRunRequest(BaseModel):
    code:        str = ""
    error:       str = ""
    run_timeout: int = 60   # Docker 실행 최대 시간(초)


@app.post("/api/diagnose/fix-and-run")
@limiter.limit("20/minute")
async def diagnose_fix_and_run(request: Request, req: FixAndRunRequest):
    """
    MEEP 코드 + 에러 → 진단 → 수정 코드 생성 → Docker 실행 검증.

    1. /api/diagnose 로직으로 fixed_code 획득
    2. Docker 컨테이너에서 경량 실행 (resolution=10, until=20)
    3. 실패 시 run_stderr로 2차 진단 (최대 1회 재시도)
    4. 결과 반환

    Returns:
        diagnose 결과 + run_result + retry_result (실패 시)
    """
    import sys as _sys
    _sys.path.insert(0, str(BASE / "api"))

    from diagnose_engine import (
        parse_error, search_db, search_vector,
        extract_physics_context, check_physics_issues,
        build_physics_diagnosis_prompt, extract_fixed_code,
        check_mpi_deadlock_risk,
    )
    from fix_runner import run_fixed_code

    code  = req.code.strip()
    error = req.error.strip()
    timeout = min(max(req.run_timeout, 10), 120)  # 10~120초 클램프

    if not code and not error:
        return {"error": "code 또는 error를 입력하세요."}

    # ── 1단계: 진단 + fixed_code 획득 ──────────────────────────────────────
    error_info     = parse_error(code, error)
    phys_ctx       = extract_physics_context(code)
    physics_issues = check_physics_issues(code, phys_ctx)
    db_results     = search_db(error_info, code, error, n=5)

    query_v = f"{error_info['primary_type']} {error[:200]} {' '.join(error_info['meep_keywords'][:3])}"
    vec_results = search_vector(
        query_v, n=3,
        model=_cache.get("model") or _cache.get("model_1024"),
        client=_cache.get("chroma"),
    )

    seen, combined = set(), []
    for r in db_results + vec_results:
        key = (r.get("title","") + r.get("cause",""))[:80]
        if key not in seen:
            seen.add(key); combined.append(r)
    combined.sort(key=lambda x: x.get("score", 0), reverse=True)

    top_score    = combined[0]["score"] if combined else 0
    db_sufficient = top_score >= 0.65 and len(combined) >= 2

    # LLM으로 fixed_code 생성
    fixed_code   = None
    llm_result   = {"available": False, "answer": ""}
    if not db_sufficient and (code or error):
        try:
            import anthropic, os as _os
            api_key = _os.environ.get("ANTHROPIC_API_KEY", "")
            if api_key:
                prompt = build_physics_diagnosis_prompt(
                    code, error, error_info, combined[:3], phys_ctx,
                    physics_issues=physics_issues,
                )
                client_llm = anthropic.Anthropic(api_key=api_key)
                msg = client_llm.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}],
                )
                answer_text = msg.content[0].text
                fixed_code  = extract_fixed_code(answer_text, code)
                llm_result  = {
                    "available": True,
                    "answer": answer_text,
                    "fixed_code": fixed_code,
                }
        except Exception as e:
            llm_result = {"available": False, "answer": "", "error": str(e)}

    # DB에서 fixed_code 보완
    if not fixed_code:
        for r in combined:
            if r.get("code") and len(r["code"]) > max(len(code) * 0.3, 100):
                fixed_code = r["code"]; break

    # ── 2단계: Docker 실행 검증 ─────────────────────────────────────────────
    run_result = None
    retry_result = None

    if fixed_code:
        run_result = run_fixed_code(fixed_code, timeout=timeout)

        # ── 3단계: 실패 시 1회 재시도 ──────────────────────────────────────
        if not run_result["success"] and not run_result.get("blocked"):
            run_err = run_result.get("stderr", "") + run_result.get("stdout", "")
            if run_err and (code or error):
                try:
                    api_key = __import__("os").environ.get("ANTHROPIC_API_KEY", "")
                    if api_key:
                        retry_error_info = parse_error(fixed_code, run_err)
                        retry_phys       = extract_physics_context(fixed_code)
                        retry_issues     = check_physics_issues(fixed_code, retry_phys)
                        retry_prompt     = build_physics_diagnosis_prompt(
                            fixed_code, run_err, retry_error_info, combined[:2],
                            retry_phys, physics_issues=retry_issues,
                        )
                        client_llm2 = __import__("anthropic").Anthropic(api_key=api_key)
                        msg2 = client_llm2.messages.create(
                            model="claude-sonnet-4-6",
                            max_tokens=4096,
                            messages=[{"role": "user", "content": retry_prompt}],
                        )
                        retry_answer  = msg2.content[0].text
                        retry_fixed   = extract_fixed_code(retry_answer, fixed_code)
                        if retry_fixed:
                            retry_result = run_fixed_code(retry_fixed, timeout=timeout)
                            retry_result["llm_answer"] = retry_answer
                            retry_result["fixed_code"] = retry_fixed
                except Exception:
                    pass

    return {
        "error_info":      error_info,
        "physics_issues":  physics_issues,
        "physics_context": phys_ctx,
        "db_sufficient":   db_sufficient,
        "top_score":       round(top_score, 3),
        "llm_result":      llm_result,
        "fixed_code":      fixed_code,
        "run_result":      run_result,
        "retry_result":    retry_result,
        "suggestions":     combined[:5],
    }


# ══════════════════════════════════════════════════════════════════════════════
# /api/concept  — MEEP 개념 설명 엔드포인트
# ══════════════════════════════════════════════════════════════════════════════

class ConceptRequest(BaseModel):
    query: str          # "PML이 뭐야", "EigenmodeSource 설명"
    include_code: bool = True

    include_images: bool = True


@app.post("/api/concept")
@limiter.limit("30/minute")
async def get_concept(request: Request, req: ConceptRequest):
    """
    MEEP 개념 질문에 개념 설명 + 데모 코드 + 실행 결과 반환.

    질문 예시:
    - "PML이 뭐야?"
    - "EigenmodeSource 어떻게 써?"
    - "resolution 얼마로 설정해야 해?"
    """
    import sys as _sys
    _sys.path.insert(0, str(BASE / "api"))
    from concept_detector import detect_concept, get_concept_confidence

    query = req.query.strip()

    # 1. 개념 키워드 감지
    detected = detect_concept(query)
    confidence = get_concept_confidence(query, detected) if detected else 0.0

    concept_row = None

    # 2. concepts 테이블 FTS 검색
    if detected:
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=10)
            row = conn.execute(
                """SELECT name, name_ko, aliases, category, difficulty,
                   summary, explanation, physics_background, common_mistakes,
                   related_concepts, demo_code, demo_description,
                   result_stdout, result_images, result_executed_at, result_status,
                   meep_version, doc_url
                   FROM concepts WHERE name=?""",
                (detected,)
            ).fetchone()
            conn.close()
            if row:
                concept_row = row
        except Exception as e:
            print(f"[get_concept] DB 검색 실패: {e}")

    # 3. 키워드 미감지 또는 DB 없으면 FTS 검색
    if not concept_row:
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=10)
            # FTS 전문 검색
            fts_rows = conn.execute(
                """SELECT c.name, c.name_ko, c.aliases, c.category, c.difficulty,
                   c.summary, c.explanation, c.physics_background, c.common_mistakes,
                   c.related_concepts, c.demo_code, c.demo_description,
                   c.result_stdout, c.result_images, c.result_executed_at, c.result_status,
                   c.meep_version, c.doc_url
                   FROM concepts c
                   JOIN concepts_fts ON c.id = concepts_fts.rowid
                   WHERE concepts_fts MATCH ?
                   LIMIT 1""",
                (query,)
            ).fetchall()
            conn.close()
            if fts_rows:
                concept_row = fts_rows[0]
                if not detected:
                    detected = concept_row[0]
                    confidence = 0.75
        except Exception as e:
            print(f"[get_concept] FTS 검색 실패: {e}")

    # 4. 개념 없으면 → LLM fallback
    if not concept_row:
        # docs 테이블 검색 후 LLM 생성
        try:
            import anthropic as _anth
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if api_key:
                client_llm = _anth.Anthropic(api_key=api_key)
                prompt = f"""당신은 MEEP FDTD 전문가입니다.
다음 질문에 답하세요: {query}

간결하고 명확하게 1~2단락으로 답변하세요. 수식은 LaTeX ($...$) 형식으로 작성하세요."""
                msg = client_llm.messages.create(
                    model="claude-3-5-haiku-20241022",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}],
                )
                return {
                    "matched_concept": None,
                    "name_ko": None,
                    "category": None,
                    "difficulty": None,
                    "summary": msg.content[0].text,
                    "explanation": msg.content[0].text,
                    "physics_background": None,
                    "common_mistakes": [],
                    "related_concepts": [],
                    "demo_code": None if not req.include_code else None,
                    "demo_description": None,
                    "result_status": None,
                    "result_images": [],
                    "result_stdout": "",
                    "doc_url": None,
                    "confidence": 0.5,
                    "source": "llm_fallback",
                }
        except Exception as e:
            return {"error": f"개념을 찾지 못했습니다: {e}", "query": query}

        return {"error": "해당 MEEP 개념을 찾지 못했습니다.", "query": query}

    # 5. 응답 구성
    r = concept_row
    common_mistakes = []
    try:
        common_mistakes = json.loads(r[8]) if r[8] else []
    except:
        common_mistakes = [r[8]] if r[8] else []

    related_concepts = []
    try:
        related_concepts = json.loads(r[9]) if r[9] else []
    except:
        related_concepts = [r[9]] if r[9] else []

    result_images = []
    try:
        result_images = json.loads(r[13]) if r[13] else []
    except:
        result_images = []

    return {
        "matched_concept":  r[0],
        "name_ko":         r[1],
        "category":        r[3],
        "difficulty":      r[4],
        "summary":         r[5],
        "explanation":     r[6],
        "physics_background": r[7],
        "common_mistakes": common_mistakes,
        "related_concepts": related_concepts,
        "demo_code":       r[10] if req.include_code else None,
        "demo_description": r[11],
        "result_status":   r[15] or "pending",
        "result_images":   result_images if req.include_images else [],
        "result_stdout":   r[12] or "",
        "doc_url":         r[17],
        "confidence":      round(confidence, 2),
        "aliases":         json.loads(r[2]) if r[2] else [],
        "meep_version":    r[16],
        "source":          "db",
    }


@app.get("/api/concepts")
async def list_concepts():
    """등록된 MEEP 개념 목록 반환"""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        rows = conn.execute(
            """SELECT name, name_ko, category, difficulty, result_status,
               LENGTH(summary) as has_summary, LENGTH(demo_code) as has_code
               FROM concepts ORDER BY category, difficulty, name"""
        ).fetchall()
        conn.close()
        return {
            "total": len(rows),
            "concepts": [
                {
                    "name": r[0], "name_ko": r[1],
                    "category": r[2], "difficulty": r[3],
                    "result_status": r[4],
                    "has_summary": bool(r[5]),
                    "has_code": bool(r[6]),
                }
                for r in rows
            ]
        }
    except Exception as e:
        return {"error": str(e), "total": 0, "concepts": []}


# ── /api/stats/errors — 에러 커버리지 현황 ───────────────────────────────────

@app.get("/api/stats/errors")
async def stats_errors():
    """sim_errors 테이블 커버리지 통계"""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        total = conn.execute("SELECT COUNT(*) FROM sim_errors").fetchone()[0]
        verified = conn.execute("SELECT COUNT(*) FROM sim_errors WHERE fix_worked=1").fetchone()[0]
        by_type = conn.execute(
            "SELECT error_type, COUNT(*) as cnt FROM sim_errors GROUP BY error_type ORDER BY cnt DESC LIMIT 15"
        ).fetchall()
        by_source = conn.execute(
            "SELECT source, COUNT(*) as cnt FROM sim_errors GROUP BY source"
        ).fetchall()
        conn.close()
        return {
            "total": total,
            "verified": verified,
            "by_type": [{"type": r[0], "count": r[1]} for r in by_type],
            "by_source": [{"source": r[0], "count": r[1]} for r in by_source],
        }
    except Exception as e:
        return {"error": str(e)}


# ── /api/topo — Topology Optimization endpoints ──────────────────────────────

@app.post("/api/topo/runs")
async def create_topo_run(data: dict):
    """Create or upsert a topology optimization run record"""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.execute(
            """INSERT INTO topo_opt_runs
               (run_id, paper_id, device_type, optimizer, n_phases_completed,
                fom_init, fom_final, fom_paper, closure_pct, status,
                error_phase, error_type, resolution, beta_schedule,
                meep_version, mpi_ranks, elapsed_s, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(run_id) DO UPDATE SET
                 n_phases_completed=excluded.n_phases_completed,
                 fom_final=excluded.fom_final,
                 closure_pct=excluded.closure_pct,
                 status=excluded.status,
                 error_phase=excluded.error_phase,
                 error_type=excluded.error_type,
                 elapsed_s=excluded.elapsed_s,
                 notes=excluded.notes""",
            (
                data.get("run_id"), data.get("paper_id"), data.get("device_type"),
                data.get("optimizer"), data.get("n_phases_completed", 0),
                data.get("fom_init"), data.get("fom_final"), data.get("fom_paper"),
                data.get("closure_pct"), data.get("status", "running"),
                data.get("error_phase"), data.get("error_type"),
                data.get("resolution"), data.get("beta_schedule"),
                data.get("meep_version"), data.get("mpi_ranks", 1),
                data.get("elapsed_s"), data.get("notes"),
            )
        )
        conn.commit()
        conn.close()
        return {"ok": True, "run_id": data.get("run_id")}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/topo/runs")
async def list_topo_runs(paper_id: str = None, status: str = None, limit: int = 100):
    """List topology optimization runs, optionally filtered"""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        where_clauses = []
        params = []
        if paper_id:
            where_clauses.append("paper_id=?")
            params.append(paper_id)
        if status:
            where_clauses.append("status=?")
            params.append(status)
        where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        params.append(limit)
        rows = conn.execute(
            f"""SELECT run_id, paper_id, device_type, optimizer, n_phases_completed,
                       fom_init, fom_final, fom_paper, closure_pct, status,
                       error_phase, error_type, resolution, meep_version,
                       mpi_ranks, elapsed_s, created_at
                FROM topo_opt_runs {where}
                ORDER BY created_at DESC LIMIT ?""",
            params
        ).fetchall()
        conn.close()
        cols = ["run_id","paper_id","device_type","optimizer","n_phases_completed",
                "fom_init","fom_final","fom_paper","closure_pct","status",
                "error_phase","error_type","resolution","meep_version",
                "mpi_ranks","elapsed_s","created_at"]
        return {"total": len(rows), "runs": [dict(zip(cols, r)) for r in rows]}
    except Exception as e:
        return {"error": str(e), "total": 0, "runs": []}


@app.get("/api/topo/runs/{run_id}")
async def get_topo_run(run_id: str):
    """Get a single topology optimization run by run_id"""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        row = conn.execute(
            "SELECT * FROM topo_opt_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if not row:
            conn.close()
            return {"error": "not found"}
        cols = [d[0] for d in conn.execute("SELECT * FROM topo_opt_runs LIMIT 0").description]
        conn.close()
        return dict(zip(cols, row))
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/topo/phases")
async def create_topo_phase(data: dict):
    """Log a topology optimization phase result"""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.execute(
            """INSERT INTO topo_opt_phases
               (run_id, paper_id, device_type, phase_id, phase_name, status,
                error_type, error_msg, physics_issues, fom_value, grad_norm,
                input_flux, elapsed_s, stdout_tail)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data.get("run_id"), data.get("paper_id"), data.get("device_type"),
                data.get("phase_id"), data.get("phase_name"), data.get("status"),
                data.get("error_type"), data.get("error_msg"),
                data.get("physics_issues"), data.get("fom_value"),
                data.get("grad_norm"), data.get("input_flux"),
                data.get("elapsed_s"), data.get("stdout_tail"),
            )
        )
        conn.commit()
        conn.close()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/topo/phases/{run_id}")
async def get_topo_phases(run_id: str):
    """Get all phases for a topology optimization run"""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        rows = conn.execute(
            """SELECT phase_id, phase_name, status, error_type, error_msg,
                      physics_issues, fom_value, grad_norm, input_flux,
                      elapsed_s, created_at
               FROM topo_opt_phases WHERE run_id=? ORDER BY phase_id""",
            (run_id,)
        ).fetchall()
        conn.close()
        cols = ["phase_id","phase_name","status","error_type","error_msg",
                "physics_issues","fom_value","grad_norm","input_flux",
                "elapsed_s","created_at"]
        return {"run_id": run_id, "phases": [dict(zip(cols, r)) for r in rows]}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/topo/iterations")
async def log_topo_iterations(data: dict):
    """Bulk-insert topology optimization iteration data"""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        iterations = data.get("iterations", [])
        run_id = data.get("run_id")
        paper_id = data.get("paper_id")
        phase_id = data.get("phase_id", 6)
        conn.executemany(
            """INSERT INTO topo_opt_iterations
               (run_id, paper_id, phase_id, iteration, beta, fom,
                fom_delta, grad_norm, design_hash)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            [
                (
                    run_id, paper_id, phase_id,
                    it.get("iteration"), it.get("beta"), it.get("fom"),
                    it.get("fom_delta"), it.get("grad_norm"), it.get("design_hash"),
                )
                for it in iterations
            ]
        )
        conn.commit()
        conn.close()
        return {"ok": True, "inserted": len(iterations)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/topo/iterations/{run_id}")
async def get_topo_iterations(run_id: str, phase_id: int = None, limit: int = 500):
    """Get iteration history for a topology optimization run"""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        params = [run_id]
        phase_filter = ""
        if phase_id is not None:
            phase_filter = "AND phase_id=?"
            params.append(phase_id)
        params.append(limit)
        rows = conn.execute(
            f"""SELECT phase_id, iteration, beta, fom, fom_delta, grad_norm,
                       design_hash, created_at
                FROM topo_opt_iterations
                WHERE run_id=? {phase_filter}
                ORDER BY phase_id, iteration LIMIT ?""",
            params
        ).fetchall()
        conn.close()
        cols = ["phase_id","iteration","beta","fom","fom_delta","grad_norm",
                "design_hash","created_at"]
        return {"run_id": run_id, "count": len(rows),
                "iterations": [dict(zip(cols, r)) for r in rows]}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/topo/stats")
async def topo_stats():
    """Summary statistics for all topology optimization runs"""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        total = conn.execute("SELECT COUNT(*) FROM topo_opt_runs").fetchone()[0]
        by_status = conn.execute(
            "SELECT status, COUNT(*) FROM topo_opt_runs GROUP BY status"
        ).fetchall()
        by_device = conn.execute(
            "SELECT device_type, COUNT(*) FROM topo_opt_runs GROUP BY device_type ORDER BY 2 DESC LIMIT 20"
        ).fetchall()
        avg_closure = conn.execute(
            "SELECT AVG(closure_pct) FROM topo_opt_runs WHERE closure_pct IS NOT NULL"
        ).fetchone()[0]
        recent = conn.execute(
            """SELECT run_id, paper_id, device_type, status, closure_pct, created_at
               FROM topo_opt_runs ORDER BY created_at DESC LIMIT 10"""
        ).fetchall()
        conn.close()
        return {
            "total_runs": total,
            "by_status": [{"status": r[0], "count": r[1]} for r in by_status],
            "by_device": [{"device_type": r[0], "count": r[1]} for r in by_device],
            "avg_closure_pct": round(avg_closure, 2) if avg_closure else None,
            "recent": [
                {"run_id": r[0], "paper_id": r[1], "device_type": r[2],
                 "status": r[3], "closure_pct": r[4], "created_at": r[5]}
                for r in recent
            ]
        }
    except Exception as e:
        return {"error": str(e)}

# ══════════════════════════════════════════════════════════════════════════════
# /api/ingest/verified_fix  — 실행 검증된 에러 수정 사례 등록
# ══════════════════════════════════════════════════════════════════════════════

class VerifiedFixIngest(BaseModel):
    # 필수
    purpose: str
    original_code: str
    fixed_code: str
    exec_exit_code: int

    # 에러 정보
    error_output: Optional[str] = None
    error_type: Optional[str] = None
    error_pattern: Optional[str] = None

    # 실행 결과
    exec_stdout: Optional[str] = None
    exec_stderr: Optional[str] = None
    exec_run_time: Optional[float] = None
    exec_images: Optional[List[str]] = None

    # 수정 정보
    fix_description: Optional[str] = None
    code_diff: Optional[str] = None

    # 수치 검증 기준
    T_min: Optional[float] = None
    T_max: Optional[float] = None
    R_max: Optional[float] = None
    TR_sum_min: Optional[float] = None
    TR_sum_max: Optional[float] = None
    FOM_threshold: Optional[float] = None

    # 메타
    purpose_tags: Optional[List[str]] = None
    meep_version: Optional[str] = "1.28.0"
    mpi_np: Optional[int] = 1
    resolution: Optional[int] = None
    sim_params: Optional[dict] = None
    source: Optional[str] = "manual"
    project_id: Optional[str] = None
    manual_verified: Optional[int] = 0
    verified_by: Optional[str] = None


@app.post("/api/ingest/verified_fix")
async def ingest_verified_fix(req: VerifiedFixIngest):
    """
    실행 검증된 에러 수정 사례를 코퍼스에 등록.
    exec_exit_code=0 이어야 등록 가능.
    """
    import re, datetime

    # 실행 성공 여부 체크
    if req.exec_exit_code != 0:
        raise HTTPException(
            status_code=400,
            detail=f"exec_exit_code={req.exec_exit_code}: 실행 성공(0)한 경우만 등록 가능합니다."
        )

    # 자동 수치 검증
    auto_passed = 1  # 기본 통과 (수치 기준 없으면 통과로 간주)
    if req.exec_stdout:
        # T, R 파싱 시도
        t_match = re.search(r'[Tt]ransmittance[^\d]*([\d.]+)', req.exec_stdout)
        r_match = re.search(r'[Rr]eflectance[^\d]*([\d.]+)', req.exec_stdout)
        fom_match = re.search(r'FOM[^\d]*([\d.]+)', req.exec_stdout)

        t_val = float(t_match.group(1)) if t_match else None
        r_val = float(r_match.group(1)) if r_match else None
        fom_val = float(fom_match.group(1)) if fom_match else None

        # 수치 기준 체크
        if req.T_min is not None and t_val is not None and t_val < req.T_min:
            auto_passed = 0
        if req.T_max is not None and t_val is not None and t_val > req.T_max:
            auto_passed = 0
        if req.R_max is not None and r_val is not None and r_val > req.R_max:
            auto_passed = 0
        if req.TR_sum_min is not None and t_val is not None and r_val is not None:
            if t_val + r_val < req.TR_sum_min:
                auto_passed = 0
        if req.TR_sum_max is not None and t_val is not None and r_val is not None:
            if t_val + r_val > req.TR_sum_max:
                auto_passed = 0
        if req.FOM_threshold is not None and fom_val is not None and fom_val < req.FOM_threshold:
            auto_passed = 0

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    c = conn.cursor()
    c.execute("""
        INSERT INTO verified_fixes (
            purpose, purpose_tags,
            original_code, error_output, error_type, error_pattern,
            fixed_code, fix_description, code_diff,
            exec_stdout, exec_stderr, exec_exit_code, exec_run_time, exec_images,
            T_min, T_max, R_max, TR_sum_min, TR_sum_max, FOM_threshold,
            auto_passed, manual_verified, verified_by, verified_at,
            meep_version, mpi_np, resolution, sim_params, source, project_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        req.purpose,
        json.dumps(req.purpose_tags, ensure_ascii=False) if req.purpose_tags else None,
        req.original_code,
        req.error_output,
        req.error_type,
        req.error_pattern,
        req.fixed_code,
        req.fix_description,
        req.code_diff,
        req.exec_stdout,
        req.exec_stderr,
        req.exec_exit_code,
        req.exec_run_time,
        json.dumps(req.exec_images) if req.exec_images else None,
        req.T_min, req.T_max, req.R_max, req.TR_sum_min, req.TR_sum_max, req.FOM_threshold,
        auto_passed,
        req.manual_verified,
        req.verified_by,
        datetime.datetime.now().isoformat() if req.manual_verified else None,
        req.meep_version,
        req.mpi_np,
        req.resolution,
        json.dumps(req.sim_params, ensure_ascii=False) if req.sim_params else None,
        req.source,
        req.project_id,
    ))
    new_id = c.lastrowid
    conn.commit()

    # FTS 업데이트
    try:
        c.execute("""
            INSERT INTO verified_fixes_fts(rowid, purpose, error_pattern, fix_description, error_output)
            VALUES (?, ?, ?, ?, ?)
        """, (new_id, req.purpose, req.error_pattern or "", req.fix_description or "", req.error_output or ""))
        conn.commit()
    except Exception:
        pass
    conn.close()

    return {
        "id": new_id,
        "auto_passed": auto_passed,
        "message": f"verified_fix #{new_id} 등록 완료 (auto_passed={auto_passed})"
    }


@app.get("/api/verified_fixes")
async def list_verified_fixes(
    limit: int = 20,
    only_passed: bool = False,
    project_id: Optional[str] = None
):
    """검증된 수정 사례 목록 조회"""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    c = conn.cursor()

    conditions = []
    params = []
    if only_passed:
        conditions.append("(auto_passed=1 OR manual_verified=1)")
    if project_id:
        conditions.append("project_id=?")
        params.append(project_id)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    c.execute(f"""
        SELECT id, purpose, error_type, error_pattern, fix_description,
               auto_passed, manual_verified, source, project_id, created_at
        FROM verified_fixes
        {where}
        ORDER BY created_at DESC
        LIMIT ?
    """, params)

    cols = [d[0] for d in c.description]
    rows = [dict(zip(cols, r)) for r in c.fetchall()]
    conn.close()
    return {"total": len(rows), "items": rows}
