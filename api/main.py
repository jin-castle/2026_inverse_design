#!/usr/bin/env python3
"""
MEEP-KB FastAPI 백엔드 (Hybrid RAG)

포트: 8765
"""

import sys, os, time, sqlite3, pickle
from pathlib import Path
from typing import Optional, List, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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
        print("[startup] ✅ 모델 로드 완료")
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
            "type":       intent.get("intent", "unknown"),
            "lang":       intent.get("lang", "en"),
            "confidence": round(float(intent.get("confidence", 0)), 2),
            "keywords":   intent.get("keywords", []),
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


# ── 정적 파일 서빙 (프론트엔드) ───────────────────────────────────────────────
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765, reload=False)
