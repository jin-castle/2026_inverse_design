#!/usr/bin/env python3
"""
MEEP-KB 검색 CLI
사용법: python search.py "검색어"
       python search.py "검색어" --type errors
       python search.py "검색어" --type examples --limit 5
"""

import sqlite3, sys, argparse
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"

def search(query: str, kind: str = "all", limit: int = 5):
    if not DB_PATH.exists():
        print("❌ DB 없음. `python crawlers/01_db_setup.py` 먼저 실행하세요.")
        return

    conn = sqlite3.connect(DB_PATH)
    results = []

    if kind in ("all", "errors"):
        rows = conn.execute("""
            SELECT e.error_msg, e.category, e.cause, e.solution, e.source_url
            FROM errors_fts f
            JOIN errors e ON e.id = f.rowid
            WHERE errors_fts MATCH ?
            LIMIT ?
        """, (query, limit)).fetchall()
        for r in rows:
            results.append(("ERROR", r))

    if kind in ("all", "examples"):
        rows = conn.execute("""
            SELECT e.title, e.description, e.tags, e.code, e.source_repo
            FROM examples_fts f
            JOIN examples e ON e.id = f.rowid
            WHERE examples_fts MATCH ?
            LIMIT ?
        """, (query, limit)).fetchall()
        for r in rows:
            results.append(("EXAMPLE", r))

    if kind in ("all", "docs"):
        rows = conn.execute("""
            SELECT d.section, d.content, d.url, d.simulator
            FROM docs_fts f
            JOIN docs d ON d.id = f.rowid
            WHERE docs_fts MATCH ?
            LIMIT ?
        """, (query, limit)).fetchall()
        for r in rows:
            results.append(("DOC", r))

    conn.close()

    if not results:
        # FTS 실패 시 LIKE fallback
        conn = sqlite3.connect(DB_PATH)
        like = f"%{query}%"
        rows = conn.execute(
            "SELECT error_msg, category, cause, solution, source_url FROM errors "
            "WHERE error_msg LIKE ? OR solution LIKE ? LIMIT ?",
            (like, like, limit)
        ).fetchall()
        for r in rows:
            results.append(("ERROR", r))
        conn.close()

    if not results:
        print(f"🔍 '{query}' 결과 없음.")
        return

    print(f"\n🔍 '{query}' 검색 결과 {len(results)}건\n{'='*60}")
    for rtype, data in results:
        if rtype == "ERROR":
            msg, cat, cause, sol, url = data
            print(f"\n[{rtype}] [{cat or '?'}] {msg[:100]}")
            if cause: print(f"  원인: {cause[:150]}")
            if sol:   print(f"  ✅ 해결: {sol[:200]}")
            if url:   print(f"  🔗 {url}")
        elif rtype == "EXAMPLE":
            title, desc, tags, code, repo = data
            print(f"\n[{rtype}] {title[:80]}")
            print(f"  Tags: {tags} | Repo: {repo}")
            if code:
                snippet = code[:300].replace('\n', '\n  ')
                print(f"  ```python\n  {snippet}\n  ```")
        elif rtype == "DOC":
            section, content, url, sim = data
            print(f"\n[{rtype}] [{sim}] {section}")
            if content: print(f"  {content[:200].strip()}...")
            if url: print(f"  🔗 {url}")

    print(f"\n{'='*60}")
    n_err = sqlite3.connect(DB_PATH).execute("SELECT COUNT(*) FROM errors").fetchone()[0]
    n_ex  = sqlite3.connect(DB_PATH).execute("SELECT COUNT(*) FROM examples").fetchone()[0]
    print(f"DB 현황: errors={n_err}, examples={n_ex}")

def stats():
    conn = sqlite3.connect(DB_PATH)
    print("\n📊 MEEP-KB 통계")
    print("="*40)
    for table in ["errors", "examples", "docs", "patterns"]:
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<12}: {n:>6}건")

    print("\n에러 카테고리별:")
    rows = conn.execute(
        "SELECT category, COUNT(*) as n FROM errors GROUP BY category ORDER BY n DESC"
    ).fetchall()
    for cat, n in rows:
        print(f"  {cat or '?':<15}: {n:>5}건")

    print("\n코드 출처별:")
    rows = conn.execute(
        "SELECT source_repo, COUNT(*) as n FROM examples GROUP BY source_repo ORDER BY n DESC LIMIT 10"
    ).fetchall()
    for repo, n in rows:
        print(f"  {repo:<35}: {n:>4}건")
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MEEP Knowledge Base 검색")
    parser.add_argument("query", nargs="?", help="검색어")
    parser.add_argument("--type", choices=["all","errors","examples","docs"], default="all")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--stats", action="store_true", help="DB 통계 출력")
    parser.add_argument("--semantic", action="store_true", help="벡터 시맨틱 검색 사용")
    args = parser.parse_args()

    if args.stats:
        stats()
    elif args.query and args.semantic:
        import sys, os
        sys.path.insert(0, os.path.dirname(__file__))
        from semantic_search_v2 import semantic_search   # v2: 한국어 쿼리 확장 포함
        semantic_search(args.query, args.type, args.limit, verbose=True)
    elif args.query:
        search(args.query, args.type, args.limit)
    else:
        parser.print_help()
