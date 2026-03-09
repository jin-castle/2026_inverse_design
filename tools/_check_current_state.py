import sqlite3
db = sqlite3.connect('db/knowledge.db')
cur = db.cursor()

cur.execute("SELECT COUNT(*) FROM sim_errors")
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM sim_errors WHERE fix_worked=1")
verified = cur.fetchone()[0]
cur.execute("SELECT source, COUNT(*) FROM sim_errors GROUP BY source ORDER BY COUNT(*) DESC")
by_source = cur.fetchall()
cur.execute("SELECT error_type, COUNT(*) FROM sim_errors GROUP BY error_type ORDER BY COUNT(*) DESC LIMIT 8")
by_type = cur.fetchall()

print(f"sim_errors 총 {total}개 (검증됨: {verified}개)")
print("소스별:", by_source)
print("에러타입:", by_type)

# 최근 5개
cur.execute("SELECT source, error_type, error_message FROM sim_errors ORDER BY id DESC LIMIT 5")
print("\n최근 5개:")
for r in cur.fetchall():
    print(f"  [{r[0]}] {r[1]}: {r[2][:60]}")
db.close()
