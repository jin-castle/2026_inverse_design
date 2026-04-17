import sqlite3
conn = sqlite3.connect('db/knowledge.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('Tables:', [t[0] for t in tables])
for tname in ['patterns', 'examples', 'errors', 'concepts']:
    try:
        cols = conn.execute(f'PRAGMA table_info({tname})').fetchall()
        print(f'\n[{tname}] cols:', [c[1] for c in cols])
        row = conn.execute(f'SELECT * FROM {tname} LIMIT 1').fetchone()
        if row:
            for i, col in enumerate(cols):
                val = str(row[i] or '')[:120]
                print(f'  {col[1]}: {val}')
    except Exception as e:
        print(f'{tname}: {e}')
conn.close()
