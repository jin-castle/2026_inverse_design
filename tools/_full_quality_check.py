"""56개 전체 이미지 품질 점검 — 빈/흰/작은 이미지 및 실제 내용 확인."""
import subprocess, sqlite3, re
from pathlib import Path
from PIL import Image

RESULTS_DIR = Path("db/results")
conn = sqlite3.connect("db/knowledge.db")
rows = conn.execute("SELECT name FROM concepts ORDER BY name").fetchall()
conn.close()

issues = []

for (name,) in rows:
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    img = RESULTS_DIR / f"concept_{safe}.png"

    if not img.exists():
        issues.append((name, "파일없음", 0))
        continue

    size = img.stat().st_size
    if size < 5000:
        issues.append((name, f"작음({size//1024}KB)", size))
        continue

    # PIL로 실제 내용 확인
    try:
        im = Image.open(img).convert("RGB")
        pixels = list(im.getdata())
        n_white = sum(1 for p in pixels if p[0] > 245 and p[1] > 245 and p[2] > 245)
        n_total = len(pixels)
        white_pct = n_white / n_total * 100
        if white_pct > 90:
            issues.append((name, f"흰색{white_pct:.0f}%({size//1024}KB)", size))
        elif white_pct > 70:
            issues.append((name, f"⚠️대부분흰색{white_pct:.0f}%({size//1024}KB)", size))
    except Exception as e:
        issues.append((name, f"PIL오류:{e}", size))

print(f"총 {len(rows)}개 점검 완료")
if issues:
    print(f"\n❌ 문제 있는 이미지: {len(issues)}개")
    for n, msg, s in issues:
        print(f"  {n}: {msg}")
else:
    print("✅ 모든 이미지 정상!")
