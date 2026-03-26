import sqlite3
conn = sqlite3.connect('db/knowledge.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT id, error_type, error_class, error_message, original_code FROM sim_errors_v2 WHERE fix_worked=0 ORDER BY id").fetchall()
for r in rows:
    code = (r['original_code'] or '')[:200]
    print(f"id={r['id']} | {r['error_class']} | {r['error_type']} | {str(r['error_message'])[:80]}")
    print(f"  code: {code[:150].replace(chr(10),' ')}")
    print()
conn.close()
