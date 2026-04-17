# -*- coding: utf-8 -*-
"""
run_fix_batch_cleaned.py — code_cleaner 정제 완료된 IDs 배치 처리
이미 code_cleaner로 original_code 정제된 레코드들에 대해 verified_fix_v2 실행
"""
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"
BASE = Path(__file__).parent.parent

# code_cleaner 성공 IDs (38, 43, 52, 65, 67은 이미 run_fix_batch_safe에서 처리)
CLEANED_IDS = [20, 22, 23, 24, 27, 28, 30, 31, 37, 40, 42, 44, 49, 68, 70, 71, 72, 76, 77, 80, 82, 91, 93, 95, 100, 107]

# 아직 fix_worked=0인 것만 필터
conn = sqlite3.connect(str(DB_PATH))
pending = [r[0] for r in conn.execute(
    f"SELECT id FROM sim_errors_v2 WHERE id IN ({','.join(str(x) for x in CLEANED_IDS)}) AND fix_worked=0"
).fetchall()]
conn.close()

print(f"[배치] code_cleaner 정제 완료 중 미처리: {len(pending)}건")
print(f"대상 IDs: {pending}")
print()

succeeded = []
failed = []
timed_out = []

for i, vid in enumerate(pending):
    print(f"[{i+1}/{len(pending)}] id={vid} 처리 중...")
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8",
             str(BASE / "tools" / "verified_fix_v2.py"),
             "--id", str(vid)],
            cwd=str(BASE),
            timeout=180,
            capture_output=False
        )
        conn = sqlite3.connect(str(DB_PATH))
        fw = conn.execute("SELECT fix_worked FROM sim_errors_v2 WHERE id=?", (vid,)).fetchone()
        conn.close()
        if fw and fw[0] == 1:
            succeeded.append(vid)
            print(f"  ✅ id={vid} 수정 성공 (fix_worked=1)")
        else:
            failed.append(vid)
            print(f"  ❌ id={vid} 수정 실패 (fix_worked=0)")
    except subprocess.TimeoutExpired:
        timed_out.append(vid)
        print(f"  ⏰ id={vid} 타임아웃 (180s)")
    except Exception as e:
        failed.append(vid)
        print(f"  💥 id={vid} 예외: {e}")
    time.sleep(2)

print()
print("=" * 60)
print(f"배치 완료:")
print(f"  ✅ 성공: {len(succeeded)}건 {succeeded}")
print(f"  ❌ 실패: {len(failed)}건 {failed}")
print(f"  ⏰ 타임아웃: {len(timed_out)}건 {timed_out}")

# 결과 확인
conn = sqlite3.connect(str(DB_PATH))
fw = conn.execute("SELECT fix_worked, COUNT(*) FROM sim_errors_v2 GROUP BY fix_worked").fetchall()
conn.close()
print("\n=== fix_worked 현황 ===")
for f, c in fw:
    print(f"  fix_worked={f}: {c}")
