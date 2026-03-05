import sqlite3

DB = '/mnt/c/Users/user/projects/meep-kb/db/feedback.db'
conn = sqlite3.connect(DB)

# answer_text 컬럼 추가 (없을 때만)
try:
    conn.execute('ALTER TABLE feedback ADD COLUMN answer_text TEXT DEFAULT ""')
    conn.commit()
    print('answer_text column added')
except Exception as e:
    print('already exists or error:', e)

# 스키마 확인
schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table'").fetchone()
print(schema[0])
conn.close()
