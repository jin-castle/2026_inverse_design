"""
test_github_preprocess.py
GitHub Issues 전처리 + research_notes KB 반영 검증 테스트.
6개 테스트 케이스.
"""

import sys
import json
import sqlite3
import subprocess
from pathlib import Path

BASE = Path(__file__).parent
DB_PATH = BASE.parent / "db" / "knowledge.db"
RUNNABLE_JSON = BASE / "runnable_issues.json"
PREPROCESSOR = BASE / "github_preprocessor.py"
INGEST_SCRIPT = BASE / "ingest_research_notes.py"


def run_test(name: str, fn):
    """테스트 실행 래퍼."""
    try:
        result = fn()
        if result:
            print(f"[PASS] {name}")
            return True
        else:
            print(f"[FAIL] {name}")
            return False
    except Exception as e:
        print(f"[FAIL] {name} -- Exception: {e}")
        return False


def test1_preprocessor_runs():
    """TEST 1: github_preprocessor.py 실행 -> runnable_issues.json 생성."""
    result = subprocess.run(
        [sys.executable, str(PREPROCESSOR)],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        print(f"  stderr: {result.stderr[:300]}")
        return False
    if not RUNNABLE_JSON.exists():
        print("  runnable_issues.json not found")
        return False
    # JSON 유효성
    with open(RUNNABLE_JSON, encoding="utf-8") as f:
        data = json.load(f)
    if "summary" not in data:
        print("  summary key missing")
        return False
    print(f"  summary: {data['summary']}")
    return True


def test2_runnable_or_patchable_found():
    """TEST 2: runnable 1건 이상 OR patchable 5건 이상."""
    with open(RUNNABLE_JSON, encoding="utf-8") as f:
        data = json.load(f)
    runnable = data["summary"]["runnable"]
    patchable = data["summary"]["patchable"]
    print(f"  runnable={runnable}, patchable={patchable}")
    return runnable >= 1 or patchable >= 5


def test3_common_import_patch():
    """TEST 3: patchable 코드에 common_import 치환 적용 확인."""
    # github_preprocessor의 함수를 직접 테스트
    sys.path.insert(0, str(BASE))
    from github_preprocessor import patch_code, apply_common_fixes

    # common import 치환 테스트
    test_code = "from common import *\n\nsim = mp.Simulation(cell_size=mp.Vector3(1,1,0), resolution=10)\nsim.run(until=10)"
    patched, patches = patch_code(test_code)
    
    if "common_import" not in patches and "from" not in patches and not any("common" in p for p in patches):
        # patches에 common 관련이 없어도, 코드에 치환이 적용됐는지 확인
        pass
    
    if "from common import *" in patched:
        print(f"  from common still present in patched code!")
        return False
    if "import meep as mp" not in patched:
        print(f"  import meep not found after patch: {patched[:200]}")
        return False
    print(f"  patches applied: {patches}")
    print(f"  patched code (first 200): {patched[:200]}")
    return True


def test4_score_without_meep():
    """TEST 4: runability_score() 정확도 - import meep 없는 코드 -> score < 70."""
    sys.path.insert(0, str(BASE))
    from github_preprocessor import runability_score

    # meep import 없는 코드
    code_no_meep = """
import numpy as np
x = np.linspace(0, 10, 100)
y = np.sin(x)
print(y)
"""
    result = runability_score(code_no_meep)
    score = result["score"]
    print(f"  score without meep: {score} (flags: {result['flags']})")
    if score >= 70:
        print(f"  score too high ({score}) for code without meep!")
        return False

    # meep import 있는 완전한 코드
    code_with_meep = """
import meep as mp

sim = mp.Simulation(
    cell_size=mp.Vector3(1,1,0),
    resolution=10,
)
sim.run(until=10)
"""
    result2 = runability_score(code_with_meep)
    score2 = result2["score"]
    print(f"  score with meep: {score2} (flags: {result2['flags']})")
    return score < 70 and score2 >= 70


def test5_ingest_research_notes():
    """TEST 5: ingest_research_notes.py -> sim_errors_v2에 8건 삽입 확인."""
    result = subprocess.run(
        [sys.executable, str(INGEST_SCRIPT)],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        print(f"  stderr: {result.stderr[:300]}")
        return False

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE source='research_notes'")
    count = cur.fetchone()[0]
    conn.close()
    
    print(f"  research_notes count: {count}")
    return count == 8


def test6_research_notes_quality():
    """TEST 6: 삽입된 8건 모두 fix_worked=1, physics_cause 있음."""
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    
    # fix_worked=1인 것
    cur.execute("""
        SELECT COUNT(*) FROM sim_errors_v2 
        WHERE source='research_notes' AND fix_worked=1
    """)
    fw_count = cur.fetchone()[0]
    
    # physics_cause != NULL
    cur.execute("""
        SELECT COUNT(*) FROM sim_errors_v2 
        WHERE source='research_notes' AND physics_cause IS NOT NULL AND physics_cause != ''
    """)
    pc_count = cur.fetchone()[0]
    
    # 샘플 출력
    cur.execute("""
        SELECT error_type, fix_worked, physics_cause
        FROM sim_errors_v2 WHERE source='research_notes'
        LIMIT 3
    """)
    rows = cur.fetchall()
    for r in rows:
        print(f"  type={r[0]}, fix_worked={r[1]}, physics_cause[:60]={str(r[2])[:60]}")
    
    conn.close()
    
    print(f"  fix_worked=1: {fw_count}/8, physics_cause있음: {pc_count}/8")
    return fw_count == 8 and pc_count == 8


def main():
    print("=" * 60)
    print("GitHub Issues 전처리 + research_notes KB 검증")
    print("=" * 60)

    tests = [
        ("TEST 1: github_preprocessor.py 실행 -> JSON 생성", test1_preprocessor_runs),
        ("TEST 2: runnable 1건+ OR patchable 5건+ 확인", test2_runnable_or_patchable_found),
        ("TEST 3: patchable 코드에 common_import 치환", test3_common_import_patch),
        ("TEST 4: runability_score() - meep 없는 코드 < 70", test4_score_without_meep),
        ("TEST 5: ingest_research_notes.py -> 8건 삽입", test5_ingest_research_notes),
        ("TEST 6: 8건 모두 fix_worked=1, physics_cause 있음", test6_research_notes_quality),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        print(f"\n{name}")
        if run_test(name, fn):
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"결과: {passed}/{len(tests)} 통과, {failed} 실패")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
