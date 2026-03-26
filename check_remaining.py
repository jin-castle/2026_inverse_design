import json, sqlite3

with open('tools/audit_report.json', 'r', encoding='utf-8') as f:
    report = json.load(f)

examples = report.get('examples', {})
runnable_items = examples.get('runnable_items', [])
print(f'runnable_items 총계: {len(runnable_items)}')

conn = sqlite3.connect('db/knowledge.db')
total = conn.execute('SELECT COUNT(*) FROM live_runs').fetchone()[0]
done_refs = set(row[0] for row in conn.execute("SELECT source_ref FROM live_runs WHERE source='examples'"))
print(f'live_runs 총계: {total}')
print(f'examples source_ref done: {len(done_refs)}')

by_status = conn.execute('SELECT status, COUNT(*) FROM live_runs GROUP BY status').fetchall()
for s, c in by_status:
    print(f'  {s}: {c}')

# Check not_done by id
not_done = [r for r in runnable_items if f"ex_{r['id']}" not in done_refs]
print(f'\n미실행 runnable: {len(not_done)}건')
for r in not_done[:10]:
    print(f"  ex_{r['id']}: {r['title']}")
conn.close()
