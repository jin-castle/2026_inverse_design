"""
파이프라인 순차 실행:
  1. Solution Structurer 완료 대기
  2. ErrorInjector 실행 (Docker 필요)
  3. DB 현황 리포트

실행: python tools/pipeline_runner.py
"""
import sqlite3, time, subprocess, sys
from pathlib import Path

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"


def get_structured_count():
    db = sqlite3.connect(DB_PATH)
    n = db.execute("SELECT COUNT(*) FROM sim_errors WHERE source='github_structured'").fetchone()[0]
    db.close()
    return n


def get_total():
    db = sqlite3.connect(DB_PATH)
    total = db.execute("SELECT COUNT(*) FROM sim_errors").fetchone()[0]
    verified = db.execute("SELECT COUNT(*) FROM sim_errors WHERE fix_worked=1").fetchone()[0]
    db.close()
    return total, verified


def wait_for_structurer(check_interval=30, stable_rounds=3):
    """카운트가 stable_rounds번 연속으로 변화 없으면 완료로 판단"""
    print("=== Phase 1: Solution Structurer 완료 대기 ===")
    prev = get_structured_count()
    stable = 0
    while True:
        time.sleep(check_interval)
        curr = get_structured_count()
        total, verified = get_total()
        print(f"  github_structured: {curr}개 | sim_errors 총 {total}개 (검증됨 {verified}개)")
        if curr == prev:
            stable += 1
            if stable >= stable_rounds:
                print(f"  → {check_interval * stable_rounds}초 동안 변화 없음. 완료로 판단.")
                break
        else:
            stable = 0
        prev = curr
    print(f"  최종 github_structured: {curr}개\n")
    return curr


def run_error_injector():
    """Phase 2: ErrorInjector 실행"""
    print("=== Phase 2: ErrorInjector 실행 ===")

    # Docker 컨테이너 확인
    r = subprocess.run(
        ["docker", "inspect", "--format={{.State.Running}}", "meep-pilot-worker"],
        capture_output=True, text=True
    )
    if r.stdout.strip() != "true":
        print("  ⚠️  meep-pilot-worker 컨테이너가 실행 중이 아닙니다.")
        print("  → ErrorInjector 건너뜀. Docker 시작 후 수동 실행:")
        print("     python tools/error_injector.py --limit 50")
        return 0

    print("  Docker 컨테이너 확인됨. ErrorInjector 실행 중...")
    result = subprocess.run(
        [sys.executable, str(BASE / "tools" / "error_injector.py"), "--limit", "50"],
        cwd=str(BASE),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600,
    )
    print(result.stdout[-2000:] if result.stdout else "(no output)")
    if result.returncode != 0:
        print(f"  오류:\n{result.stderr[-500:]}")
    return result.returncode


def final_report():
    """최종 DB 현황"""
    db = sqlite3.connect(DB_PATH)
    total = db.execute("SELECT COUNT(*) FROM sim_errors").fetchone()[0]
    verified = db.execute("SELECT COUNT(*) FROM sim_errors WHERE fix_worked=1").fetchone()[0]
    by_source = db.execute(
        "SELECT source, COUNT(*) FROM sim_errors GROUP BY source ORDER BY COUNT(*) DESC"
    ).fetchall()
    by_type = db.execute(
        "SELECT error_type, COUNT(*) FROM sim_errors GROUP BY error_type ORDER BY COUNT(*) DESC LIMIT 10"
    ).fetchall()
    db.close()

    print("\n=== 최종 DB 현황 ===")
    print(f"  sim_errors: {total}개 (검증됨: {verified}개)")
    print("  소스별:")
    for s, c in by_source:
        print(f"    {s}: {c}개")
    print("  에러 타입별:")
    for t, c in by_type:
        print(f"    {t}: {c}개")
    print()

    if total >= 500:
        print("✅ 목표 달성! sim_errors 500개+ 확보")
    else:
        print(f"⏳ 목표까지 {500 - total}개 더 필요")


if __name__ == "__main__":
    # Phase 1: Solution Structurer 완료 대기
    wait_for_structurer(check_interval=30, stable_rounds=3)

    # Phase 2: ErrorInjector
    run_error_injector()

    # 최종 리포트
    final_report()

    print("\n다음 단계: MARL 실제 시뮬레이션")
    print("  cd C:\\Users\\user\\projects\\photonics-agent")
    print("  python marl_orchestrator.py workspace/projects/PROJ-002/code/forward_sim.py --project PROJ-002 --device mode_converter")
