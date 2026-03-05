"""
patterns 테이블:
1. url 컬럼 추가 (없는 경우)
2. 각 패턴의 url = '/dict#{pattern_name}' 으로 업데이트

실행:
  python update_pattern_urls.py                          # 로컬
  docker exec meep-kb-meep-kb-1 python update_pattern_urls.py  # Docker
"""
import sqlite3, os

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "db", "knowledge.db"))

conn = sqlite3.connect(DB_PATH, timeout=30)

# 1. url 컬럼 추가 (없으면)
cols = [r[1] for r in conn.execute("PRAGMA table_info(patterns)").fetchall()]
if "url" not in cols:
    conn.execute("ALTER TABLE patterns ADD COLUMN url TEXT DEFAULT ''")
    conn.commit()
    print("url 컬럼 추가 완료")
else:
    print("url 컬럼 이미 존재")

# 2. 각 패턴 url 업데이트
rows = conn.execute("SELECT id, pattern_name FROM patterns").fetchall()
updated = 0
for pid, pname in rows:
    url = f"/dict#{pname}"
    conn.execute("UPDATE patterns SET url=? WHERE id=?", (url, pid))
    updated += 1

conn.commit()
print(f"{updated}개 패턴 URL 업데이트 완료")

# 3. 확인
samples = conn.execute("SELECT id, pattern_name, url FROM patterns LIMIT 5").fetchall()
print("\n=== 샘플 확인 ===")
for r in samples:
    print(f"  {r[0]:3d} | {r[1][:40]:<40} | {r[2]}")

conn.close()
