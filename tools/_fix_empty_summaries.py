#!/usr/bin/env python3
"""summary가 비어있는 개념들만 재생성."""
import os, sys, sqlite3
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# 두 스크립트 모두 import
import importlib.util

def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

base = Path(__file__).parent
v1 = load_module(base / "generate_concepts.py", "gcv1")
v2 = load_module(base / "generate_concepts_v2.py", "gcv2")

# 전체 개념 목록 합치기
all_concepts = {c["name"]: (c, v1) for c in v1.CONCEPTS}
all_concepts.update({c["name"]: (c, v2) for c in v2.CONCEPTS})

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"
conn = sqlite3.connect(str(DB_PATH), timeout=10)

# summary 빈 개념 찾기
bad = conn.execute(
    "SELECT name FROM concepts WHERE summary IS NULL OR LENGTH(summary) <= 10"
).fetchall()
bad_names = [r[0] for r in bad]

if not bad_names:
    print("모두 OK! 재처리 불필요.")
    conn.close()
    sys.exit(0)

print(f"재처리 대상 {len(bad_names)}개: {bad_names}")

api_key = os.environ.get("ANTHROPIC_API_KEY", "")
if not api_key:
    print("[ERROR] ANTHROPIC_API_KEY 없음")
    sys.exit(1)

import time
success = 0
for name in bad_names:
    if name not in all_concepts:
        print(f"  SKIP {name} (목록에 없음)")
        continue
    concept, mod = all_concepts[name]
    print(f"  🔄 {name} ({concept['name_ko']}) 재생성...")
    try:
        parsed = mod.generate_concept(concept, api_key)
        if not parsed.get("summary") or len(parsed["summary"]) < 20:
            print(f"     ⚠️  summary 짧음: {repr(parsed.get('summary',''))[:60]}")
        mod.save_concept(conn, concept, parsed)
        print(f"     ✅ summary: {len(parsed.get('summary',''))}자, code: {len(parsed.get('demo_code',''))}자")
        success += 1
        time.sleep(1)
    except Exception as e:
        print(f"     ❌ 실패: {e}")

conn.close()
print(f"\n=== 재처리 완료: {success}/{len(bad_names)} ===")
