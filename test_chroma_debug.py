"""ChromaDB 거리 메트릭 + 실제 score 범위 파악"""
import chromadb

CHROMA_DIR = '/mnt/c/Users/user/projects/meep-kb/db/chroma'
client = chromadb.PersistentClient(path=CHROMA_DIR)

# 컬렉션 목록 + 메타데이터
print("=== 컬렉션 목록 ===")
cols = client.list_collections()
for c in cols:
    # 컬렉션 메타 확인
    meta = c.metadata or {}
    print(f"  {c.name}: {c.count()}건 | distance={meta.get('hnsw:space', 'l2(기본값)')}")

print()

# errors 컬렉션의 실제 거리 분포 확인
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

test_queries = ["adjoint memory error", "simulation diverge", "EigenModeSource"]

for col_name in ["errors", "examples", "docs"]:
    try:
        col = client.get_collection(col_name)
        meta = col.metadata or {}
        space = meta.get("hnsw:space", "l2")
        print(f"\n[{col_name}] distance={space}, 건수={col.count()}")

        emb = model.encode([test_queries[0]]).tolist()
        res = col.query(query_embeddings=emb, n_results=5, include=["distances", "metadatas"])

        dists = res["distances"][0]
        metas = res["metadatas"][0]
        print(f"  거리 범위: {min(dists):.3f} ~ {max(dists):.3f}")
        for d, m in zip(dists, metas):
            score_wrong = 1 - d     # 현재 잘못된 방식
            # cosine space면: score = (2 - dist) / 2 → distance는 0~2
            # l2 space면: 0~∞, 1-dist는 의미없음
            print(f"  dist={d:.3f} | 1-dist={score_wrong:.3f} | keys={list(m.keys())[:3]}")
    except Exception as e:
        print(f"[{col_name}] 오류: {e}")
