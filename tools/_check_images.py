import sqlite3, os
from pathlib import Path

conn = sqlite3.connect("db/knowledge.db")

# result_images 현황
rows = conn.execute("SELECT name, result_status, result_images FROM concepts ORDER BY name").fetchall()
has_img = [(r[0], r[2]) for r in rows if r[2] and r[2].strip()]
no_img = [r[0] for r in rows if not r[2] or not r[2].strip()]

print(f"result_images 컬럼 있는 것: {len(has_img)}개")
for n, img in has_img[:5]:
    print(f"  {n}: {img[:80]}")

print(f"\nresult_images 없는 것: {len(no_img)}개")

# db/results 폴더의 png 파일
results_dir = Path("db/results")
pngs = sorted(results_dir.glob("concept_*.png"))
print(f"\ndb/results/concept_*.png: {len(pngs)}개")
for p in pngs:
    print(f"  {p.name} ({p.stat().st_size//1024}KB)")

conn.close()
