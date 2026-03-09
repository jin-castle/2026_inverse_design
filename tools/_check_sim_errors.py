import sqlite3
db = sqlite3.connect('db/knowledge.db')
cur = db.cursor()
cur.execute("PRAGMA table_info(sim_errors)")
cols = cur.fetchall()
print('sim_errors 컬럼:')
for c in cols:
    print(' ', c)
cur.execute("SELECT * FROM sim_errors LIMIT 2")
for row in cur.fetchall():
    print('row:', str(row)[:200])
db.close()
