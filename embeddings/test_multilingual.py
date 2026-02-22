from sentence_transformers import SentenceTransformer
m = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
v = m.encode(["시뮬레이션 발산", "simulation diverges"])
print(f"Korean vec shape: {v.shape}")
print(f"Sample values: {v[0][:3]}")
print("✅ 멀티링구얼 모델 정상 동작")
