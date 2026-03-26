"""현재 DB에서 result_status 현황 + 흰색/에러 이미지 체크."""
import sqlite3
from pathlib import Path

conn = sqlite3.connect("db/knowledge.db")
rows = conn.execute(
    "SELECT name, result_status, result_images, result_stdout FROM concepts ORDER BY name"
).fetchall()
conn.close()

results_dir = Path("db/results")

errors = []
white = []
ok = []

for name, status, img_url, stdout in rows:
    safe = name.replace("-", "_")
    import re
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    img_path = results_dir / f"concept_{safe}.png"

    if status == 'error':
        errors.append((name, stdout[:100] if stdout else ""))
    elif img_path.exists():
        size = img_path.stat().st_size
        if size < 3000:
            white.append((name, size, stdout[:80] if stdout else ""))
        else:
            ok.append(name)
    else:
        errors.append((name, "이미지 파일 없음"))

print(f"✅ OK: {len(ok)}개")
print(f"⚠️  흰색/작은 이미지: {len(white)}개")
print(f"❌ 에러/이미지없음: {len(errors)}개")

if white:
    print("\n--- 흰색 이미지 ---")
    for n, s, msg in white:
        print(f"  {n} ({s}B): {msg}")

if errors:
    print("\n--- 에러 목록 ---")
    for n, msg in errors:
        print(f"  {n}: {msg[:80]}")
