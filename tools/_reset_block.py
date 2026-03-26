import sqlite3
conn = sqlite3.connect("db/knowledge.db")
conn.execute("UPDATE concepts SET summary=NULL WHERE name='Block'")
conn.commit()
print("Block summary 초기화 완료")
conn.close()
