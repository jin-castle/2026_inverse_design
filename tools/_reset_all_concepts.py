import sqlite3
conn = sqlite3.connect("db/knowledge.db")
conn.execute("UPDATE concepts SET result_status='pending', result_images=NULL")
conn.commit()
n = conn.execute("SELECT COUNT(*) FROM concepts WHERE result_status='pending'").fetchone()[0]
print(f"전체 pending 초기화: {n}개")
conn.close()
