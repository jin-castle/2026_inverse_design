#!/usr/bin/env python3
"""
Step 2: SQLite → ChromaDB 임베딩 적재
- ChromaDB 내장 DefaultEmbeddingFunction (all-MiniLM-L6-v2 ONNX)
- 별도 sentence-transformers 불필요, 충돌 없음
"""

import sqlite3, sys, time
from pathlib import Path

DB_PATH    = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge.db")
CHROMA_DIR = Path("/mnt/c/Users/user/projects/meep-kb/db/chroma")
BATCH_SIZE = 32

def get_client_and_ef():
    import chromadb
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    ef     = DefaultEmbeddingFunction()   # all-MiniLM-L6-v2 ONNX, 첫 실행 시 다운로드
    return client, ef

def embed_collection(client, ef, name, rows, id_prefix):
    """rows: list of (db_id, embed_text, metadata_dict)"""
    col = client.get_or_create_collection(
        name=name,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )
    existing  = set(col.get(include=[])["ids"])
    new_rows  = [(r[0], r[1], r[2]) for r in rows if f"{id_prefix}{r[0]}" not in existing]

    if not new_rows:
        print(f"  [{name}] 전체 기수집, 스킵")
        return 0

    print(f"  [{name}] {len(new_rows)}건 적재 ({len(existing)}건 기수집)...")
    saved = 0

    for i in range(0, len(new_rows), BATCH_SIZE):
        batch     = new_rows[i:i + BATCH_SIZE]
        ids       = [f"{id_prefix}{r[0]}" for r in batch]
        documents = [r[1][:1000] for r in batch]
        metadatas = [r[2]        for r in batch]

        col.upsert(ids=ids, documents=documents, metadatas=metadatas)
        saved += len(batch)
        pct = saved * 100 // len(new_rows)
        sys.stdout.write(f"\r  [{name}] {saved}/{len(new_rows)} ({pct}%) ...")
        sys.stdout.flush()

    print(f"\r  [{name}] ✅ {saved}건 완료{' '*20}")
    return saved

def main():
    t0     = time.time()
    conn   = sqlite3.connect(str(DB_PATH), timeout=30)
    client, ef = get_client_and_ef()

    print("모델 로드 중 (첫 실행 시 ~90MB 다운로드)...")
    # 모델 warm-up
    _ = ef(["warmup"])
    print("✅ 모델 준비 완료\n")

    # ── errors ────────────────────────────────────────────────
    rows = conn.execute(
        "SELECT id, error_msg, cause, solution, category, source_url, source_type FROM errors"
    ).fetchall()
    data = [
        (r[0],
         f"{r[1]} {r[2] or ''} {r[3] or ''}".strip()[:1000],
         {"category": r[4] or "", "source_url": r[5] or "",
          "source_type": r[6] or "", "has_solution": "1" if r[3] else "0",
          "error_msg": r[1][:200]})
        for r in rows
    ]
    embed_collection(client, ef, "errors", data, "err_")

    # ── examples ──────────────────────────────────────────────
    rows = conn.execute(
        "SELECT id, title, description, tags, source_repo, code FROM examples"
    ).fetchall()
    data = [
        (r[0],
         f"{r[1]} {r[2] or ''} {r[3] or ''} {(r[5] or '')[:300]}".strip()[:1000],
         {"title": r[1][:200], "tags": r[3] or "", "source_repo": r[4] or ""})
        for r in rows
    ]
    embed_collection(client, ef, "examples", data, "ex_")

    # ── docs (상위 2000건) ─────────────────────────────────────
    rows = conn.execute(
        "SELECT id, section, content, url, simulator FROM docs LIMIT 2000"
    ).fetchall()
    data = [
        (r[0],
         f"{r[1]} {(r[2] or '')[:500]}".strip()[:1000],
         {"section": r[1][:200], "url": r[2] or "", "simulator": r[4] or ""})
        for r in rows
    ]
    embed_collection(client, ef, "docs", data, "doc_")

    conn.close()
    elapsed = time.time() - t0
    print(f"\n{'='*55}")
    print(f"✅ 임베딩 완료  ({elapsed:.0f}초)")
    for cname in ["errors", "examples", "docs"]:
        print(f"  {cname:<10}: {client.get_collection(cname, embedding_function=ef).count()}건")
    print("="*55)

if __name__ == "__main__":
    main()
