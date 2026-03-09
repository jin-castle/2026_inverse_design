import json, sqlite3
from pathlib import Path

# 1. agent2_failed.json 확인
data = json.load(open('agent2_failed.json'))
print('agent2_failed.json 레코드 수:', len(data))
if data:
    print('필드:', list(data[0].keys()))
    print('샘플:')
    d = data[0]
    for k, v in d.items():
        print(f'  {k}: {str(v)[:100]}')
    print()

# 2. typee/typeb 에러 파일들
import os
err_files = [f for f in os.listdir('.') if f.startswith('typee_err_') or f.startswith('typeb_err_')]
print(f'에러 파일 수: {len(err_files)}')
for f in err_files[:3]:
    content = open(f).read()[:200]
    print(f'  {f}: {content[:100]}')

print()

# 3. knowledge.db issues 테이블
db = sqlite3.connect('db/knowledge.db')
cur = db.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('DB 테이블:', tables)
for t in tables:
    cur.execute(f'SELECT COUNT(*) FROM "{t}"')
    cnt = cur.fetchone()[0]
    print(f'  {t}: {cnt}개')
db.close()
