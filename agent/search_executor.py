#!/usr/bin/env python3
"""
Search Executor — SearchPlan 에 따라 실제 검색 수행, 결과 통합
"""

import sys, sqlite3, pickle
from pathlib import Path

BASE = Path("/app")
sys.path.insert(0, str(BASE / "query"))

_LOCAL_DB = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge.db")
DB_PATH    = BASE / "db/knowledge.db" if (BASE / "db/knowledge.db").exists() else _LOCAL_DB
CHROMA_DIR = BASE / "db/chroma"
GRAPH_PATH = BASE / "db/knowledge_graph_v2.pkl"
MODEL_NAME = "BAAI/bge-m3"   # ChromaDB 컬렉션과 동일한 1024-dim 모델 (수정: MiniLM 384-dim → bge-m3 1024-dim)

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

        if "patterns" in db_types or "all" in db_types:
            try:
                rows = conn.execute(
                    "SELECT id, pattern_name, description, code_snippet, use_case FROM patterns "
                    "WHERE pattern_name LIKE ? OR description LIKE ? OR use_case LIKE ? LIMIT ?",
                    ("%" + query + "%", "%" + query + "%", "%" + query + "%", n)
                ).fetchall()
                for r in rows:
                    results.append({
                        "source": "keyword", "type": "PATTERN",
                        "score": 0.88,
                        "title": r[1][:100], "category": r[4] or "",
                        "cause": r[2] or "", "solution": "",
                        "url": "", "code": (r[3] or "")[:500]
                    })
            except Exception:
                pass
    except Exception as e:
        pass
    finally:
        conn.close()

    return results


# ── sim_errors_unified 3분할 symptom 검색 ──────────────────────────────────────
# 수치 패턴 키워드
_NUMERICAL_KEYWORDS = ["t>", "nan", "ratio", "gradient", "t=", "r=", "flux", "%", "×", "배", "차이", "비율", "수치"]
# 행동 패턴 키워드
_BEHAVIORAL_KEYWORDS = ["수렴", "발산", "체커보드", "hanging", "diverge", "oscillat", "수렴실패", "응답없음", "중단", "왜곡", "오차"]

def sim_errors_v2_search(query: str, n: int) -> list:
    """sim_errors_unified 테이블에서 symptoms 3분할 컬럼을 활용한 검색.
    (구 sim_errors_v2_search — 이름 유지로 하위 호환성 보존)

    - 수치 패턴 키워드 포함 → symptom_numerical LIKE 검색
    - 행동 패턴 키워드 포함 → symptom_behavioral LIKE 검색
    - 나머지 / 공통      → error_message + symptom_error_pattern LIKE 검색
    - fix_worked=1 케이스에 score +0.1 보너스
    - origin_table 로 source 레이블 구분 (sim_v2 / sim_se)
    """
    results = []
    q_lower = query.lower()

    # 쿼리 패턴 분류
    is_numerical  = any(kw in q_lower for kw in _NUMERICAL_KEYWORDS)
    is_behavioral = any(kw in q_lower for kw in _BEHAVIORAL_KEYWORDS)

    # 검색에 사용할 LIKE 토큰: 공백 분리된 각 단어
    tokens = [t.strip() for t in query.split() if len(t.strip()) >= 2]
    if not tokens:
        tokens = [query]

    conn = sqlite3.connect(str(DB_PATH), timeout=30)

    seen_ids = set()

    def _fetch_rows(where_clause: str, params: tuple) -> list:
        sql = (
            "SELECT id, error_type, error_message, error_class, "
            "physics_cause, root_cause, fix_description, fixed_code, "
            "fix_worked, verification_criteria, diagnostic_snippet, "
            "symptom_numerical, symptom_behavioral, symptom_error_pattern, "
            "origin_table "
            f"FROM sim_errors_unified WHERE {where_clause} LIMIT ?"
        )
        try:
            return conn.execute(sql, params + (n * 3,)).fetchall()
        except Exception:
            return []

    try:
        row_buckets = []  # list of (rows, base_score)

        # 1) 수치 패턴 검색
        if is_numerical:
            for tok in tokens:
                rows = _fetch_rows("symptom_numerical LIKE ?", (f"%{tok}%",))
                if rows:
                    row_buckets.append((rows, 0.88))

        # 2) 행동 패턴 검색
        if is_behavioral:
            for tok in tokens:
                rows = _fetch_rows("symptom_behavioral LIKE ?", (f"%{tok}%",))
                if rows:
                    row_buckets.append((rows, 0.88))

        # 3) 에러 메시지 / symptom_error_pattern 검색 (항상 수행)
        # 3a) 전체 쿼리 문자열로 정확 매칭 (높은 스코어)
        rows = _fetch_rows(
            "error_message LIKE ? OR symptom_error_pattern LIKE ?",
            (f"%{query[:120]}%", f"%{query[:120]}%")
        )
        if rows:
            row_buckets.append((rows, 0.93))
        # 3b) 토큰별 매칭 (일반 스코어)
        for tok in tokens:
            rows = _fetch_rows(
                "error_message LIKE ? OR symptom_error_pattern LIKE ?",
                (f"%{tok}%", f"%{tok}%")
            )
            if rows:
                row_buckets.append((rows, 0.85))

        # 4) 결과가 없으면 전체 텍스트 fallback (physics_cause, root_cause, fix_description)
        if not row_buckets:
            for tok in tokens:
                rows = _fetch_rows(
                    "physics_cause LIKE ? OR root_cause LIKE ? OR fix_description LIKE ?",
                    (f"%{tok}%", f"%{tok}%", f"%{tok}%")
                )
                if rows:
                    row_buckets.append((rows, 0.75))

        # 수집된 row bucket → 결과 dict 변환
        for rows, base_score in row_buckets:
            for r in rows:
                row_id = r[0]
                if row_id in seen_ids:
                    continue
                seen_ids.add(row_id)

                score = base_score
                # fix_worked=1 이면 +0.1 보너스
                if r[8] == 1:
                    score = min(score + 0.1, 1.0)

                # origin 별 source 레이블
                origin = r[14] or "sim_errors_v2"
                src_label = "sim_v2" if origin == "sim_errors_v2" else "sim_se"

                # title: error_type 없으면 error_message 앞부분
                title = (r[1] or r[2] or "Unknown Error")[:100]

                # cause: physics_cause 우선, 없으면 root_cause
                cause_text = r[4] or r[5] or ""

                results.append({
                    "source": src_label,
                    "type":   "SIM_ERROR",
                    "score":  round(score, 3),
                    "title":  title,
                    "category": r[3] or "",
                    "cause":    cause_text[:300],
                    "solution": (r[6] or "")[:300],
                    "code":     (r[7] or "")[:500],
                    "verification_criteria": r[9] or "",
                    "diagnostic_snippet":   (r[10] or "")[:300],
                })

    finally:
        conn.close()

    # 점수 내림차순 → 상위 n개
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:n]



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
                    if score < 0.25: continue
                    try:
                        db_id = int(doc_id.replace("err_", "").split("_")[0])
                    except (ValueError, IndexError):
                        continue
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
                    if score < 0.25: continue
                    try:
                        db_id = int(doc_id.replace("ex_", "").split("_")[0])
                    except (ValueError, IndexError):
                        continue
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
                    if score < 0.25: continue
                    try:
                        db_id = int(doc_id.replace("doc_", "").split("_")[0])
                    except (ValueError, IndexError):
                        continue
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

        if "patterns" in db_types or "all" in db_types:
            res = qcol("patterns", "pattern_", n)
            if res and res["ids"][0]:
                for doc_id, dist in zip(res["ids"][0], res["distances"][0]):
                    if doc_id in seen_ids: continue
                    seen_ids.add(doc_id)
                    score = max(0.0, 1.0 - dist * 0.5)  # L2 → cosine 유사 방식으로 정규화
                    try:
                        import re as _re
                        m = _re.search(r"(\d+)$", doc_id)
                        if not m: continue
                        db_id = int(m.group(1))
                    except:
                        continue
                    row = conn.execute(
                        "SELECT pattern_name, description, code_snippet, use_case FROM patterns WHERE id=?", (db_id,)
                    ).fetchone()
                    if row:
                        results.append({
                            "source": "vector", "type": "PATTERN", "score": round(score, 3),
                            "title": row[0][:100], "category": row[3] or "",
                            "cause": row[1] or "", "solution": "",
                            "url": "", "code": (row[2] or "")[:500]
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
                    "source": "graph", "type": "ERROR", "score": 0.55,
                    "title": row[0][:100], "category": row[1] or "",
                    "cause": row[2] or "", "solution": row[3] or "",
                    "url": row[4] or "", "code": ""
                })
    finally:
        conn.close()

    return results


# ── 파이프라인 패턴 검색 ───────────────────────────────────────────────────────
# Stage 5-1~5-5 stage 태그 매핑 (pipeline_stage_idx → use_case 태그)
_STAGE_TAG_MAP = {
    1: "forward_sim",
    2: "adjoint_sim",
    3: "gradient",
    4: "beta_scheduling",
    5: "filter",
}

def pipeline_search(query: str, pipeline_category: str, pipeline_stage_idx: int, n: int) -> list:
    """
    PIPELINE 타입 패턴 우선 검색.
    - pipeline_category 기반으로 패턴 필터링
    - inv_loop의 경우 stage_idx ±1 인접 단계도 포함
    - 결과는 score 0.95 (현재 단계) / 0.80 (인접 단계) 부여
    """
    conn    = sqlite3.connect(str(DB_PATH), timeout=30)
    results = []

    try:
        # 검색 대상 use_case 키워드 목록 수집
        # inv_loop + stage_idx 있으면 stage 레벨 검색 (카테고리 전체 X)
        if pipeline_category == "inv_loop" and pipeline_stage_idx > 0:
            # 현재 단계 stage 태그
            cur_tag = _STAGE_TAG_MAP.get(pipeline_stage_idx, "")
            target_tags   = []
            target_scores  = {}
            if cur_tag:
                cur_stage_tag = f"pipeline_stage:{cur_tag}"
                target_tags.append(cur_stage_tag)
                target_scores[cur_stage_tag] = 0.97  # 현재 단계 최우선

            # 인접 단계 (±1)
            for adj_idx in [pipeline_stage_idx - 1, pipeline_stage_idx + 1]:
                adj_tag = _STAGE_TAG_MAP.get(adj_idx, "")
                if adj_tag:
                    adj_stage_tag = f"pipeline_stage:{adj_tag}"
                    target_tags.append(adj_stage_tag)
                    target_scores[adj_stage_tag] = 0.78

        else:
            # 카테고리 레벨 검색 (inv_loop 외 카테고리 또는 stage 없을 때)
            target_tags   = [f"pipeline_category:{pipeline_category}"]
            target_scores = {f"pipeline_category:{pipeline_category}": 0.95}

        # patterns 테이블에서 tag 기반 LIKE 검색
        seen_ids = set()
        for tag in target_tags:
            rows = conn.execute(
                "SELECT id, pattern_name, description, code_snippet, use_case "
                "FROM patterns WHERE use_case LIKE ? LIMIT ?",
                (f"%{tag}%", n)
            ).fetchall()
            for r in rows:
                if r[0] in seen_ids:
                    continue
                seen_ids.add(r[0])
                score = target_scores.get(tag, 0.80)
                results.append({
                    "source": "pipeline",
                    "type":   "PATTERN",
                    "score":  score,
                    "title":  r[1][:100],
                    "category": pipeline_category,
                    "cause":    (r[2] or "")[:300],
                    "solution": "",
                    "url":  "",
                    "code": (r[3] or "")[:500],
                })

        # 위 태그 검색으로 결과 없으면 텍스트 fallback
        if not results:
            rows = conn.execute(
                "SELECT id, pattern_name, description, code_snippet, use_case "
                "FROM patterns WHERE pattern_name LIKE 'pipeline_%' LIMIT ?",
                (n,)
            ).fetchall()
            for r in rows:
                if r[0] in seen_ids:
                    continue
                seen_ids.add(r[0])
                results.append({
                    "source": "pipeline",
                    "type":   "PATTERN",
                    "score":  0.70,
                    "title":  r[1][:100],
                    "category": "",
                    "cause":    (r[2] or "")[:300],
                    "solution": "",
                    "url":  "",
                    "code": (r[3] or "")[:500],
                })

    except Exception as e:
        pass
    finally:
        conn.close()

    # 점수 내림차순 정렬
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:n]


# ── 피드백 부스팅 캐시 ────────────────────────────────────────────────────────
_boost_cache: dict = {}          # {url: boost_value}
_boost_cache_dirty: bool = True  # True면 DB에서 재로드

BOOST_FACTOR = 0.12   # 최대 12% 점수 상승
FEEDBACK_DB  = None   # main.py startup에서 주입


def _load_boost_cache():
    """feedback DB에서 URL별 부스팅 값 계산"""
    global _boost_cache, _boost_cache_dirty
    if not _boost_cache_dirty:
        return

    if FEEDBACK_DB is None:
        _boost_cache_dirty = False
        return

    try:
        import sqlite3
        conn = sqlite3.connect(str(FEEDBACK_DB), timeout=5)
        rows = conn.execute("""
            SELECT result_url,
                   SUM(helpful)  AS helpful_count,
                   COUNT(*)      AS total_count
            FROM feedback
            WHERE result_url != '' AND result_index > 0
            GROUP BY result_url
        """).fetchall()
        conn.close()

        if not rows:
            _boost_cache = {}
            _boost_cache_dirty = False
            return

        max_helpful = max(r[1] for r in rows) or 1
        new_cache = {}
        for url, helpful, total in rows:
            # 긍정 비율 * BOOST_FACTOR (많이 도움된 자료일수록 높은 부스팅)
            ratio = helpful / max_helpful
            new_cache[url] = round(ratio * BOOST_FACTOR, 4)

        _boost_cache = new_cache
        _boost_cache_dirty = False
    except Exception:
        _boost_cache_dirty = False


# ── 결과 통합 ────────────────────────────────────────────────────────────────
def merge_results(all_results: list, n: int) -> list:
    """중복 제거 + score 가중 정렬 + 피드백 부스팅 + 상위 n개 반환"""
    seen_titles = {}

    # source 가중치: vector > keyword > graph
    # (그래프는 고정점수 0.55 × 0.85 = 0.47 → 벡터 결과보다 낮게)
    SOURCE_WEIGHT = {"vector": 1.0, "keyword": 0.90, "graph": 0.85, "pattern": 1.1}

    # 피드백 부스팅 캐시 로드
    _load_boost_cache()

    for r in all_results:
        key   = r["title"].lower()[:50]
        score = r["score"] * SOURCE_WEIGHT.get(r["source"], 1.0)

        # 피드백 부스팅 적용
        url = r.get("url", "")
        if url and url in _boost_cache:
            score = min(score + _boost_cache[url], 1.0)
            r = {**r, "feedback_boosted": True}

        if key in seen_titles:
            if score > seen_titles[key]["score"]:
                seen_titles[key] = {**r, "score": round(score, 3)}
        else:
            seen_titles[key] = {**r, "score": round(score, 3)}

    merged = sorted(seen_titles.values(), key=lambda x: x["score"], reverse=True)
    return merged[:n]


def execute(plan, query: str, intent: dict) -> list:
    """SearchPlan 실행 → 통합 결과"""
    keywords  = intent.get("keywords", [])
    all_items = []

    for method in plan.methods:
        if method == "pipeline":
            # PIPELINE DB 우선 검색 (인접 단계 ±1 포함)
            pipeline_cat = getattr(plan, "pipeline_category", "") or intent.get("pipeline_category", "")
            pipeline_idx = getattr(plan, "pipeline_stage_idx", 0) or int(intent.get("pipeline_stage_idx", 0))
            items = pipeline_search(query, pipeline_cat, pipeline_idx, plan.n_results)
            all_items.extend(items)

        elif method == "keyword":
            items = keyword_search(query, plan.db_types, plan.n_results)
            # 키워드 검색 실패 시 핵심 키워드로 재시도
            if not items and keywords:
                for kw in keywords[:2]:
                    items = keyword_search(kw, plan.db_types, plan.n_results)
                    if items:
                        break
            all_items.extend(items)
            # sim_errors_v2 symptom 3분할 검색 병합
            all_items.extend(sim_errors_v2_search(query, plan.n_results))

        elif method == "vector":
            items = vector_search(query, keywords, plan.db_types, plan.n_results)
            all_items.extend(items)
            # sim_errors_v2 symptom 3분할 검색 병합
            all_items.extend(sim_errors_v2_search(query, plan.n_results))

        elif method == "graph":
            items = graph_search(query, keywords, plan.graph_mode, plan.graph_depth, plan.n_results)
            all_items.extend(items)

    return merge_results(all_items, plan.n_results)
