"""
번역 결과 검증:
1. 한국어 잔존 여부 확인
2. 번역 전/후 샘플 비교 (백업 DB vs 현재)
3. 품질 체크 (빈 필드, 너무 짧은 번역 등)
"""
import sqlite3
import re

def has_korean(text):
    if not text:
        return False
    return bool(re.search(r'[\uAC00-\uD7A3\u3131-\u314E\u314F-\u3163]', text))

# 현재 DB
conn_new = sqlite3.connect('db/knowledge.db')
# 백업 DB
conn_old = sqlite3.connect('db/knowledge_backup_before_translate.db')

cur_new = conn_new.cursor()
cur_old = conn_old.cursor()

# 1. 한국어 잔존 체크
print("=" * 60)
print("1. 한국어 잔존 체크")
print("=" * 60)
cur_new.execute("SELECT id, pattern_name, description, use_case FROM patterns")
rows = cur_new.fetchall()

korean_remain = []
for row in rows:
    pid, name, desc, use_case = row
    if has_korean(desc) or has_korean(use_case):
        korean_remain.append((pid, name, 'desc' if has_korean(desc) else 'use_case'))

if korean_remain:
    print(f"[WARN] 한국어 잔존: {len(korean_remain)}개")
    for r in korean_remain:
        print(f"  id={r[0]} | {r[1]} | 필드: {r[2]}")
else:
    print(f"[OK] 한국어 잔존 없음 - 전체 {len(rows)}개 모두 영어")

# 2. 빈 필드 체크
print("\n" + "=" * 60)
print("2. 빈 필드 체크")
print("=" * 60)
empty_desc = [(r[0], r[1]) for r in rows if not r[2]]
empty_use  = [(r[0], r[1]) for r in rows if not r[3]]
print(f"  description 없음: {len(empty_desc)}개 → {[r[1] for r in empty_desc]}")
print(f"  use_case 없음:    {len(empty_use)}개 → {[r[1] for r in empty_use]}")

# 3. 번역 전/후 비교 샘플 5개
print("\n" + "=" * 60)
print("3. 번역 전/후 비교 (랜덤 5개)")
print("=" * 60)
cur_old.execute("SELECT id, pattern_name, description, use_case FROM patterns ORDER BY RANDOM() LIMIT 5")
old_samples = cur_old.fetchall()

for old in old_samples:
    pid, name, old_desc, old_use = old
    cur_new.execute("SELECT description, use_case FROM patterns WHERE id=?", (pid,))
    new = cur_new.fetchone()
    if not new:
        continue
    new_desc, new_use = new
    print(f"\n[id={pid}] {name}")
    if old_desc != new_desc:
        print(f"  BEFORE desc: {old_desc[:80] if old_desc else 'N/A'}")
        print(f"  AFTER  desc: {new_desc[:80] if new_desc else 'N/A'}")
    else:
        print(f"  desc: (no change) {new_desc[:80] if new_desc else 'N/A'}")
    if old_use != new_use:
        print(f"  BEFORE use : {old_use[:80] if old_use else 'N/A'}")
        print(f"  AFTER  use : {new_use[:80] if new_use else 'N/A'}")
    else:
        print(f"  use:  (no change) {new_use[:80] if new_use else 'N/A'}")

# 4. 요약
print("\n" + "=" * 60)
print("4. 최종 요약")
print("=" * 60)
cur_old.execute("SELECT id, description, use_case FROM patterns")
old_all = {r[0]: (r[1], r[2]) for r in cur_old.fetchall()}
changed = sum(1 for r in rows if old_all.get(r[0], (None,None)) != (r[2], r[3]))
print(f"  전체 패턴: {len(rows)}개")
print(f"  변경된 패턴: {changed}개")
print(f"  한국어 잔존: {len(korean_remain)}개")
print(f"  빈 description: {len(empty_desc)}개")
print(f"  빈 use_case: {len(empty_use)}개")

conn_new.close()
conn_old.close()
