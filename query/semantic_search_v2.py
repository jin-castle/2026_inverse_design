#!/usr/bin/env python3
"""
MEEP-KB 시맨틱 검색 v2 (한국어 쿼리 확장 + 저유사도 경고 + 버그 수정)

개선 사항 (from review_20260222.md):
  - augment_query(): 한국어 키워드 → 영어 기술 용어 자동 확장
  - 유사도 50% 미만 시 ⚠️ 경고 표시
  - 중복 결과 필터링 (동일 db_id 제거)
  - DB 연결 안전하게 close
  - 미사용 파라미터 제거

사용법:
  python query/semantic_search_v2.py "시뮬레이션이 발산해"
  python query/semantic_search_v2.py "모드 소스 설정 방법" --type docs
  python query/semantic_search_v2.py "adjoint 최적화 기울기" --type examples
  python query/semantic_search_v2.py "EigenModeSource convergence" --type errors --n 5
"""

import argparse, sqlite3
from pathlib import Path

DB_PATH    = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge.db")
CHROMA_DIR = Path("/mnt/c/Users/user/projects/meep-kb/db/chroma")
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
LOW_SCORE_THRESHOLD = 0.50   # 이 미만이면 ⚠️ 경고

# ── 한국어 쿼리 확장 테이블 ──────────────────────────────────────────────────
KO_QUERY_MAP = {
    # 시뮬레이션 상태
    "발산":  "diverge unstable NaN Inf fields blow up",
    "수렴":  "convergence Courant resolution stability",
    "불안정": "unstable diverge NaN",
    # 광학/MEEP 개념
    "소스":  "source EigenModeSource GaussianSource ContinuousSource",
    "모드":  "mode eigenmode EigenModeSource waveguide guided",
    "플럭스": "flux FluxRegion add_flux DFT monitor",
    "구조":  "geometry Block Cylinder Prism material",
    "경계":  "PML absorbing boundary perfectly matched",
    "슬랩":  "slab waveguide photonic crystal layer",
    "도파관": "waveguide mode source transmission",
    # 최적화/adjoint
    "최적화": "optimization adjoint inverse design topology",
    "기울기": "gradient adjoint sensitivity backpropagation",
    "역설계": "inverse design adjoint optimization topology",
    # 실행 환경
    "병렬":  "parallel MPI mpirun multicore",
    "설치":  "install conda pip import error",
    "오류":  "error exception RuntimeError",
    # 물리
    "주기":  "periodic lattice photonic crystal unit cell",
    "밴드":  "band structure dispersion MPB",
    "포토닉 결정": "photonic crystal PhC lattice bandgap",
    "모드 변환기": "mode converter mode multiplexer",
}

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


def augment_query(query: str) -> str:
    """한국어 키워드 포함 시 영어 기술 용어를 자동으로 추가"""
    additions = []
    for ko, en in KO_QUERY_MAP.items():
        if ko in query:
            additions.append(en)
    if additions:
        augmented = f"{query} {' '.join(additions)}"
        return augmented
    return query


def qcol(client, cname, query_vec, n_res):
    """ChromaDB 컬렉션 쿼리 (EF 없이 직접 벡터 사용)"""
    try:
        col = client.get_collection(cname)
        res = col.query(
            query_embeddings=query_vec,
            n_results=min(n_res, col.count()),
            include=["distances", "metadatas"]
        )
        return res
    except Exception as e:
        return None


def semantic_search(query: str, kind: str = "all", n: int = 5, verbose: bool = False):
    if not CHROMA_DIR.exists():
        print("❌ ChromaDB 없음. `python embeddings/embed_multilingual.py` 먼저 실행하세요.")
        return

    model  = get_model()
    client = get_client()

    # 한국어 쿼리 확장
    augmented = augment_query(query)
    if verbose and augmented != query:
        print(f"🔤 쿼리 확장: \"{query}\" → \"{augmented[:80]}...\"")

    query_vec = model.encode([augmented]).tolist()

    conn    = sqlite3.connect(str(DB_PATH), timeout=30)
    results = []
    seen_ids = set()   # 중복 결과 제거용

    try:
        if kind in ("all", "errors"):
            res = qcol(client, "errors", query_vec, n)
            if res and res["ids"][0]:
                for doc_id, dist in zip(res["ids"][0], res["distances"][0]):
                    if doc_id in seen_ids:
                        continue
                    seen_ids.add(doc_id)
                    db_id = int(doc_id.replace("err_", ""))
                    row   = conn.execute(
                        "SELECT error_msg, category, cause, solution, source_url FROM errors WHERE id=?", (db_id,)
                    ).fetchone()
                    if row:
                        results.append(("ERROR", 1 - dist, row))

        if kind in ("all", "examples"):
            res = qcol(client, "examples", query_vec, n)
            if res and res["ids"][0]:
                for doc_id, dist in zip(res["ids"][0], res["distances"][0]):
                    if doc_id in seen_ids:
                        continue
                    seen_ids.add(doc_id)
                    db_id = int(doc_id.replace("ex_", ""))
                    row   = conn.execute(
                        "SELECT title, description, tags, code, source_repo FROM examples WHERE id=?", (db_id,)
                    ).fetchone()
                    if row:
                        results.append(("EXAMPLE", 1 - dist, row))

        if kind in ("all", "docs"):
            res = qcol(client, "docs", query_vec, n)
            if res and res["ids"][0]:
                seen_content = set()   # docs 중복 콘텐츠 제거
                for doc_id, dist in zip(res["ids"][0], res["distances"][0]):
                    if doc_id in seen_ids:
                        continue
                    seen_ids.add(doc_id)
                    db_id = int(doc_id.replace("doc_", ""))
                    row   = conn.execute(
                        "SELECT section, content, url, simulator FROM docs WHERE id=?", (db_id,)
                    ).fetchone()
                    if row:
                        # 동일 section+url 중복 제거
                        dedup_key = f"{row[0]}|{row[2]}"
                        if dedup_key in seen_content:
                            continue
                        seen_content.add(dedup_key)
                        results.append(("DOC", 1 - dist, row))
    finally:
        conn.close()

    results.sort(key=lambda x: x[1], reverse=True)

    print(f"\n🔍 시맨틱 검색 v2: \"{query}\"")
    if augmented != query:
        print(f"   (쿼리 확장 적용됨)")
    print(f"상위 {min(n, len(results))}건\n{'='*60}")

    for rtype, score, data in results[:n]:
        bar  = "█" * int(score * 10) + "░" * (10 - int(score * 10))
        pct  = int(score * 100)
        warn = " ⚠️ 낮은 유사도" if score < LOW_SCORE_THRESHOLD else ""

        if rtype == "ERROR":
            msg, cat, cause, sol, url = data
            print(f"\n[{rtype}] [{cat}] 유사도 {pct}%{warn}  {bar}")
            print(f"  에러: {msg[:100]}")
            if cause: print(f"  원인: {(cause or '')[:150]}")
            if sol:   print(f"  ✅ 해결: {sol[:200]}")
            if url:   print(f"  🔗 {url}")

        elif rtype == "EXAMPLE":
            title, desc, tags, code, repo = data
            print(f"\n[{rtype}] 유사도 {pct}%{warn}  {bar}")
            print(f"  {title[:80]}  [{repo}]")
            if code:
                snippet = (code or "")[:250].strip().replace("\n", "\n  ")
                print(f"  ```python\n  {snippet}\n  ```")

        elif rtype == "DOC":
            section, content, url, sim = data
            print(f"\n[{rtype}] [{sim}] 유사도 {pct}%{warn}  {bar}")
            print(f"  {section}")
            if content: print(f"  {(content or '')[:180].strip()}...")
            if url:     print(f"  🔗 {url}")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MEEP-KB 시맨틱 검색 v2 (한국어/영어 + 쿼리 확장)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python query/semantic_search_v2.py "시뮬레이션이 발산해"
  python query/semantic_search_v2.py "모드 소스 설정" --type docs --n 5
  python query/semantic_search_v2.py "adjoint 최적화" --type examples -v
        """
    )
    parser.add_argument("query", help="자연어 검색어 (한국어/영어 모두 가능)")
    parser.add_argument("--type", choices=["all","errors","examples","docs"], default="all")
    parser.add_argument("--n",    type=int, default=5)
    parser.add_argument("-v", "--verbose", action="store_true", help="쿼리 확장 내용 출력")
    args = parser.parse_args()
    semantic_search(args.query, args.type, args.n, args.verbose)
