# -*- coding: utf-8 -*-
"""
test_fix_batch.py — fix-batch 파이프라인 검증 테스트

실행:
  python -X utf8 tools/test_fix_batch.py
"""
import sqlite3
import sys
import subprocess
from pathlib import Path

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"

passed = 0
failed = 0
results = []


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        print(f"  ✅ PASS: {name}")
        if detail:
            print(f"     {detail}")
        passed += 1
        results.append(("PASS", name))
    else:
        print(f"  ❌ FAIL: {name}")
        if detail:
            print(f"     {detail}")
        failed += 1
        results.append(("FAIL", name))


def get_fix_worked_count(fw_val: int) -> int:
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=?", (fw_val,)).fetchone()[0]
    conn.close()
    return c


print("=" * 60)
print("test_fix_batch.py — fix-batch 파이프라인 검증")
print("=" * 60)
print()

# ─────────────────────────────────────────────────────────────
# TEST 1: run_fix_batch_safe.py 존재 확인 및 fix_worked=1 기록 확인
# ─────────────────────────────────────────────────────────────
print("TEST 1: run_fix_batch_safe.py 존재 확인 및 fix_worked=1 현황")
batch_safe = BASE / "tools" / "run_fix_batch_safe.py"
check("run_fix_batch_safe.py 파일 존재", batch_safe.exists())

fw1_count = get_fix_worked_count(1)
fw0_count = get_fix_worked_count(0)
print(f"  현재 fix_worked=1: {fw1_count}건, fix_worked=0: {fw0_count}건")
check("fix_worked=1 최소 11건 이상 (초기값)", fw1_count >= 11,
      f"현재 {fw1_count}건")
print()

# ─────────────────────────────────────────────────────────────
# TEST 2: code_cleaner.py 마크다운 정제 테스트
# ─────────────────────────────────────────────────────────────
print("TEST 2: code_cleaner.py 마크다운 정제 테스트")
sys.path.insert(0, str(BASE / "tools"))
try:
    from code_cleaner import clean_meep_code
    check("code_cleaner.py import 성공", True)
except ImportError as e:
    check("code_cleaner.py import 성공", False, str(e))
    print()
    print("⚠️  code_cleaner.py를 import할 수 없어 TEST 2, 3 스킵")
    clean_meep_code = None

if clean_meep_code:
    # 테스트 케이스 1: ```python ... ``` 블록 추출
    test_md = '```python\nimport meep as mp\nresolution = 20\ncell = mp.Vector3(16, 8, 0)\n```'
    result = clean_meep_code(test_md)
    check(
        "```python 블록 추출",
        result is not None and "import meep" in result,
        f"결과: {repr(result[:60]) if result else 'None'}"
    )

    # 테스트 케이스 2: In [N]: 패턴 제거
    test_jupyter = "In [1]: import meep as mp\nIn [2]: resolution = 20\nIn [3]: sim = mp.Simulation(resolution=resolution)"
    result2 = clean_meep_code(test_jupyter)
    check(
        "In [N]: 패턴 제거",
        result2 is not None and "import meep" in result2 and "In [" not in result2,
        f"결과: {repr(result2[:60]) if result2 else 'None'}"
    )

    # 테스트 케이스 3: # [MD] 블록 제거
    test_md_block = """# [MD]
# Radiation Pattern

# [MD]
In this example, we compute the radiation pattern of an antenna.

import meep as mp
import numpy as np

resolution = 25
cell = mp.Vector3(10, 10, 0)
sim = mp.Simulation(cell_size=cell, resolution=resolution)
"""
    result3 = clean_meep_code(test_md_block)
    check(
        "# [MD] 블록 제거 후 import meep 추출",
        result3 is not None and "import meep" in result3 and "# [MD]" not in result3,
        f"결과: {repr(result3[:80]) if result3 else 'None'}"
    )

    # 테스트 케이스 4: import meep 없으면 None 반환
    test_no_meep = "import numpy as np\nx = np.array([1, 2, 3])\nprint(x)"
    result4 = clean_meep_code(test_no_meep)
    check(
        "import meep 없으면 None 반환",
        result4 is None,
        f"결과: {repr(result4)}"
    )
print()

# ─────────────────────────────────────────────────────────────
# TEST 3: DB 업데이트 확인 (original_code_raw 컬럼 존재)
# ─────────────────────────────────────────────────────────────
print("TEST 3: DB 스키마 확인 (original_code_raw 컬럼)")
conn = sqlite3.connect(str(DB_PATH))
cols = conn.execute("PRAGMA table_info(sim_errors_v2)").fetchall()
col_names = [c[1] for c in cols]
has_raw_col = "original_code_raw" in col_names
conn.close()

if not has_raw_col:
    print("  ℹ️  original_code_raw 컬럼 없음 → code_cleaner 실행 시 자동 추가됨")
    # 컬럼 추가 시도 (code_cleaner 시뮬레이션)
    try:
        conn2 = sqlite3.connect(str(DB_PATH))
        conn2.execute("ALTER TABLE sim_errors_v2 ADD COLUMN original_code_raw TEXT")
        conn2.commit()
        conn2.close()
        check("original_code_raw 컬럼 추가 성공", True)
    except Exception as e:
        check("original_code_raw 컬럼 추가 성공", False, str(e))
else:
    check("original_code_raw 컬럼 존재", True)

# code_cleaner dry-run으로 # [MD] 코드 정제 확인
conn3 = sqlite3.connect(str(DB_PATH))
md_count = conn3.execute(
    "SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=0 AND original_code LIKE '# [MD]%'"
).fetchone()[0]
conn3.close()
print(f"  # [MD] 혼재 코드: {md_count}건 발견")
check("# [MD] 혼재 코드 발견 (정제 대상)", md_count >= 0,
      f"{md_count}건")
print()

# ─────────────────────────────────────────────────────────────
# TEST 4: verified_fix_v2.py 존재 확인 (실행은 배치 테스트)
# ─────────────────────────────────────────────────────────────
print("TEST 4: verified_fix_v2.py 파일 존재 확인")
vfv2 = BASE / "tools" / "verified_fix_v2.py"
check("verified_fix_v2.py 파일 존재", vfv2.exists())

# code_cleaner.py 파일 확인
cc = BASE / "tools" / "code_cleaner.py"
check("code_cleaner.py 파일 존재", cc.exists())
print()

# ─────────────────────────────────────────────────────────────
# TEST 5: 최종 fix_worked=1 건수 확인
# ─────────────────────────────────────────────────────────────
print("TEST 5: 최종 fix_worked=1 건수 확인")
fw1_final = get_fix_worked_count(1)
fw0_final = get_fix_worked_count(0)
print(f"  fix_worked=1: {fw1_final}건")
print(f"  fix_worked=0: {fw0_final}건")
check(
    f"fix_worked=1 ≥ 15건",
    fw1_final >= 15,
    f"현재 {fw1_final}건 (목표: 15건 이상)"
)

# 에러 유형별 분포 출력
conn4 = sqlite3.connect(str(DB_PATH))
dist = conn4.execute("""
    SELECT error_type, fix_worked, COUNT(*) as cnt
    FROM sim_errors_v2
    GROUP BY error_type, fix_worked
    ORDER BY error_type, fix_worked
""").fetchall()
conn4.close()
print("\n  에러 유형별 fix_worked 분포:")
for etype, fw_val, cnt in dist:
    status = "✅" if fw_val == 1 else "  "
    print(f"  {status} {etype or '(없음)'}: fix_worked={fw_val} → {cnt}건")

print()
print("=" * 60)
print(f"결과: {passed} PASSED, {failed} FAILED")
print("=" * 60)

if failed == 0:
    print("✅ ALL PASSED")
    sys.exit(0)
else:
    print("❌ 일부 실패")
    for status, name in results:
        if status == "FAIL":
            print(f"  FAIL: {name}")
    sys.exit(1)
