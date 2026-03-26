import sqlite3
conn = sqlite3.connect("db/knowledge.db")
rows = conn.execute("SELECT name, name_ko, category, difficulty FROM concepts WHERE result_status='error' ORDER BY difficulty, category").fetchall()
print(f"재생성 대상: {len(rows)}개")
for r in rows:
    print(f"  {r[0]} / {r[1]} / {r[2]} / {r[3]}")
conn.close()
