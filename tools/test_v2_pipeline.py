# -*- coding: utf-8 -*-
"""
test_v2_pipeline.py — sim_errors_v2 파이프라인 검증 테스트
=============================================================
실행: python -X utf8 tools/test_v2_pipeline.py
"""
import json, sqlite3, sys, requests, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
sys.path.insert(0, str(Path(__file__).parent))

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []


def check(name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    msg = f"  {status}: {name}"
    if detail:
        msg += f"\n         {detail}"
    print(msg)
    results.append((name, condition))
    return condition


# ──────────────────────────────────────────────────────────────────────────────
# TEST 1: sim_errors_v2 테이블 존재 + 인덱스 6개
# ──────────────────────────────────────────────────────────────────────────────
print("\n[TEST 1] sim_errors_v2 테이블 + 인덱스")
conn = sqlite3.connect(str(DB_PATH))
try:
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sim_errors_v2'"
    ).fetchall()]
    check("sim_errors_v2 테이블 존재", len(tables) == 1)

    indexes = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='sim_errors_v2'"
    ).fetchall()]
    check(f"인덱스 6개 존재 (현재 {len(indexes)}개)",
          len(indexes) >= 6,
          f"인덱스: {indexes}")
except Exception as e:
    check("TEST 1 실행", False, str(e))
finally:
    conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# TEST 2: collect_v2() 정상 코드 → v2 저장 안 됨
# ──────────────────────────────────────────────────────────────────────────────
print("\n[TEST 2] collect_v2() 정상 코드 → sim_errors_v2 저장 안 됨")
from error_collector import collect_v2
from live_runner import RunResult

NORMAL_CODE = """\
import meep as mp
resolution = 10
cell = mp.Vector3(16, 8, 0)
geometry = [mp.Block(mp.Vector3(mp.inf, 1, mp.inf), center=mp.Vector3(),
                     material=mp.Medium(epsilon=12))]
sources = [mp.Source(mp.GaussianSource(frequency=0.15, fwidth=0.1),
                     component=mp.Ez, center=mp.Vector3(-7))]
sim = mp.Simulation(cell_size=cell, resolution=resolution,
                    geometry=geometry, sources=sources)
sim.run(until=10)
print("OK")
"""

normal_result = RunResult(
    status="success",
    stdout="OK\n",
    stderr="",
    error_type="",
    error_message="",
    run_time_sec=1.5,
    T_value=0.85,
    R_value=0.10,
)

before_count = sqlite3.connect(str(DB_PATH)).execute(
    "SELECT COUNT(*) FROM sim_errors_v2"
).fetchone()[0]
v2_id = collect_v2(NORMAL_CODE, normal_result, source="test", source_ref="test_normal")
after_count = sqlite3.connect(str(DB_PATH)).execute(
    "SELECT COUNT(*) FROM sim_errors_v2"
).fetchone()[0]

check("정상 코드 → v2 저장 안 됨", v2_id == 0,
      f"v2_id={v2_id}, before={before_count}, after={after_count}")


# ──────────────────────────────────────────────────────────────────────────────
# TEST 3: collect_v2() 에러 코드 → sim_errors_v2 저장
# ──────────────────────────────────────────────────────────────────────────────
print("\n[TEST 3] collect_v2() 에러 코드 → sim_errors_v2 저장")

ERROR_CODE = """\
import meep as mp
resolution = 20
cell = mp.Vector3(16, 8, 0)
fcen = 0.645  # ~1550nm
sources = [mp.EigenmodeSource(mp.GaussianSource(frequency=fcen, fwidth=0.05),
                               size=mp.Vector3(0, 6, 0), center=mp.Vector3(-7),
                               eig_band=1, direction=mp.X)]
sim = mp.Simulation(cell_size=cell, resolution=resolution,
                    geometry=[], sources=sources,
                    boundary_layers=[mp.PML(1.5)])
sim.run(until=200)
"""

error_result = RunResult(
    status="error",
    stdout="",
    stderr='Traceback (most recent call last):\n  File "test.py", line 9, in <module>\n    sim.run(until=200)\nAttributeError: Simulation object has no attribute run_mode\n',
    error_type="AttributeError",
    error_message="Simulation object has no attribute run_mode",
    run_time_sec=0.3,
    T_value=None,
    R_value=None,
)

# 중복 방지용 unique code
import time as _t
ERROR_CODE_U = ERROR_CODE + f"\n# unique {_t.time()}"

v2_id3 = collect_v2(ERROR_CODE_U, error_result, source="test", source_ref="test_error_code")
check("에러 코드 → sim_errors_v2 저장됨", v2_id3 > 0, f"v2_id={v2_id3}")

if v2_id3 > 0:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM sim_errors_v2 WHERE id = ?", (v2_id3,)).fetchone()
    conn.close()

    check("error_class = code_error", row["error_class"] == "code_error",
          f"실제: {row['error_class']}")
    check("run_mode = forward", row["run_mode"] == "forward",
          f"실제: {row['run_mode']}")

    rcc = json.loads(row["root_cause_chain"] or "[]")
    check("root_cause_chain JSON 파싱 가능", isinstance(rcc, list) and len(rcc) > 0,
          f"len={len(rcc)}")


# ──────────────────────────────────────────────────────────────────────────────
# TEST 4: physics_error → T>100% → error_class="physics_error", symptom="T>100%"
# ──────────────────────────────────────────────────────────────────────────────
print("\n[TEST 4] collect_v2() physics_error → T>100%")

PHYS_CODE = """\
import meep as mp
resolution = 5  # too low
cell = mp.Vector3(16, 8, 0)
fcen = 0.645
sim = mp.Simulation(cell_size=cell, resolution=resolution)
sim.run(until=50)
# T = 1.25 measured
"""
PHYS_CODE_U = PHYS_CODE + f"\n# unique {_t.time()}"

phys_result = RunResult(
    status="success",
    stdout="T = 1.2500\n",
    stderr="",
    error_type="",
    error_message="",
    run_time_sec=2.0,
    T_value=1.25,
    R_value=0.0,
)

v2_id4 = collect_v2(PHYS_CODE_U, phys_result, source="test", source_ref="test_physics")
check("physics_error → sim_errors_v2 저장됨", v2_id4 > 0, f"v2_id={v2_id4}")

if v2_id4 > 0:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    row4 = conn.execute("SELECT * FROM sim_errors_v2 WHERE id = ?", (v2_id4,)).fetchone()
    conn.close()

    check("error_class = physics_error", row4["error_class"] == "physics_error",
          f"실제: {row4['error_class']}")
    check("symptom = T>100%", row4["symptom"] == "T>100%",
          f"실제: {row4['symptom']}")


# ──────────────────────────────────────────────────────────────────────────────
# TEST 5: /api/diagnose 응답에 sim_errors_v2 결과 포함
# (fix_worked=1인 v2 레코드가 있어야 검색 결과에 나옴 — 없으면 Skip)
# ──────────────────────────────────────────────────────────────────────────────
print("\n[TEST 5] /api/diagnose 응답 확인")

API_URL = "http://localhost:8765"

try:
    resp = requests.post(
        f"{API_URL}/api/diagnose",
        json={
            "code": ERROR_CODE,
            "error": "AttributeError: Simulation object has no attribute run_mode",
        },
        timeout=15,
    )
    if resp.status_code == 200:
        data = resp.json()
        check("/api/diagnose 응답 OK", True, f"status={resp.status_code}")

        # sim_errors_v2 타입이 있는지 확인 (fix_worked=1 레코드 없으면 없을 수 있음)
        all_types = [r.get("type") for r in data.get("db_results", [])]
        has_v2 = "sim_error_v2" in all_types
        # fix_worked=1 v2 레코드 수 확인
        v2_verified = sqlite3.connect(str(DB_PATH)).execute(
            "SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=1"
        ).fetchone()[0]
        if v2_verified > 0:
            check("sim_error_v2 타입 결과 포함", has_v2, f"타입 목록: {all_types[:5]}")
        else:
            print(f"  ⚠️  SKIP: fix_worked=1 v2 레코드 없음 (현재 {v2_verified}건) → 검색 결과에 나오지 않음")
            results.append(("TEST 5 sim_error_v2 검색 (v2 검증 레코드 없어 skip)", True))
    else:
        check(f"/api/diagnose 응답 OK", False, f"status={resp.status_code}, body={resp.text[:200]}")
except Exception as e:
    print(f"  ⚠️  API 연결 실패: {e}")
    results.append(("TEST 5 API 연결", False))


# ──────────────────────────────────────────────────────────────────────────────
# TEST 6: live_runs 배치 실행 후 저장 건수 확인
# ──────────────────────────────────────────────────────────────────────────────
print("\n[TEST 6] live_runs 저장 건수 확인")
conn = sqlite3.connect(str(DB_PATH))
live_count = conn.execute("SELECT COUNT(*) FROM live_runs").fetchone()[0]
v2_count = conn.execute("SELECT COUNT(*) FROM sim_errors_v2").fetchone()[0]
conn.close()

check(f"live_runs 1건+ 저장됨 (현재 {live_count}건)", live_count >= 1,
      f"live_runs.count = {live_count}")
print(f"  ℹ️  sim_errors_v2 현재: {v2_count}건")


# ──────────────────────────────────────────────────────────────────────────────
# 최종 결과
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"결과: {passed}/{total} PASSED")
if passed == total:
    print("🎉 ALL TESTS PASSED")
else:
    print("⚠️  일부 테스트 실패:")
    for name, ok in results:
        if not ok:
            print(f"  ❌ {name}")
print("=" * 60)
sys.exit(0 if passed == total else 1)
