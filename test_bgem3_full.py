#!/usr/bin/env python3
"""
BGE-M3 교체 후 종합 검증 테스트

1. 임베딩 모델 확인 (dim=1024 여부)
2. ChromaDB 컬렉션 메타데이터 확인
3. 검색 품질 테스트 (10개 쿼리)
4. 응답 속도 측정
5. API 엔드포인트 실전 테스트
"""

import sqlite3, time
from pathlib import Path

DB_PATH    = Path("/app/db/knowledge.db")
CHROMA_DIR = Path("/app/db/chroma")

def hr(title=""):
    print(f"\n{'='*60}")
    if title:
        print(f"  {title}")
        print(f"{'='*60}")

# ── 1. 임베딩 모델 확인 ─────────────────────────────────────
hr("1. 임베딩 모델 확인")
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("BAAI/bge-m3", device="cpu")
dim = model.get_sentence_embedding_dimension()
print(f"  Model   : BAAI/bge-m3")
print(f"  Dim     : {dim}  ({'OK' if dim == 1024 else 'FAIL - expected 1024'})")

# ── 2. ChromaDB 컬렉션 메타데이터 ──────────────────────────
hr("2. ChromaDB 컬렉션 현황")
import chromadb
client = chromadb.PersistentClient(path=str(CHROMA_DIR))
for col in client.list_collections():
    meta = col.metadata or {}
    em   = meta.get("embedding_model", "unknown")
    d    = meta.get("dim", "?")
    ok   = "OK" if em == "BAAI/bge-m3" and d == 1024 else "WARN"
    print(f"  [{ok}] {col.name:<12} count={col.count():4d}  model={em}  dim={d}")

# ── 3. 검색 품질 테스트 ─────────────────────────────────────
hr("3. 검색 품질 테스트 (10개 쿼리)")

test_cases = [
    # (쿼리, 기대 패턴명, 컬렉션)
    ("adjoint gradient NaN problem",         "adjoint_solver_complete",    "patterns"),
    ("3D SOI slab TE mode eigenmode source", "eigenmode_source_kpoints",   "patterns"),
    ("beta schedule binarization adjoint",   "get_beta_schedule",          "patterns"),
    ("MPI parallel mpirun MEEP",             "mpi_parallel_simulation",    "patterns"),
    ("PhC bandgap waveguide band structure", "phc_holey_waveguide_bands",  "patterns"),
    ("SiO2 substrate PML extend",            "sio2_substrate_pml_geometry","patterns"),
    ("adjoint waveguide bend 90 degree",     "adjoint_waveguide_bend_optimization", "patterns"),
    ("DFT field monitor 3D SOI",             "dft_monitor_3d_soi_setup",   "patterns"),
    ("mode converter TE0 TE1 adjoint",       "adjoint_mode_converter_opt", "patterns"),
    ("plot convergence FOM optimization",    "plot_convergence_4panel",    "patterns"),
]

passed = 0
results_table = []

for query, expected, col_name in test_cases:
    t0  = time.time()
    vec = model.encode(query, normalize_embeddings=True).tolist()
    col = client.get_collection(col_name)
    res = col.query(query_embeddings=[vec], n_results=3)
    elapsed = (time.time() - t0) * 1000

    top_ids  = res["ids"][0]
    top_dist = res["distances"][0]
    scores   = [1 - d for d in top_dist]

    # ID에서 패턴명 추출 → DB 조회
    conn = sqlite3.connect(str(DB_PATH))
    top_names = []
    for doc_id in top_ids:
        raw_id = doc_id.replace("pat_", "")
        row = conn.execute("SELECT pattern_name FROM patterns WHERE id=?", (raw_id,)).fetchone()
        top_names.append(row[0] if row else doc_id)
    conn.close()

    hit  = expected in top_names
    rank = top_names.index(expected) + 1 if hit else 0
    score = scores[rank - 1] if hit else scores[0]

    if hit and rank == 1:
        status = "PASS"
        passed += 1
    elif hit:
        status = f"PASS@{rank}"
        passed += 1
    else:
        status = "FAIL"

    results_table.append((status, score, elapsed, query[:40], expected, top_names[0]))

# 출력
print(f"  {'STATUS':<8} {'SCORE':>6}  {'MS':>5}  {'QUERY':<42} {'TOP-1 HIT'}")
print(f"  {'-'*8} {'-'*6}  {'-'*5}  {'-'*42} {'-'*30}")
for status, score, ms, q, expected, top1 in results_table:
    mark = "OK" if "PASS" in status else "XX"
    print(f"  {status:<8} {score:.3f}  {ms:>5.0f}ms  {q:<42} {top1}")

total = len(test_cases)
print(f"\n  결과: {passed}/{total} 통과  ({passed*100//total}%)")

# ── 4. 응답 속도 평균 ──────────────────────────────────────
hr("4. 응답 속도")
times = [r[2] for r in results_table]
print(f"  평균: {sum(times)/len(times):.0f}ms")
print(f"  최소: {min(times):.0f}ms")
print(f"  최대: {max(times):.0f}ms")

# ── 5. 구버전 vs BGE-M3 간단 비교 ───────────────────────────
hr("5. 구버전 MiniLM vs BGE-M3 유사도 비교")
old_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2", device="cpu")
compare_queries = [
    ("beta schedule binarization adjoint",   "get_beta_schedule"),
    ("MPI parallel mpirun MEEP",             "mpi_parallel_simulation"),
    ("3D SOI slab TE mode eigenmode source", "eigenmode_source_kpoints"),
]
conn = sqlite3.connect(str(DB_PATH))
for q, expected in compare_queries:
    row = conn.execute(
        "SELECT id, pattern_name || '. ' || COALESCE(description,'') || ' ' || COALESCE(use_case,'') FROM patterns WHERE pattern_name=?",
        (expected,)
    ).fetchone()
    if not row:
        continue
    doc_text = row[1]

    v_new = model.encode(q, normalize_embeddings=True)
    v_doc_new = model.encode(doc_text, normalize_embeddings=True)
    score_new = float((v_new * v_doc_new).sum())

    v_old = old_model.encode(q, normalize_embeddings=True)
    v_doc_old = old_model.encode(doc_text, normalize_embeddings=True)
    score_old = float((v_old * v_doc_old).sum())

    delta = score_new - score_old
    print(f"  [{expected[:30]}]")
    print(f"    MiniLM: {score_old:.3f}  |  BGE-M3: {score_new:.3f}  |  +{delta:.3f}")
conn.close()

hr("완료")
print("  BGE-M3 임베딩 교체 검증 완료")
