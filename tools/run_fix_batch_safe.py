# -*- coding: utf-8 -*-
"""
run_fix_batch_safe.py — 즉시 실행 가능 8건 배치 처리
마크다운 없이 바로 verified_fix_v2로 처리 가능한 IDs
"""
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"
BASE = Path(__file__).parent.parent

TARGET_IDS = [4, 11, 38, 43, 52, 58, 65, 67]

print(f"[배치] 즉시 실행 가능 {len(TARGET_IDS)}건 처리 시작")
print(f"대상 IDs: {TARGET_IDS}")
print()

succeeded = []
failed = []
timed_out = []

for i, vid in enumerate(TARGET_IDS):
    print(f"[{i+1}/{len(TARGET_IDS)}] id={vid} 처리 중...")
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8",
             str(BASE / "tools" / "verified_fix_v2.py"),
             "--id", str(vid)],
            cwd=str(BASE),
            timeout=180,
            capture_output=False  # 직접 출력
        )
        # DB에서 fix_worked 확인
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
