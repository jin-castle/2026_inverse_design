import sqlite3
conn = sqlite3.connect('db/knowledge.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('Tables:', [r[0] for r in c.fetchall()])
c.execute('PRAGMA table_info(concepts)')
print('Columns:', [(r[1], r[2]) for r in c.fetchall()])
c.execute('SELECT COUNT(*) FROM concepts')
print('Total concepts:', c.fetchone()[0])
# List all concept names
c.execute('SELECT name FROM concepts ORDER BY name')
names = [r[0] for r in c.fetchall()]
print('Names:', names)
conn.close()
