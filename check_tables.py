import sqlite3, json, os

# DB 파일 찾기
for db_path in ['/app/db/knowledge.db', '/app/db/meep_kb.db', '/app/meep_kb.db', '/data/meep_kb.db']:
    if os.path.exists(db_path):
        print(f'DB found: {db_path}')
        conn = sqlite3.connect(db_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print('Tables:', [t[0] for t in tables])

        for t in tables:
            tname = t[0]
            count = conn.execute(f'SELECT COUNT(*) FROM {tname}').fetchone()[0]
            print(f'  {tname}: {count} rows')
            if tname == 'examples':
                cur = conn.cursor()
                cur.execute('PRAGMA table_info(examples)')
                cols = [r[1] for r in cur.fetchall()]
                print(f'    columns: {cols}')
                cur.execute('SELECT result_status, COUNT(*) FROM examples GROUP BY result_status')
                print('    result_status 현황:')
                for row in cur.fetchall():
                    status = row[0] if row[0] else 'NULL'
                    print(f'      {status}: {row[1]}')
                typec_ids = [333,341,353,375,378,381,389,400,505,513,526,528,539,548,554,559,562,573,575,592]
                ids_str = ','.join(map(str, typec_ids))
                cur.execute(f'SELECT id, title, result_status, result_images FROM examples WHERE id IN ({ids_str}) ORDER BY id')
                print('\n    TypeC 예제 상태:')
                for row in cur.fetchall():
                    imgs = row[3]
                    img_count = len(json.loads(imgs)) if imgs and imgs not in ('[]', None) else 0
                    status = row[2] if row[2] else 'NULL'
                    print(f'      id={row[0]} [{status}] {str(row[1])[:40]} (이미지:{img_count})')
        conn.close()
        break
else:
    print('DB not found in expected paths')
    os.system('find /app -name "*.db" 2>/dev/null')
