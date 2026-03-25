# -*- coding: utf-8 -*-
"""
test_live_pipeline.py — Live Run 파이프라인 통합 테스트
=======================================================
실행:
  python -X utf8 tools/test_live_pipeline.py
"""
import sys, json, sqlite3, subprocess
from pathlib import Path

# 경로 설정
TOOLS_DIR = Path(__file__).parent
BASE = TOOLS_DIR.parent
DB_PATH = BASE / "db" / "knowledge.db"
sys.path.insert(0, str(BASE / "api"))
sys.path.insert(0, str(TOOLS_DIR))

# ──────────────────────────────────────────────────────────────────────────────
# 테스트 유틸
# ──────────────────────────────────────────────────────────────────────────────

passed = 0
failed = 0
results = []

def test(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ PASS: {name}")
        results.append(("PASS", name, detail))
    else:
        failed += 1
        print(f"  ❌ FAIL: {name} {detail}")
        results.append(("FAIL", name, detail))
    return condition


# ──────────────────────────────────────────────────────────────────────────────
# TEST 1: data_auditor — audit_report.json 생성
# ──────────────────────────────────────────────────────────────────────────────

def test1_data_auditor():
    print("\n" + "=" * 60)
    print("TEST 1: data_auditor — audit_report.json 생성")
    print("=" * 60)

    import data_auditor
    report_path = TOOLS_DIR / "audit_report.json"

    # 이전 리포트 삭제
    if report_path.exists():
        report_path.unlink()

    try:
        report = data_auditor.run_audit()
        ok1 = test("audit_report.json 생성됨", report_path.exists())
        ok2 = test(
            "examples runnable 1건 이상",
            report.get("examples", {}).get("runnable_count", 0) >= 1,
            f"(runnable_count={report.get('examples', {}).get('runnable_count', 0)})"
        )
        ok3 = test(
            "sim_errors 분석 완료",
            report.get("sim_errors", {}).get("total", 0) >= 0,
            f"(total={report.get('sim_errors', {}).get('total', 0)})"
        )
        return ok1 and ok2 and ok3
    except Exception as e:
        test("data_auditor 실행 성공", False, str(e))
        return False


# ──────────────────────────────────────────────────────────────────────────────
# TEST 2: live_runner — 정상 MEEP 코드 실행
# ──────────────────────────────────────────────────────────────────────────────

def test2_live_runner_success():
    print("\n" + "=" * 60)
    print("TEST 2: live_runner — 정상 MEEP 코드 실행 (status=success)")
    print("=" * 60)

    from live_runner import run_code

    safe_code = """
import meep as mp
resolution = 10
cell = mp.Vector3(16, 0, 0)
pml = [mp.PML(1.0)]
src = mp.Source(mp.GaussianSource(1.0, fwidth=0.2), component=mp.Ez, center=mp.Vector3(-6))
sim = mp.Simulation(cell_size=cell, boundary_layers=pml, sources=[src], resolution=resolution)
flux = sim.add_flux(1.0, 0, 1, mp.FluxRegion(center=mp.Vector3(6)))
sim.run(until=30)
t = mp.get_fluxes(flux)[0]
print(f"[RESULT] T = {t:.4f}")
"""

    try:
        result = run_code(safe_code, timeout=120)
        print(f"  Status: {result.status}, Time: {result.run_time_sec}s")
        if result.stdout:
            print(f"  stdout (last 200): ...{result.stdout[-200:]}")
        if result.stderr and result.status != "success":
            print(f"  stderr (first 300): {result.stderr[:300]}")

        ok1 = test("status == success", result.status == "success",
                   f"(got: {result.status})")
        ok2 = test("run_time_sec > 0", result.run_time_sec > 0,
                   f"(got: {result.run_time_sec})")
        return ok1
    except Exception as e:
        test("live_runner 실행 성공", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ──────────────────────────────────────────────────────────────────────────────
# TEST 3: live_runner — eig_band=0 에러 코드 캡처
# ──────────────────────────────────────────────────────────────────────────────

def test3_live_runner_error():
    print("\n" + "=" * 60)
    print("TEST 3: live_runner — eig_band=0 에러 코드 → 에러 캡처")
    print("=" * 60)

    from live_runner import run_code

    error_code = """
import meep as mp
resolution = 10
cell = mp.Vector3(16, 8, 0)
pml = [mp.PML(1.0)]
src = mp.EigenModeSource(
    mp.GaussianSource(1.0, fwidth=0.2),
    center=mp.Vector3(-5),
    size=mp.Vector3(0, 6, 0),
    eig_band=0
)
sim = mp.Simulation(cell_size=cell, boundary_layers=pml, sources=[src], resolution=resolution)
sim.run(until=20)
"""

    try:
        result = run_code(error_code, timeout=60)
        print(f"  Status: {result.status}")
        print(f"  Error type: {result.error_type}")
        if result.stderr:
            print(f"  stderr (first 300): {result.stderr[:300]}")

        ok1 = test(
            "status == error (에러 캡처됨)",
            result.status == "error",
            f"(got: {result.status})"
        )
        ok2 = test(
            "error_type 분류됨",
            bool(result.error_type),
            f"(got: '{result.error_type}')"
        )
        return ok1
    except Exception as e:
        test("eig_band=0 에러 캡처", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ──────────────────────────────────────────────────────────────────────────────
# TEST 4: MPI deadlock 위험 코드 → 실행 안 함
# ──────────────────────────────────────────────────────────────────────────────

def test4_mpi_deadlock_risk():
    print("\n" + "=" * 60)
    print("TEST 4: MPI deadlock HIGH RISK → status=mpi_deadlock_risk (실행 안 함)")
    print("=" * 60)

    from live_runner import run_code

    # sys.exit() + mpirun 패턴 → HIGH RISK
    risky_code = """
import meep as mp
import sys

resolution = 10
cell = mp.Vector3(16, 0, 0)
pml = [mp.PML(1.0)]

sim = mp.Simulation(cell_size=cell, boundary_layers=pml, resolution=resolution)

result = sim.get_field_point(mp.Ez, mp.Vector3(0))
if result is None:
    sys.exit(1)

print("done")
"""

    try:
        result = run_code(risky_code, timeout=60)
        print(f"  Status: {result.status}")
        print(f"  mpi_check risk_level: {result.mpi_check.get('risk_level', 'N/A')}")

        ok = test(
            "status == mpi_deadlock_risk (HIGH RISK 차단됨)",
            result.status == "mpi_deadlock_risk",
            f"(got: {result.status}, risk={result.mpi_check.get('risk_level','?')})"
        )
        return ok
    except Exception as e:
        test("MPI deadlock 감지", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ──────────────────────────────────────────────────────────────────────────────
# TEST 5: error_collector — DB 저장 확인
# ──────────────────────────────────────────────────────────────────────────────

def test5_error_collector():
    print("\n" + "=" * 60)
    print("TEST 5: error_collector — live_runs DB 저장 확인")
    print("=" * 60)

    from live_runner import run_code, RunResult
    from error_collector import collect, migrate_db

    # DB 마이그레이션 먼저
    migrate_db()

    # 간단한 성공 코드로 테스트
    test_code = """
import meep as mp
resolution = 5
cell = mp.Vector3(4, 0, 0)
sim = mp.Simulation(cell_size=cell, resolution=resolution)
sim.run(until=5)
print("[RESULT] T = 0.9500")
"""

    try:
        # 실행
        run_result = run_code(test_code, timeout=60)
        print(f"  실행 결과: status={run_result.status}")

        # 저장 전 카운트
        conn = sqlite3.connect(str(DB_PATH))
        before_count = conn.execute("SELECT COUNT(*) FROM live_runs").fetchone()[0]
        conn.close()

        # 저장
        lr_id = collect(
            code=test_code,
            run_result=run_result,
            source="test",
            source_ref="test_collector_001",
        )
        print(f"  live_runs.id = {lr_id}")

        # 저장 후 카운트
        conn = sqlite3.connect(str(DB_PATH))
        after_count = conn.execute("SELECT COUNT(*) FROM live_runs").fetchone()[0]
        row = conn.execute(
            "SELECT id, status, source FROM live_runs WHERE id = ?", (lr_id,)
        ).fetchone() if lr_id > 0 else None
        conn.close()

        ok1 = test(
            "live_runs ID 반환됨",
            lr_id > 0,
            f"(got: {lr_id})"
        )
        ok2 = test(
            "live_runs 1건 삽입됨 (or 중복 처리됨)",
            after_count >= before_count,
            f"(before={before_count}, after={after_count})"
        )
        ok3 = test(
            "저장된 레코드 확인",
            row is not None,
            f"(row: {row})"
        )
        return ok1 and ok2
    except Exception as e:
        test("error_collector 실행", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ──────────────────────────────────────────────────────────────────────────────
# TEST 6: batch_live_runner --dry-run
# ──────────────────────────────────────────────────────────────────────────────

def test6_batch_dry_run():
    print("\n" + "=" * 60)
    print("TEST 6: batch_live_runner --dry-run → 목록 출력 확인")
    print("=" * 60)

    from batch_live_runner import run_batch

    try:
        stats = run_batch(
            source="examples",
            limit=5,
            dry_run=True,
        )
        print(f"  stats: {stats}")

        ok = test(
            "dry-run 실행 완료 (total >= 0)",
            isinstance(stats, dict) and stats.get("total", -1) >= 0,
            f"(total={stats.get('total', 'N/A')})"
        )
        return ok
    except Exception as e:
        test("batch_live_runner dry-run 실행", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("KB Live Pipeline — 통합 테스트 시작")
    print("=" * 60)

    # 컨테이너 상태 확인
    try:
        r = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", "meep-pilot-worker"],
            capture_output=True, text=True, timeout=10
        )
        container_running = r.stdout.strip() == "true"
    except Exception:
        container_running = False

    print(f"\n🐳 meep-pilot-worker 컨테이너 실행 중: {container_running}")
    if not container_running:
        print("⚠️  컨테이너가 실행 중이 아닙니다. TEST 2, 3은 실패할 수 있습니다.")

    # 테스트 실행
    test1_data_auditor()
    test2_live_runner_success()
    test3_live_runner_error()
    test4_mpi_deadlock_risk()
    test5_error_collector()
    test6_batch_dry_run()

    # 최종 결과
    total = passed + failed
    print(f"\n{'=' * 60}")
    print(f"테스트 결과: {passed}/{total} PASSED")
    print(f"{'=' * 60}")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED")
        sys.exit(0)
    else:
        print(f"\n❌ {failed}개 테스트 실패:")
        for status, name, detail in results:
            if status == "FAIL":
                print(f"  - {name} {detail}")
        sys.exit(1)
