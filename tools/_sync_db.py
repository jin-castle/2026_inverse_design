import sqlite3, shutil

# WAL 체크포인트 + DELETE 모드로 저장
src = 'db/knowledge.db'
dst = 'db/knowledge_clean.db'
shutil.copy2(src, dst)

db = sqlite3.connect(dst)
db.execute('PRAGMA journal_mode=DELETE')
db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
db.commit()
total = db.execute('SELECT COUNT(*) FROM sim_errors').fetchone()[0]
marl = db.execute("SELECT COUNT(*) FROM sim_errors WHERE source='marl_auto'").fetchone()[0]
print(f'sim_errors: {total}개, marl_auto: {marl}개')
db.close()
print('Clean DB 준비 완료')
