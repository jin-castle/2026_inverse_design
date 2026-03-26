import sqlite3
conn = sqlite3.connect("db/knowledge.db")
conn.execute("UPDATE concepts SET result_status='pending' WHERE result_status='error'")
conn.commit()
n = conn.execute("SELECT COUNT(*) FROM concepts WHERE result_status='pending'").fetchone()[0]
print(f"pending으로 초기화: {n}개")
stats = dict(conn.execute("SELECT result_status, COUNT(*) FROM concepts GROUP BY result_status").fetchall())
print("현재 상태:", stats)
conn.close()
