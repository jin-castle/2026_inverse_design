#!/usr/bin/env python3
"""
Search Executor — SearchPlan 에 따라 실제 검색 수행, 결과 통합
"""

import sys, sqlite3, pickle
from pathlib import Path

BASE = Path("/mnt/c/Users/user/projects/meep-kb")
sys.path.insert(0, str(BASE / "query"))

DB_PATH    = BASE / "db/knowledge.db"
CHROMA_DIR = BASE / "db/chroma"
GRAPH_PATH = BASE / "db/knowledge_graph_v2.pkl"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

_model  = None
_client = None
_graph  = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def get_chroma():
    global _client
    if _client is None:
        import chromadb
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def get_graph():
    global _graph
    if _graph is None:
        with open(GRAPH_PATH, "rb") as f:
            _graph = pickle.load(f)
    return _graph


# ── 키워드 검색 ──────────────────────────────────────────────────────────────
def keyword_search(query: str, db_types: list, n: int) -> list:
    """SQLite FTS5 검색 → 통합 결과 리스트"""
    results = []
    conn    = sqlite3.connect(str(DB_PATH), timeout=30)

    try:
        if "errors" in db_types or "all" in db_types:
            rows = conn.execute(
                "SELECT error_msg, category, cause, solution, source_url FROM errors "
                "WHERE errors MATCH ? LIMIT ?",
                (query, n)
            ).fetchall()
            for r in rows:
                results.append({
                    "source": "keyword", "type": "ERROR",
                    "score": 0.9,   # 키워드 매칭은 score 고정
                    "title": r[0][:100], "category": r[1] or "",
                    "cause": r[2] or "", "solution": r[3] or "",
                    "url": r[4] or "", "code": ""
                })

        if "examples" in db_types or "all" in db_types:
            rows = conn.execute(
                "SELECT title, description, tags, code, source_repo FROM examples "
                "WHERE examples MATCH ? LIMIT ?",
                (query, n)
            ).fetchall()
            for r in rows:
                results.append({
                    "source": "keyword", "type": "EXAMPLE",
                    "score": 0.9,
                    "title": r[0][:100], "category": r[2] or "",
                    "cause": "", "solution": "",
                    "url": r[4] or "", "code": (r[3] or "")[:300]
                })

        if "docs" in db_types or "all" in db_types:
            rows = conn.execute(
                "SELECT section, content, url, simulator FROM docs "
                "WHERE docs MATCH ? LIMIT ?",
                (query, n)
            ).fetchall()
            for r in rows:
                results.append({
                    "source": "keyword", "type": "DOC",
                    "score": 0.85,
                    "title": r[0][:100], "category": r[3] or "",
                    "cause": (r[1] or "")[:200], "solution": "",
                    "url": r[2] or "", "code": ""
                })
    except Exception as e:
        pass
    finally:
        conn.close()

    return results


# ── 벡터 검색 ────────────────────────────────────────────────────────────────
def vector_search(query: str, keywords: list, db_types: list, n: int) -> list:
    """ChromaDB 시맨틱 검색"""
    from semantic_search_v2 import augment_query

    results = []
    augmented = augment_query(query)
    model  = get_model()
    client = get_chroma()
    conn   = sqlite3.connect(str(DB_PATH), timeout=30)

    query_vec  = model.encode([augmented]).tolist()
    seen_ids   = set()
    seen_dedup = set()

    def qcol(cname, id_prefix, n_res):
        try:
            col = client.get_collection(cname)
            res = col.query(query_embeddings=query_vec,
                            n_results=min(n_res, col.count()),
                            include=["distances", "metadatas"])
            return res
        except Exception:
            return None

    try:
        if "errors" in db_types or "all" in db_types:
            res = qcol("errors", "err_", n)
            if res and res["ids"][0]:
                for doc_id, dist in zip(res["ids"][0], res["distances"][0]):
                    if doc_id in seen_ids: continue
                    seen_ids.add(doc_id)
                    score = 1 - dist
                    if score < 0.40: continue
                    db_id = int(doc_id.replace("err_", ""))
                    row   = conn.execute(
                        "SELECT error_msg, category, cause, solution, source_url FROM errors WHERE id=?", (db_id,)
                    ).fetchone()
                    if row:
                        results.append({
                            "source": "vector", "type": "ERROR", "score": round(score, 3),
                            "title": row[0][:100], "category": row[1] or "",
                            "cause": row[2] or "", "solution": row[3] or "",
                            "url": row[4] or "", "code": ""
                        })

        if "examples" in db_types or "all" in db_types:
            res = qcol("examples", "ex_", n)
            if res and res["ids"][0]:
                for doc_id, dist in zip(res["ids"][0], res["distances"][0]):
                    if doc_id in seen_ids: continue
                    seen_ids.add(doc_id)
                    score = 1 - dist
                    if score < 0.40: continue
                    db_id = int(doc_id.replace("ex_", ""))
                    row   = conn.execute(
                        "SELECT title, description, tags, code, source_repo FROM examples WHERE id=?", (db_id,)
                    ).fetchone()
                    if row:
                        results.append({
                            "source": "vector", "type": "EXAMPLE", "score": round(score, 3),
                            "title": row[0][:100], "category": row[2] or "",
                            "cause": "", "solution": "",
                            "url": row[4] or "", "code": (row[3] or "")[:300]
                        })

        if "docs" in db_types or "all" in db_types:
            res = qcol("docs", "doc_", n)
            if res and res["ids"][0]:
                for doc_id, dist in zip(res["ids"][0], res["distances"][0]):
                    if doc_id in seen_ids: continue
                    seen_ids.add(doc_id)
                    score = 1 - dist
                    if score < 0.40: continue
                    db_id = int(doc_id.replace("doc_", ""))
                    row   = conn.execute(
                        "SELECT section, content, url, simulator FROM docs WHERE id=?", (db_id,)
                    ).fetchone()
                    if row:
                        dedup = f"{row[0]}|{row[2]}"
                        if dedup in seen_dedup: continue
                        seen_dedup.add(dedup)
                        results.append({
                            "source": "vector", "type": "DOC", "score": round(score, 3),
                            "title": row[0][:100], "category": row[3] or "",
                            "cause": (row[1] or "")[:200], "solution": "",
                            "url": row[2] or "", "code": ""
                        })
    finally:
        conn.close()

    return results


# ── 그래프 검색 ──────────────────────────────────────────────────────────────
def graph_search(query: str, keywords: list, mode: str, depth: int, n: int) -> list:
    """NetworkX 그래프 탐색"""
    import sys
    sys.path.insert(0, str(BASE / "query"))
    from graph_search_v2 import find_nodes

    G    = get_graph()
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    results = []

    # 검색어 후보: 원문 + 추출 키워드
    search_terms = [query] + keywords
    matched_nodes = []
    seen_nids = set()

    for term in search_terms:
        for nid, ntype, label in find_nodes(G, term):
            if nid not in seen_nids:
                matched_nodes.append((nid, ntype, label))
                seen_nids.add(nid)

    if not matched_nodes:
        conn.close()
        return []

    # 탐색 모드
    visited = set()
    error_nids = []

    if mode == "traverse":
        from collections import deque
        SKIP = {"similar_error", "mentioned_in", "used_in"}
        for start_nid, _, _ in matched_nodes[:2]:
            q = deque([(start_nid, 0)])
            while q:
                nid, d = q.popleft()
                if nid in visited or d > depth: continue
                visited.add(nid)
                ntype = G.nodes[nid].get("type","")
                if ntype == "error":
                    error_nids.append(nid)
                for _, nbr, ed in G.out_edges(nid, data=True):
                    if ed.get("rel","") not in SKIP:
                        q.append((nbr, d+1))
                for src, _, ed in G.in_edges(nid, data=True):
                    if ed.get("rel","") not in SKIP:
                        q.append((src, d+1))
    else:
        for nid, ntype, _ in matched_nodes[:3]:
            if ntype == "error":
                error_nids.append(nid)
            for _, nbr, ed in G.out_edges(nid, data=True):
                if G.nodes[nbr].get("type") == "error":
                    error_nids.append(nbr)
            for src, _, ed in G.in_edges(nid, data=True):
                if G.nodes[src].get("type") == "error":
                    error_nids.append(src)

    # error_nids → DB에서 내용 조회
    seen_ids = set()
    try:
        for nid in error_nids[:n]:
            if nid in seen_ids: continue
            seen_ids.add(nid)
            db_id = int(nid.replace("error:", ""))
            row   = conn.execute(
                "SELECT error_msg, category, cause, solution, source_url FROM errors WHERE id=?", (db_id,)
            ).fetchone()
            if row:
                results.append({
                    "source": "graph", "type": "ERROR", "score": 0.80,
                    "title": row[0][:100], "category": row[1] or "",
                    "cause": row[2] or "", "solution": row[3] or "",
                    "url": row[4] or "", "code": ""
                })
    finally:
        conn.close()

    return results


# ── 결과 통합 ────────────────────────────────────────────────────────────────
def merge_results(all_results: list, n: int) -> list:
    """중복 제거 + score 가중 정렬 + 상위 n개 반환"""
    seen_titles = {}
    merged = []

    # source 가중치: vector > graph > keyword (동일 내용이면 벡터 우선)
    SOURCE_WEIGHT = {"vector": 1.0, "graph": 0.95, "keyword": 0.90}

    for r in all_results:
        key   = r["title"].lower()[:50]
        score = r["score"] * SOURCE_WEIGHT.get(r["source"], 1.0)

        if key in seen_titles:
            # 더 높은 score로 업데이트
            if score > seen_titles[key]["score"]:
                seen_titles[key] = {**r, "score": score}
        else:
            seen_titles[key] = {**r, "score": score}

    merged = sorted(seen_titles.values(), key=lambda x: x["score"], reverse=True)
    return merged[:n]


def execute(plan, query: str, intent: dict) -> list:
    """SearchPlan 실행 → 통합 결과"""
    keywords  = intent.get("keywords", [])
    all_items = []

    for method in plan.methods:
        if method == "keyword":
            items = keyword_search(query, plan.db_types, plan.n_results)
            # 키워드 검색 실패 시 핵심 키워드로 재시도
            if not items and keywords:
                for kw in keywords[:2]:
                    items = keyword_search(kw, plan.db_types, plan.n_results)
                    if items:
                        break
            all_items.extend(items)

        elif method == "vector":
            items = vector_search(query, keywords, plan.db_types, plan.n_results)
            all_items.extend(items)

        elif method == "graph":
            items = graph_search(query, keywords, plan.graph_mode, plan.graph_depth, plan.n_results)
            all_items.extend(items)

    return merge_results(all_items, plan.n_results)
