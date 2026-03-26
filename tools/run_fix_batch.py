# -*- coding: utf-8 -*-
"""
run_fix_batch.py — Timeout/MPIDeadlockRisk/Unknown 제외 배치 실행
"""
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"

SKIP_TYPES = ('Timeout', 'MPIDeadlockRisk', 'Unknown', '')

conn = sqlite3.connect(str(DB_PATH))
rows = conn.execute("""
    SELECT id, error_type FROM sim_errors_v2 
    WHERE fix_worked=0 
    AND error_type NOT IN ('Timeout', 'MPIDeadlockRisk', 'Unknown')
    AND (error_type IS NOT NULL AND error_type != '')
    AND original_code IS NOT NULL AND original_code != ''
    ORDER BY 
        CASE error_type
            WHEN 'NumericalError' THEN 1
            WHEN 'ImportError' THEN 2
            WHEN 'PML' THEN 3
            WHEN 'TypeError' THEN 4
            WHEN 'RuntimeError' THEN 5
            WHEN 'AttributeError' THEN 6
            WHEN 'Harminv' THEN 7
            ELSE 8
        END,
        id
""").fetchall()
conn.close()

print(f"[배치] 처리 대상: {len(rows)}건")
for error_type, count in [(r[1], rows.count(r)) for r in rows]:
    pass

# 에러 타입별 집계 출력
from collections import Counter
type_counts = Counter(r[1] for r in rows)
for et, c in type_counts.most_common():
    print(f"  {et}: {c}건")

print()
succeeded = []
failed = []

for i, (vid, error_type) in enumerate(rows):
    print(f"\n[{i+1}/{len(rows)}] id={vid} ({error_type}) 처리 중...")
    try:
        result = subprocess.run(
            [sys.executable, '-X', 'utf8', 'tools/verified_fix_v2.py', '--id', str(vid)],
            cwd=str(BASE),
            timeout=300,
            capture_output=False
        )
        if result.returncode == 0:
            # DB에서 fix_worked 확인
            conn2 = sqlite3.connect(str(DB_PATH))
            fw = conn2.execute('SELECT fix_worked FROM sim_errors_v2 WHERE id=?', (vid,)).fetchone()
            conn2.close()
            if fw and fw[0] == 1:
                succeeded.append((vid, error_type))
                print(f"  ✅ id={vid} 성공!")
            else:
                failed.append((vid, error_type))
                print(f"  ❌ id={vid} 실패 (fix_worked=0)")
        else:
            failed.append((vid, error_type))
            print(f"  ❌ id={vid} 프로세스 오류 (returncode={result.returncode})")
    except subprocess.TimeoutExpired:
        failed.append((vid, error_type))
        print(f"  ⏰ id={vid} 전체 타임아웃 (300s 초과)")
    except Exception as e:
        failed.append((vid, error_type))
        print(f"  💥 id={vid} 예외: {e}")
    
    time.sleep(0.5)

print(f"\n{'='*60}")
print(f"🏁 배치 완료:")
print(f"  ✅ 성공: {len(succeeded)}건 — {succeeded}")
print(f"  ❌ 실패: {len(failed)}건")

# 최종 DB 통계
conn3 = sqlite3.connect(str(DB_PATH))
by_fw = conn3.execute('SELECT fix_worked, COUNT(*) FROM sim_errors_v2 GROUP BY fix_worked').fetchall()
conn3.close()
print(f"\n=== 최종 DB 상태 ===")
for fw, c in by_fw:
    print(f"  fix_worked={fw}: {c}건")
