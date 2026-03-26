# -*- coding: utf-8 -*-
import sqlite3
conn = sqlite3.connect('db/knowledge.db')
# Check full code of ID 38
code38 = conn.execute('SELECT original_code FROM sim_errors_v2 WHERE id=38').fetchone()[0]
print('=== ID 38 (first 800 chars) ===')
print(code38[:800])
print()
# how many have # [MD] pattern
md_count = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=0 AND original_code LIKE '# [MD]%'").fetchone()[0]
print(f'# [MD] 시작 코드: {md_count}건')
# All fix_worked=0 IDs with original_code
rows = conn.execute("SELECT id, substr(original_code,1,100) FROM sim_errors_v2 WHERE fix_worked=0 ORDER BY id").fetchall()
print(f'\nfix_worked=0 records: {len(rows)}')
for r in rows[:10]:
    print(f'  id={r[0]}: {repr(r[1][:60])}')
conn.close()
