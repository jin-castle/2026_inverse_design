import sqlite3
conn = sqlite3.connect('db/knowledge.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('Tables:', tables)

# Check sim_errors_v2 schema
if 'sim_errors_v2' in tables:
    cur.execute("PRAGMA table_info(sim_errors_v2)")
    cols = cur.fetchall()
    print('\nsim_errors_v2 columns:')
    for c in cols:
        print(' ', c)
    cur.execute("SELECT COUNT(*) FROM sim_errors_v2")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=0")
    unfixed = cur.fetchone()[0]
    print(f'\nTotal v2 records: {total}, fix_worked=0: {unfixed}')
    
    # Show sample record
    cur.execute("SELECT * FROM sim_errors_v2 WHERE fix_worked=0 LIMIT 1")
    row = cur.fetchone()
    if row:
        col_names = [c[1] for c in cur.execute("PRAGMA table_info(sim_errors_v2)").fetchall()]
        print('\nSample fix_worked=0 record:')
        for name, val in zip(col_names, row):
            if val and len(str(val)) > 100:
                print(f'  {name}: {str(val)[:100]}...')
            else:
                print(f'  {name}: {val}')
else:
    print('sim_errors_v2 table does not exist!')
conn.close()
