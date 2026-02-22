#!/usr/bin/env python3
"""
멀티링구얼 재임베딩 (한국어 + 영어 지원)
- 모델: paraphrase-multilingual-MiniLM-L12-v2
- 기존 단일언어 컬렉션을 대체
"""

import sqlite3, sys, time
from pathlib import Path

DB_PATH    = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge.db")
CHROMA_DIR = Path("/mnt/c/Users/user/projects/meep-kb/db/chroma")
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 32

# 한국어 보조 텍스트 매핑 (주요 개념)
KO_HINTS = {
    "adjoint":          "adjoint 기울기 역전파 최적화",
    "convergence":      "수렴 발산 불안정 NaN Inf 발산",
    "mpi":              "병렬 MPI 멀티코어 RAM 메모리",
    "install":          "설치 import 오류 버전",
    "geometry":         "구조 기하학 overlap 경계",
    "source":           "소스 mode 모드 EigenModeSource",
    "monitor":          "모니터 플럭스 DFT flux",
    "legume":           "legume GME 포토닉 결정 슬랩",
    "mpb":              "MPB ModeSolver 밴드구조",
    "cfwdm":            "모드 변환기 역다중화 PhC EFC",
}


class MultilingualEF:
    """sentence-transformers 기반 ChromaDB 커스텀 임베딩 함수"""
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        print(f"모델 로드: {MODEL_NAME} (첫 실행 시 ~470MB 다운로드)")
        self.model = SentenceTransformer(MODEL_NAME)
        print("✅ 모델 준비 완료")

    def name(self):
        return "multilingual-ef"

    def __call__(self, input):
        return self.model.encode(list(input), show_progress_bar=False).tolist()


def embed_collection(client, ef, name, rows, id_prefix):
    col = client.get_or_create_collection(
        name=name,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )
    existing = set(col.get(include=[])["ids"])
    new_rows  = [(r[0], r[1], r[2]) for r in rows if f"{id_prefix}{r[0]}" not in existing]

    if not new_rows:
        print(f"  [{name}] 전체 기수집, 스킵")
        return 0

    print(f"  [{name}] {len(new_rows)}건 처리 ({len(existing)}건 기수집)...")
    saved = 0
    for i in range(0, len(new_rows), BATCH_SIZE):
        batch     = new_rows[i:i + BATCH_SIZE]
        ids       = [f"{id_prefix}{r[0]}" for r in batch]
        documents = [r[1][:1000]          for r in batch]
        metadatas = [r[2]                 for r in batch]
        col.upsert(ids=ids, documents=documents, metadatas=metadatas)
        saved += len(batch)
        pct = saved * 100 // len(new_rows)
        sys.stdout.write(f"\r  [{name}] {saved}/{len(new_rows)} ({pct}%) ...")
        sys.stdout.flush()
    print(f"\r  [{name}] ✅ {saved}건 완료{' '*20}")
    return saved


def main():
    import chromadb
    t0     = time.time()
    conn   = sqlite3.connect(str(DB_PATH), timeout=30)
    ef     = MultilingualEF()
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # 기존 단일언어 컬렉션 삭제 후 재생성
    for cname in ["errors", "examples", "docs"]:
        try:
            client.delete_collection(cname)
            print(f"  기존 [{cname}] 컬렉션 삭제")
        except Exception:
            pass

    # ── errors ────────────────────────────────────────────────
    rows = conn.execute(
        "SELECT id, error_msg, cause, solution, category, source_url, source_type FROM errors"
    ).fetchall()
    data = []
    for r in rows:
        cat = r[4] or ""
        hint = KO_HINTS.get(cat, "")
        text = f"{r[1]} {r[2] or ''} {r[3] or ''} {hint}".strip()
        meta = {"category": cat, "source_url": r[5] or "",
                "source_type": r[6] or "", "has_solution": "1" if r[3] else "0",
                "error_msg": r[1][:200]}
        data.append((r[0], text, meta))
    embed_collection(client, ef, "errors", data, "err_")

    # ── examples ──────────────────────────────────────────────
    rows = conn.execute(
        "SELECT id, title, description, tags, source_repo, code FROM examples"
    ).fetchall()
    data = [
        (r[0],
         f"{r[1]} {r[2] or ''} {r[3] or ''} {(r[5] or '')[:300]}".strip(),
         {"title": r[1][:200], "tags": r[3] or "", "source_repo": r[4] or ""})
        for r in rows
    ]
    embed_collection(client, ef, "examples", data, "ex_")

    # ── docs ──────────────────────────────────────────────────
    rows = conn.execute(
        "SELECT id, section, content, url, simulator FROM docs LIMIT 2000"
    ).fetchall()
    data = [
        (r[0],
         f"{r[1]} {(r[2] or '')[:500]}".strip(),
         {"section": r[1][:200], "url": r[2] or "", "simulator": r[4] or ""})
        for r in rows
    ]
    embed_collection(client, ef, "docs", data, "doc_")

    conn.close()
    elapsed = time.time() - t0
    print(f"\n{'='*55}")
    print(f"✅ 멀티링구얼 임베딩 완료  ({elapsed:.0f}초)")
    for cname in ["errors", "examples", "docs"]:
        col = client.get_collection(cname, embedding_function=ef)
        print(f"  {cname:<10}: {col.count()}건")
    print("="*55)


if __name__ == "__main__":
    main()
