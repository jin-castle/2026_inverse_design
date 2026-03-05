#!/usr/bin/env python3
"""
final_run.py — error/skip 패턴 최종 정리
Docker 8011f9a5b95c 내부에서 실행
"""
import subprocess, json, sys, time
from pathlib import Path

PYTHON       = "/home/js/miniconda/envs/pmp/bin/python"
PATTERNS_DIR = Path("/root/autosim/patterns")
SUMMARY_FILE = Path("/root/autosim/run_summary.json")

# 이미 실행된 결과 로드
existing = {}
if SUMMARY_FILE.exists():
    existing = {r["pattern"]: r for r in json.loads(SUMMARY_FILE.read_text())}

# 영구 SKIP 목록 (실행 불가능한 것들)
PERMANENT_SKIP = {
    "coupler_mode_decomposition":       "requires coupler.gds (not available)",
    "directional_coupler":              "requires coupler.gds (not available)",
    "mpb_bragg_bands":                  "requires mpb module (not installed in pmp env)",
    "mpb_tutorial_complete":            "requires mpb module (not installed in pmp env)",
    "waveguide_source_setup":           "requires h5topng (not installed)",
    "dft_field_monitor_3d":             "code fragment only - sim object not defined in snippet",
    "grating2d_triangular_lattice":     "simulation too slow (>300s)",
    "polarization_grating":             "simulation too slow (>300s)",
    "metasurface_lens":                 "simulation too slow (>300s)",
    "adjoint_filter_source":            "relative imports from within MEEP adjoint package",
    "adjoint_jax_integration":          "requires jax, parameterized (not installed in pmp)",
    "adjoint_level_set_grating":        "requires running as complete script with external deps",
    "adjoint_multilayer_optimization":  "module-level docstring-only code, no runnable logic",
    "adjoint_objective_functions":      "relative imports from within MEEP adjoint package",
    "pipeline_stage51_forward_simulation":  "depends on sim_fwd object from prior step",
    "pipeline_stage52_adjoint_simulation":  "depends on simulation state from prior step",
    "pipeline_stage53_gradient_map":        "depends on opt object from prior step",
    "pipeline_stage54_beta_scheduling":     "depends on x0 optimization state from prior step",
    "pipeline_stage55_filter":              "depends on optimization state from prior step",
    "adjoint_cylindrical":              "empty try block from MEEP package import structure",
    "adjoint_solver_basics":            "empty try block from MEEP package import structure",
}


def run_one(py_file: Path, timeout: int = 120) -> dict:
    name = py_file.stem
    t0 = time.time()
    try:
        r = subprocess.run(
            [PYTHON, str(py_file)],
            capture_output=True, text=True,
            timeout=timeout,
            cwd="/root/autosim",
            env={**__import__("os").environ, "MPLBACKEND": "Agg"},
        )
        elapsed = time.time() - t0
        if r.returncode == 0:
            return {"pattern": name, "status": "ok", "elapsed_s": round(elapsed, 2), "outputs": [], "error": None}
        else:
            err = (r.stderr[-500:] if r.stderr else r.stdout[-200:]).strip()
            return {"pattern": name, "status": "error", "elapsed_s": round(elapsed, 2), "error": err}
    except subprocess.TimeoutExpired:
        return {"pattern": name, "status": "timeout", "elapsed_s": timeout, "error": f"Exceeded {timeout}s"}
    except Exception as e:
        return {"pattern": name, "status": "error", "elapsed_s": 0, "error": str(e)}


# 재실행 대상: 현재 ok가 아닌 것 (permanent skip 제외)
to_run = []
for pf in sorted(PATTERNS_DIR.glob("*.py")):
    name = pf.stem
    if name in PERMANENT_SKIP:
        continue
    prev = existing.get(name, {})
    if prev.get("status") == "ok":
        continue
    to_run.append(pf)

print(f"=== 최종 재실행: {len(to_run)}개 ===\n")
results_new = []
ok = err = 0

for i, pf in enumerate(to_run, 1):
    name = pf.stem
    prev_status = existing.get(name, {}).get("status", "new")
    timeout = 180 if "adjoint_solver_complete" in name else 120
    print(f"[{i:2d}/{len(to_run)}] {name} (prev={prev_status})...", end=" ", flush=True)
    r = run_one(pf, timeout)
    results_new.append(r)
    if r["status"] == "ok":
        ok += 1; print(f"OK {r['elapsed_s']:.1f}s")
    else:
        err += 1; print(f"FAIL: {str(r.get('error',''))[:80]}")

# permanent skip 업데이트
for name, reason in PERMANENT_SKIP.items():
    existing[name] = {"pattern": name, "status": "skip", "elapsed_s": 0, "outputs": [], "error": None, "skip_reason": reason}

# 결과 병합
for r in results_new:
    existing[r["pattern"]] = r

SUMMARY_FILE.write_text(json.dumps(list(existing.values()), indent=2, ensure_ascii=False))
print(f"\n결과: {ok} OK / {err} FAIL / {len(to_run)} total")
print("Summary updated.")

# 최종 통계
from collections import Counter
counts = Counter(r["status"] for r in existing.values())
print(f"\n=== 최종 통계 ===")
print(f"OK: {counts['ok']}  ERROR: {counts['error']}  TIMEOUT: {counts['timeout']}  SKIP: {counts['skip']}  Total: {sum(counts.values())}")
fails = [r for r in existing.values() if r["status"] == "error"]
if fails:
    print(f"\n[남은 에러 {len(fails)}개]")
    for r in fails:
        print(f"  {r['pattern']}: {str(r.get('error',''))[:80]}")
