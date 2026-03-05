# -*- coding: utf-8 -*-
"""Phase 1 검토: DB 패턴 내용 확인"""
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'db/knowledge.db'
conn = sqlite3.connect(DB_PATH)

# 파이프라인 패턴 목록
rows = conn.execute(
    "SELECT id, pattern_name, length(description), length(code_snippet), use_case FROM patterns WHERE pattern_name LIKE 'pipeline_%' ORDER BY id"
).fetchall()

print(f"=== Phase 1: Pipeline 패턴 현황 ({len(rows)}개) ===\n")
for pid, name, desc_len, code_len, use_case in rows:
    tag = use_case.split('|')[0].strip() if use_case else ''
    ok_desc = 'OK' if desc_len > 100 else 'SHORT'
    ok_code = 'OK' if code_len > 200 else 'SHORT'
    print(f"  [{pid}] {name}")
    print(f"       desc={desc_len}chars({ok_desc})  code={code_len}chars({ok_code})")
    print(f"       tag: {tag}")

# ChromaDB 확인
print("\n=== ChromaDB patterns 컬렉션 ===")
try:
    import chromadb
    client = chromadb.PersistentClient(path='db/chroma')
    col = client.get_collection('patterns')
    total = col.count()
    print(f"  총 {total}개 인덱싱됨")
    # pipeline 패턴 검색 테스트
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    test_queries = [
        "adjoint field DFT plot visualization",
        "MaterialGrid DesignRegion design region",
        "gradient map sensitivity",
        "beta scheduling tanh projection binarization",
        "conic filter minimum length scale fabrication",
    ]
    print("\n  [벡터 검색 테스트 - pipeline 패턴 상위 출현 확인]")
    for q in test_queries:
        emb = model.encode([q]).tolist()
        res = col.query(query_embeddings=emb, n_results=3, include=["distances","metadatas"])
        top = [(m['name'], round(1-d, 3)) for m, d in zip(res['metadatas'][0], res['distances'][0])]
        pipeline_top = [(n,s) for n,s in top if 'pipeline' in n]
        hit = 'HIT' if pipeline_top else 'MISS'
        print(f"    [{hit}] '{q[:40]}'")
        for n, s in top:
            mark = '**' if 'pipeline' in n else '  '
            print(f"         {mark}{n} ({s})")
except Exception as e:
    print(f"  ChromaDB 확인 실패: {e}")

conn.close()
