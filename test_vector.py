"""벡터 검색 직접 디버그"""
import sys, os
sys.path.insert(0, '/mnt/c/Users/user/projects/meep-kb/agent')
sys.path.insert(0, '/mnt/c/Users/user/projects/meep-kb/query')

os.environ["ANTHROPIC_API_KEY"] = "dummy"

# ChromaDB 직접 조회
import chromadb
client = chromadb.PersistentClient(path='/mnt/c/Users/user/projects/meep-kb/db/chroma')

collections = client.list_collections()
print("=== ChromaDB 컬렉션 목록 ===")
for c in collections:
    print(f"  {c.name}: {c.count()}건")

# 벡터 검색 직접 테스트
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

query = "adjoint 메모리 오류"
emb = model.encode([query])[0].tolist()

print(f"\n=== 쿼리: {query} ===")
for c in collections:
    try:
        results = c.query(query_embeddings=[emb], n_results=3, include=["distances", "metadatas"])
        dists = results["distances"][0]
        titles = [m.get("title", "?")[:50] for m in results["metadatas"][0]]
        print(f"\n[{c.name}]")
        for d, t in zip(dists, titles):
            score = 1 - d
            print(f"  score={score:.3f} (dist={d:.3f}) | {t}")
    except Exception as e:
        print(f"[{c.name}] 오류: {e}")
