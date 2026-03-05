import sqlite3

conn = sqlite3.connect('/app/db/meep_kb.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print('=== 테이블 목록 ===', tables)

for tbl in tables:
    try:
        c.execute(f'SELECT COUNT(*) FROM {tbl}')
        cnt = c.fetchone()[0]
        c.execute(f'PRAGMA table_info({tbl})')
        cols = [r[1] for r in c.fetchall()]
        if 'created_at' in cols:
            c.execute(f'SELECT created_at FROM {tbl} ORDER BY created_at DESC LIMIT 1')
            row = c.fetchone()
            last_dt = row[0] if row else 'N/A'
        else:
            last_dt = 'N/A'
        print(f'{tbl}: {cnt}개  최근={last_dt}  컬럼={cols}')
    except Exception as e:
        print(f'{tbl}: 오류 {e}')

# errors 최근 5개
print('\n=== errors 최근 5개 ===')
c.execute('SELECT id, category, source_type, verified, created_at, SUBSTR(error_msg,1,60) as msg FROM errors ORDER BY id DESC LIMIT 5')
for r in c.fetchall():
    print(dict(r))

# examples 최근 5개
print('\n=== examples 최근 5개 ===')
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='examples'")
if c.fetchone():
    c.execute('SELECT id, title, created_at FROM examples ORDER BY id DESC LIMIT 5')
    for r in c.fetchall():
        print(dict(r))

conn.close()
