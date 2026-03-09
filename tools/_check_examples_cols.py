import sqlite3
db = sqlite3.connect('db/knowledge.db')
cur = db.cursor()
cur.execute("PRAGMA table_info(examples)")
print('examples:', [r[1] for r in cur.fetchall()])
cur.execute("PRAGMA table_info(errors)")
print('errors:', [r[1] for r in cur.fetchall()])
cur.execute("PRAGMA table_info(patterns)")
print('patterns:', [r[1] for r in cur.fetchall()])
# examples FTS 구조
cur.execute("SELECT * FROM examples LIMIT 1")
row = cur.fetchone()
print('examples row 길이:', len(row) if row else 0)
db.close()
