#!/usr/bin/env python3
"""
MEEP-KB 시맨틱 검색 (멀티링구얼 — 한국어/영어 모두 지원)
사용법:
  python query/semantic_search.py "시뮬레이션이 발산해"
  python query/semantic_search.py "adjoint 최적화 기울기" --type errors
  python query/semantic_search.py "legume z 슬랩 위치" --n 3
"""

import argparse, sqlite3
from pathlib import Path

DB_PATH    = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge.db")
CHROMA_DIR = Path("/mnt/c/Users/user/projects/meep-kb/db/chroma")
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

_model  = None
_client = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def get_client():
    global _client
    if _client is None:
        import chromadb
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client

def semantic_search(query: str, kind: str = "all", n: int = 5):
    if not CHROMA_DIR.exists():
        print("❌ ChromaDB 없음. `python embeddings/embed_multilingual.py` 먼저 실행하세요.")
        return

    model  = get_model()
    client = get_client()
    conn   = sqlite3.connect(str(DB_PATH), timeout=30)

    # 쿼리 벡터 직접 계산
    query_vec = model.encode([query]).tolist()

    results = []

    def qcol(cname, id_prefix, n_res):
        try:
            col = client.get_collection(cname)   # EF 없이 가져옴
            res = col.query(query_embeddings=query_vec,   # 미리 계산한 벡터 사용
                            n_results=min(n_res, col.count()),
                            include=["distances", "metadatas"])
            return res
        except Exception as e:
            print(f"  [{cname}] 검색 오류: {e}")
            return None

    if kind in ("all", "errors"):
        res = qcol("errors", "err_", n)
        if res and res["ids"][0]:
            for doc_id, dist in zip(res["ids"][0], res["distances"][0]):
                db_id = int(doc_id.replace("err_", ""))
                row   = conn.execute(
                    "SELECT error_msg, category, cause, solution, source_url FROM errors WHERE id=?", (db_id,)
                ).fetchone()
                if row:
                    results.append(("ERROR", 1 - dist, row))

    if kind in ("all", "examples"):
        res = qcol("examples", "ex_", n)
        if res and res["ids"][0]:
            for doc_id, dist in zip(res["ids"][0], res["distances"][0]):
                db_id = int(doc_id.replace("ex_", ""))
                row   = conn.execute(
                    "SELECT title, description, tags, code, source_repo FROM examples WHERE id=?", (db_id,)
                ).fetchone()
                if row:
                    results.append(("EXAMPLE", 1 - dist, row))

    if kind in ("all", "docs"):
        res = qcol("docs", "doc_", n)
        if res and res["ids"][0]:
            for doc_id, dist in zip(res["ids"][0], res["distances"][0]):
                db_id = int(doc_id.replace("doc_", ""))
                row   = conn.execute(
                    "SELECT section, content, url, simulator FROM docs WHERE id=?", (db_id,)
                ).fetchone()
                if row:
                    results.append(("DOC", 1 - dist, row))

    conn.close()
    results.sort(key=lambda x: x[1], reverse=True)

    print(f"\n🔍 시맨틱 검색: \"{query}\"")
    print(f"상위 {min(n, len(results))}건\n{'='*60}")

    for rtype, score, data in results[:n]:
        bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
        pct = int(score * 100)

        if rtype == "ERROR":
            msg, cat, cause, sol, url = data
            print(f"\n[{rtype}] [{cat}] 유사도 {pct}%  {bar}")
            print(f"  에러: {msg[:100]}")
            if cause: print(f"  원인: {(cause or '')[:150]}")
            if sol:   print(f"  ✅ 해결: {sol[:200]}")
            if url:   print(f"  🔗 {url}")

        elif rtype == "EXAMPLE":
            title, desc, tags, code, repo = data
            print(f"\n[{rtype}] 유사도 {pct}%  {bar}")
            print(f"  {title[:80]}  [{repo}]")
            if code:
                snippet = (code or "")[:250].strip().replace("\n", "\n  ")
                print(f"  ```python\n  {snippet}\n  ```")

        elif rtype == "DOC":
            section, content, url, sim = data
            print(f"\n[{rtype}] [{sim}] 유사도 {pct}%  {bar}")
            print(f"  {section}")
            if content: print(f"  {(content or '')[:180].strip()}...")
            if url:     print(f"  🔗 {url}")

    print(f"\n{'='*60}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MEEP-KB 시맨틱 검색 (한국어/영어)")
    parser.add_argument("query", help="자연어 검색어")
    parser.add_argument("--type", choices=["all","errors","examples","docs"], default="all")
    parser.add_argument("--n", type=int, default=5)
    args = parser.parse_args()
    semantic_search(args.query, args.type, args.n)
