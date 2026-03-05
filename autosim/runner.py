"""
runner.py — autosim 패턴 실행 관리
컨테이너 8011f9a5b95c 내부에서 실행.

사용법:
  python runner.py           # 전체 실행 (기본 60s 타임아웃)
  python runner.py tier1     # 시각화 전용 (빠른 확인)
  python runner.py tier2     # 간단한 MEEP
  python runner.py NAME      # 특정 패턴 1개
"""
import subprocess, json, sys, time
from pathlib import Path

PYTHON       = "/home/js/miniconda/envs/pmp/bin/python"
PATTERNS_DIR = Path("/root/autosim/patterns")
RESULTS_DIR  = Path("/root/autosim/results")
SUMMARY_FILE = Path("/root/autosim/run_summary.json")

# 타임아웃 설정 (초)
TIMEOUT_MAP = {
    "tier1": 30,
    "tier2": 90,
    "tier3": 300,
    "all":   120,
}

# Tier 분류
TIER1_PREFIXES = [
    "plot_", "save_", "create_field_animation", "meep_visualization",
    "history_json", "output_directory", "array_metadata", "get_point_field",
    "setup_logging",
]
TIER2_PREFIXES = [
    "straight_waveguide", "bent_waveguide", "bend_flux", "pml_boundary",
    "materials_library", "material_dispersion", "geometry_cylinder",
    "cylinder_cross", "waveguide_source", "plane_wave", "gaussian_beam",
    "solve_cw", "stop_when",
]
TIER3_PREFIXES = [
    "adjoint_", "pipeline_", "AdamOptimizer", "MappedSpace", "WarmRestarter",
    "BacktrackingLine", "AdaptiveBeta", "MsoptBeta", "LinearBeta",
    "apply_conic", "apply_tanh",
]


def classify(name: str) -> str:
    for p in TIER1_PREFIXES:
        if name.startswith(p) or p in name:
            return "tier1"
    for p in TIER2_PREFIXES:
        if name.startswith(p) or p in name:
            return "tier2"
    for p in TIER3_PREFIXES:
        if name.startswith(p) or p in name:
            return "tier3"
    return "tier2"  # 기본값


def run_one(py_file: Path, timeout: int) -> dict:
    name = py_file.stem
    t0   = time.time()
    try:
        r = subprocess.run(
            [PYTHON, str(py_file)],
            capture_output=True, text=True,
            timeout=timeout,
            cwd="/root/autosim",
            env={**__import__("os").environ, "MPLBACKEND": "Agg"},
        )
        elapsed = time.time() - t0
        result_file = RESULTS_DIR / name / "result.json"
        if result_file.exists():
            return json.loads(result_file.read_text())
        if r.returncode == 0:
            return {"pattern": name, "status": "ok", "elapsed_s": round(elapsed,2), "outputs": []}
        else:
            stderr_tail = r.stderr[-400:].strip() if r.stderr else ""
            return {"pattern": name, "status": "error", "elapsed_s": round(elapsed,2),
                    "error": stderr_tail or r.stdout[-200:]}
    except subprocess.TimeoutExpired:
        return {"pattern": name, "status": "timeout", "elapsed_s": timeout,
                "error": f"Exceeded {timeout}s"}
    except Exception as e:
        return {"pattern": name, "status": "error", "elapsed_s": 0, "error": str(e)}


def run_batch(patterns, timeout, label=""):
    results = []
    ok = err = skip = 0
    total = len(patterns)
    for i, pf in enumerate(patterns, 1):
        name = pf.stem
        tier = classify(name)
        print(f"[{i:3d}/{total}] {name} ({tier})...", end=" ", flush=True)
        r = run_one(pf, timeout)
        results.append(r)
        st = r["status"]
        if st == "ok":
            ok   += 1; print(f"OK {r.get('elapsed_s',0):.1f}s")
        elif st == "timeout":
            skip += 1; print(f"TIMEOUT ({timeout}s)")
        else:
            err  += 1; print(f"FAIL: {str(r.get('error',''))[:80]}")

    print(f"\n{'='*60}")
    print(f"{'['+label+'] ' if label else ''}Results: {ok} OK / {err} FAIL / {skip} TIMEOUT / {total} total")
    print(f"{'='*60}\n")
    return results


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    all_patterns = sorted(PATTERNS_DIR.glob("*.py"))

    if not all_patterns:
        print(f"ERROR: No .py files found in {PATTERNS_DIR}")
        sys.exit(1)

    print(f"autosim runner — mode={mode}, {len(all_patterns)} patterns available\n")

    # 단일 패턴 실행
    if mode not in ("all", "tier1", "tier2", "tier3"):
        target = PATTERNS_DIR / f"{mode}.py"
        if not target.exists():
            print(f"ERROR: Pattern not found: {target}")
            sys.exit(1)
        r = run_one(target, timeout=120)
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return

    timeout = TIMEOUT_MAP.get(mode, 120)

    if mode == "tier1":
        patterns = [p for p in all_patterns if classify(p.stem) == "tier1"]
    elif mode == "tier2":
        patterns = [p for p in all_patterns if classify(p.stem) == "tier2"]
    elif mode == "tier3":
        patterns = [p for p in all_patterns if classify(p.stem) == "tier3"]
    else:
        patterns = all_patterns

    results = run_batch(patterns, timeout, label=mode)

    # 전체 요약 저장
    existing = []
    if SUMMARY_FILE.exists():
        try:
            existing = json.loads(SUMMARY_FILE.read_text())
        except Exception:
            existing = []

    # 새 결과로 업데이트 (같은 패턴은 덮어쓰기)
    merged = {r["pattern"]: r for r in existing}
    for r in results:
        merged[r["pattern"]] = r
    SUMMARY_FILE.write_text(json.dumps(list(merged.values()), indent=2, ensure_ascii=False))
    print(f"Summary saved → {SUMMARY_FILE}")

    # 실패 목록 출력
    fails = [r for r in results if r["status"] != "ok"]
    if fails:
        print(f"\n[실패 목록 - {len(fails)}개]")
        for r in fails:
            print(f"  {r['status']:8s} | {r['pattern']}")
            if r.get("error"):
                first_line = str(r["error"]).split("\n")[0][:100]
                print(f"           | {first_line}")


if __name__ == "__main__":
    main()
