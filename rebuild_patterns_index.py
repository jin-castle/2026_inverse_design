"""
patterns 테이블 변경 후 ChromaDB 벡터 인덱스 재구축
"""
import sqlite3
import chromadb
from sentence_transformers import SentenceTransformer

DB_PATH    = '/app/db/knowledge.db'
CHROMA_DIR = '/app/db/chroma'
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'

print("Loading embedding model...")
model = SentenceTransformer(MODEL_NAME)

print("Connecting to DBs...")
conn   = sqlite3.connect(DB_PATH)
client = chromadb.PersistentClient(path=CHROMA_DIR)

# 기존 patterns 컬렉션 삭제 후 재생성
try:
    client.delete_collection("patterns")
    print("Deleted old patterns collection")
except:
    pass

col = client.create_collection(
    "patterns",
    metadata={"hnsw:space": "cosine"}
)

# 전체 패턴 로드
rows = conn.execute(
    "SELECT id, pattern_name, description, code_snippet, use_case FROM patterns"
).fetchall()
print(f"Found {len(rows)} patterns")

# 임베딩용 텍스트: description + use_case 결합
texts = []
ids   = []
metas = []

for row in rows:
    pid, name, desc, code, use_case = row
    # 검색 텍스트: description + use_case (가장 중요한 필드들)
    search_text = f"{name} {desc or ''} {use_case or ''}".strip()
    texts.append(search_text)
    ids.append(f"pattern_{pid}")
    metas.append({"id": pid, "name": name})

print("Generating embeddings...")
embeddings = model.encode(texts, batch_size=32, show_progress_bar=True).tolist()

print("Inserting into ChromaDB...")
# 배치로 삽입
BATCH = 50
for i in range(0, len(texts), BATCH):
    col.add(
        ids=ids[i:i+BATCH],
        embeddings=embeddings[i:i+BATCH],
        documents=texts[i:i+BATCH],
        metadatas=metas[i:i+BATCH],
    )

print(f"Done. patterns collection: {col.count()} entries")

# 검색 테스트
print("\n--- Search Test: 'DFT field plot adjoint' ---")
test_emb = model.encode(["DFT field plot adjoint visualization"]).tolist()
results = col.query(query_embeddings=test_emb, n_results=5,
                    include=["distances", "metadatas", "documents"])
for i, (did, dist, meta) in enumerate(zip(
    results["ids"][0], results["distances"][0], results["metadatas"][0]
)):
    score = 1 - dist
    print(f"  [{i+1}] {meta['name']} | score={score:.3f}")

conn.close()
