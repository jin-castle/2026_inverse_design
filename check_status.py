import sqlite3, json
conn = sqlite3.connect('/app/db/meep_kb.db')
cur = conn.cursor()

cur.execute('SELECT result_status, COUNT(*) FROM examples GROUP BY result_status')
print('=== Examples result_status 현황 ===')
for row in cur.fetchall():
    status = row[0] if row[0] else 'NULL'
    print(f'  {status}: {row[1]}')

cur.execute('SELECT COUNT(*) FROM examples')
print(f'\n총 examples: {cur.fetchone()[0]}')

typec_ids = [333,341,353,375,378,381,389,400,505,513,526,528,539,548,554,559,562,573,575,592]
ids_str = ','.join(map(str, typec_ids))
cur.execute(f'SELECT id, title, result_status, result_images FROM examples WHERE id IN ({ids_str}) ORDER BY id')
print('\n=== TypeC 예제 상태 ===')
for row in cur.fetchall():
    imgs = row[3]
    img_count = len(json.loads(imgs)) if imgs and imgs != '[]' else 0
    status = row[2] if row[2] else 'NULL'
    print(f'  id={row[0]} [{status}] {str(row[1])[:40]} (이미지:{img_count})')
conn.close()
