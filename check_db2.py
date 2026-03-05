import sqlite3, os

db_files = ['/app/db/meep_kb.db', '/app/db/knowledge.db', '/app/db/feedback.db']

for db_path in db_files:
    if not os.path.exists(db_path):
        continue
    size_mb = os.path.getsize(db_path) / 1024 / 1024
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in c.fetchall()]
    print(f'\n{"="*55}')
    print(f'DB: {db_path} ({size_mb:.1f} MB)')
    print(f'테이블: {tables}')

    for tbl in tables:
        try:
            c.execute(f'SELECT COUNT(*) FROM {tbl}')
            cnt = c.fetchone()[0]
            c.execute(f'PRAGMA table_info({tbl})')
            cols = [r[1] for r in c.fetchall()]

            last_dt = 'N/A'
            for dt_col in ['created_at', 'timestamp', 'date', 'updated_at']:
                if dt_col in cols:
                    c.execute(f'SELECT {dt_col} FROM {tbl} ORDER BY {dt_col} DESC LIMIT 1')
                    row = c.fetchone()
                    if row and row[0]:
                        last_dt = str(row[0])[:19]
                    break
            print(f'  {tbl:25s}: {cnt:5d}개  최근={last_dt}')
        except Exception as e:
            print(f'  {tbl}: 오류 {e}')

    # errors 테이블 있으면 최근 항목
    if 'errors' in tables:
        print(f'\n  [errors 최근 3개]')
        c.execute('SELECT id, category, source_type, created_at, SUBSTR(error_msg,1,80) as msg FROM errors ORDER BY id DESC LIMIT 3')
        for r in c.fetchall():
            print(f'    id={r["id"]} cat={r["category"]} src={r["source_type"]} dt={r["created_at"]}')
            print(f'      msg={r["msg"]}')

    # examples/docs 통계
    for tbl in ['examples', 'docs', 'patterns']:
        if tbl in tables:
            c.execute(f'PRAGMA table_info({tbl})')
            cols2 = [r[1] for r in c.fetchall()]
            print(f'\n  [{tbl} 컬럼: {cols2}]')
            c.execute(f'SELECT * FROM {tbl} LIMIT 1')
            row = c.fetchone()
            if row:
                print(f'    샘플: {dict(row)}')

    conn.close()
