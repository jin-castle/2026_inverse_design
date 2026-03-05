#!/usr/bin/env python3
"""
MEEP-KB FastAPI 백엔드 (Hybrid RAG)

포트: 8765
"""

import sys, os, time, sqlite3, pickle, json
from pathlib import Path
from typing import Optional, List, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

# ── 경로 설정 ─────────────────────────────────────────────────────────────────
BASE = Path(os.environ.get("APP_DIR", "/app"))
sys.path.insert(0, str(BASE / "agent"))
sys.path.insert(0, str(BASE / "query"))

DB_PATH    = BASE / "db/knowledge.db"
CHROMA_DIR = BASE / "db/chroma"
GRAPH_PATH = BASE / "db/knowledge_graph_v2.pkl"

# ── FastAPI 앱 ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="MEEP-KB Hybrid RAG API",
    description="MEEP 지식베이스 검색 API (DB 직출력 + LLM 생성 하이브리드)",
    version="1.0.0"
)

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
    try:
        import search_executor as se
        se._model  = _cache["model"]
        se._client = _cache["chroma"]
        se._graph  = _cache["graph"]
        print("[startup] ✅ search_executor 캐시 주입 완료")
    except Exception as e:
        print(f"[startup] ⚠️ search_executor/semantic_search 주입 실패: {e}")
    except Exception as e:
        print(f"[startup] ⚠️ search_executor 주입 실패: {e}")

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
async def search(req: SearchRequest):
    """단순 검색 (히스토리 없음)"""
    return _run_search(req.query, req.n)


@app.post("/api/chat")
async def chat(req: ChatRequest):
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
    from dict_page import generate_html
    return HTMLResponse(content=generate_html(), status_code=200)


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
async def ingest_example(req: IngestExampleRequest):
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


@app.post("/api/ingest/error")
async def ingest_error(req: IngestErrorRequest):
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

    return {"ok": True, "sqlite_id": row_id, "chroma_ok": chroma_ok,
            "chroma_error": chroma_err,
            "message": f"저장 완료 (id={row_id}, stage={req.stage or 'unknown'})"}


# ── 실행 결과 저장 ─────────────────────────────────────────────────────────────

class IngestResultRequest(BaseModel):
    example_id: int
    result_images_b64: List[str] = []   # base64 인코딩 PNG 배열
    result_stdout: str = ""
    result_run_time: float = 0.0
    result_executed_at: str = ""
    result_status: str = "success"      # success/failed/timeout/skip


@app.post("/api/ingest/result")
async def ingest_result(req: IngestResultRequest):
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