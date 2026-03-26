import sqlite3
conn = sqlite3.connect('db/knowledge.db')
conn.row_factory = sqlite3.Row
rows = conn.execute(
    'SELECT id, error_type, error_class, error_message, original_code '
    'FROM sim_errors_v2 WHERE fix_worked=0 AND original_code IS NOT NULL '
    'ORDER BY LENGTH(original_code) LIMIT 5'
).fetchall()
for r in rows:
    oc = r['original_code'] or ''
    print(f"id={r['id']} | len={len(oc)} | {r['error_class']} | {r['error_type']} | {str(r['error_message'])[:80]}")
conn.close()
