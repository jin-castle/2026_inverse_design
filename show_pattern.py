import sqlite3
conn = sqlite3.connect('/app/db/knowledge.db')
cols = [d[0] for d in conn.execute('PRAGMA table_info(patterns)').fetchall()]
r = conn.execute('SELECT * FROM patterns WHERE pattern_name="dft_fields_extraction"').fetchone()
for c, v in zip(cols, r):
    val = str(v)[:400] if v else 'NULL'
    print(f'[{c}]\n{val}\n{"─"*50}')
