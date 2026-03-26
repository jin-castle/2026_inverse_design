import sqlite3, sys, re
sys.path.insert(0, 'tools')
from run_concept_demos import preprocess_code

conn = sqlite3.connect("db/knowledge.db")
row = conn.execute("SELECT name, demo_code FROM concepts WHERE name='Block'").fetchone()
conn.close()

name, code = row
print("=== ORIGINAL demo_code (first 200) ===")
print(repr(code[:200]))
print()

processed = preprocess_code(code, name)
print("=== PROCESSED (first 400) ===")
print(processed[:400])
print()

# meep.adjoint import 잘리는 원인 확인
lines = processed.splitlines()
for i, line in enumerate(lines[:10]):
    print(f"  line {i+1}: {repr(line)}")
