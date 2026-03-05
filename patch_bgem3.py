#!/usr/bin/env python3
"""
BGE-M3로 임베딩 모델 교체 패치
대상 파일:
  /app/api/main.py
  /app/agent/search_executor.py
  /app/query/semantic_search.py
  /app/query/semantic_search_v2.py
"""
import re

OLD_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
NEW_MODEL = "BAAI/bge-m3"

files = [
    "/app/api/main.py",
    "/app/agent/search_executor.py",
    "/app/query/semantic_search.py",
    "/app/query/semantic_search_v2.py",
]

for fpath in files:
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"[SKIP] {fpath}: {e}")
        continue

    if OLD_MODEL not in content:
        print(f"[OK already] {fpath}")
        continue

    # 모델명 교체
    new_content = content.replace(OLD_MODEL, NEW_MODEL)

    # normalize_embeddings=True 추가 (encode 호출부에)
    # model.encode([query]) → model.encode([query], normalize_embeddings=True)
    # model.encode([augmented]) → model.encode([augmented], normalize_embeddings=True)
    new_content = re.sub(
        r'model\.encode\(\[([^\]]+)\]\)(?!\.tolist)',
        r'model.encode([\1], normalize_embeddings=True)',
        new_content
    )
    # .encode([...]).tolist() 패턴도 처리
    new_content = re.sub(
        r'model\.encode\(\[([^\]]+)\]\)\.tolist\(\)',
        r'model.encode([\1], normalize_embeddings=True).tolist()',
        new_content
    )

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"[PATCHED] {fpath}")

print("\nDone.")
