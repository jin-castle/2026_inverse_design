import sqlite3
conn = sqlite3.connect('C:/Users/user/projects/meep-kb/db/knowledge.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in c.fetchall()]
print('Tables:', tables)
for t in tables:
    c.execute(f'SELECT COUNT(*) FROM [{t}]')
    cnt = c.fetchone()[0]
    c.execute(f'PRAGMA table_info([{t}])')
    cols = [col[1] for col in c.fetchall()]
    print(f'  {t} ({cnt} rows): {cols}')
conn.close()
