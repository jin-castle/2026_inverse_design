import json, sqlite3, os
from pathlib import Path

# 1. agent2_failed.json
try:
    data = json.load(open('agent2_failed.json', encoding='utf-8'))
    print('agent2_failed.json 레코드 수:', len(data))
    if data:
        print('필드:', list(data[0].keys()))
        d = data[0]
        for k, v in d.items():
            print(f'  {k}: {str(v)[:80]}')
except Exception as e:
    print('agent2_failed.json 오류:', e)

print()

# 2. typee/typeb 에러 파일들
err_files = [f for f in os.listdir('.') if ('_err_' in f) and f.endswith('.txt')]
print(f'에러 텍스트 파일 수: {len(err_files)}')
for f in sorted(err_files)[:3]:
    content = open(f, encoding='utf-8', errors='replace').read()[:200]
    print(f'  {f}: {repr(content[:100])}')

print()

# 3. knowledge.db
db = sqlite3.connect('db/knowledge.db')
cur = db.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('DB 테이블:', tables)
for t in tables:
    cur.execute(f'SELECT COUNT(*) FROM "{t}"')
    cnt = cur.fetchone()[0]
    print(f'  {t}: {cnt}개')

# issues 테이블 컬럼
if 'issues' in tables:
    cur.execute("PRAGMA table_info(issues)")
    cols = [r[1] for r in cur.fetchall()]
    print('issues 컬럼:', cols)
    cur.execute("SELECT * FROM issues LIMIT 2")
    rows = cur.fetchall()
    for row in rows:
        print('  row:', str(row)[:200])

db.close()
