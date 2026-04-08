import sqlite3
conn = sqlite3.connect('db/knowledge.db')
total = conn.execute('SELECT COUNT(*) FROM patterns').fetchone()[0]
rows = conn.execute("SELECT pattern_name, author_repo FROM patterns WHERE author_repo LIKE '%nanophotonics%'").fetchall()
print(f'Total patterns: {total}')
print(f'EIDL patterns: {len(rows)}')
for r in rows:
    print(' -', r[0], '|', r[1])
conn.close()
