#!/usr/bin/env python3
"""
BGE-M3 임베딩으로 ChromaDB 전체 재구축
- 기존 컬렉션(384d) 삭제 후 새 컬렉션(1024d) 생성
- Dense retrieval 사용 (use_fp16=True, CPU 친화적)
- 백업: chroma_backup_pre_bgem3/
"""

import sqlite3
import shutil
import time
import sys
from pathlib import Path

DB_PATH    = Path("/app/db/knowledge.db")
CHROMA_DIR = Path("/app/db/chroma")
BACKUP_DIR = Path("/app/db/chroma_backup_pre_bgem3")
BATCH_SIZE = 16  # BGE-M3은 무거우므로 작게

def log(msg):
    print(msg, flush=True)

def backup_chroma():
    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR)
    shutil.copytree(CHROMA_DIR, BACKUP_DIR)
    log(f"[OK] ChromaDB backup -> {BACKUP_DIR}")

def load_model():
    from sentence_transformers import SentenceTransformer
    log("[...] Loading BAAI/bge-m3 via sentence-transformers (first run downloads ~570MB)...")
    model = SentenceTransformer('BAAI/bge-m3', device='cpu')
    log(f"[OK] Model loaded | dim={model.get_sentence_embedding_dimension()}")
    return model

def encode_batch(model, texts):
    return model.encode(texts, batch_size=BATCH_SIZE, normalize_embeddings=True).tolist()

def rebuild_collection(client, model, name, rows, id_prefix):
    """rows: list of (db_id, document_text, metadata_dict)"""
    # 기존 컬렉션 삭제 (차원 변경이므로 반드시 재생성)
    try:
        client.delete_collection(name)
        log(f"  Deleted old collection: {name}")
    except Exception:
        pass

    col = client.create_collection(
        name=name,
        metadata={"hnsw:space": "cosine", "embedding_model": "BAAI/bge-m3", "dim": 1024}
    )

    total = len(rows)
    saved = 0
    log(f"  Embedding {total} docs in batches of {BATCH_SIZE}...")

    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i+BATCH_SIZE]
        ids       = [f"{id_prefix}{r[0]}" for r in batch]
        documents = [r[1][:1000] for r in batch]
        metadatas = [r[2] for r in batch]
        embeddings = encode_batch(model, documents)

        col.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        saved += len(batch)
        pct = saved * 100 // total
        sys.stdout.write(f"\r  [{name}] {saved}/{total} ({pct}%)")
        sys.stdout.flush()

    print(f"\r  [{name}] Done: {saved} docs embedded" + " " * 20)
    return saved

def main():
    import chromadb

    log("=" * 60)
    log("BGE-M3 ChromaDB Rebuild")
    log("=" * 60)

    # 1. 백업
    backup_chroma()

    # 2. 모델 로드
    model = load_model()

    # 3. SQLite에서 데이터 읽기
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # errors: error_msg + cause + solution
    cur.execute("SELECT id, COALESCE(error_msg,'') || ' ' || COALESCE(cause,'') || ' ' || COALESCE(solution,'') FROM errors")
    errors_rows = [(r[0], r[1] or '', {"type": "error"}) for r in cur.fetchall()]

    # examples: title + description + code (truncated)
    cur.execute("SELECT id, COALESCE(title,'') || '. ' || COALESCE(description,'') || ' ' || SUBSTR(COALESCE(code,''),1,300) FROM examples")
    examples_rows = [(r[0], r[1] or '', {"type": "example"}) for r in cur.fetchall()]

    # docs: section + content
    cur.execute("SELECT id, COALESCE(section,'') || '. ' || COALESCE(content,'') FROM docs LIMIT 2000")
    docs_rows = [(r[0], r[1] or '', {"type": "doc"}) for r in cur.fetchall()]

    # patterns - description + use_case (영어로 번역 완료된 상태)
    cur.execute("SELECT id, pattern_name || '. ' || COALESCE(description,'') || ' ' || COALESCE(use_case,''), '{}' FROM patterns")
    patterns_rows = [(r[0], r[1] or '', {"type": "pattern"}) for r in cur.fetchall()]

    conn.close()

    log(f"\n[STAT] errors={len(errors_rows)}, examples={len(examples_rows)}, docs={len(docs_rows)}, patterns={len(patterns_rows)}")

    # 4. ChromaDB 재구축
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    t0 = time.time()

    log("\n[1/4] patterns (가장 중요, 먼저)")
    rebuild_collection(client, model, "patterns", patterns_rows, "pat_")

    log("\n[2/4] errors")
    rebuild_collection(client, model, "errors", errors_rows, "err_")

    log("\n[3/4] examples")
    rebuild_collection(client, model, "examples", examples_rows, "ex_")

    log("\n[4/4] docs")
    rebuild_collection(client, model, "docs", docs_rows, "doc_")

    elapsed = time.time() - t0
    log(f"\n[DONE] Total time: {elapsed/60:.1f} min")

    # 5. 검증
    log("\n[VERIFY] Collection counts:")
    for c in client.list_collections():
        log(f"  {c.name}: {c.count()} docs | metadata={c.metadata}")

if __name__ == "__main__":
    main()
