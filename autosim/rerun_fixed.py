#!/usr/bin/env python3
"""
rerun_fixed.py - 이전에 skip됐던 패턴 중 이제 고쳐진 것들 + 미테스트 패턴 실행
Docker 8011f9a5b95c 내부에서 실행
"""
import subprocess, json, sys, time
from pathlib import Path

PYTHON       = "/home/js/miniconda/envs/pmp/bin/python"
PATTERNS_DIR = Path("/root/autosim/patterns")
SUMMARY_FILE = Path("/root/autosim/run_summary.json")

# 이미 실행된 패턴 목록 (summary에서)
existing = {}
if SUMMARY_FILE.exists():
    try:
        existing = {r["pattern"]: r for r in json.loads(SUMMARY_FILE.read_text())}
    except Exception:
        existing = {}

# 영구 skip (deps 없음, 불가능)
PERMANENT_SKIP = {
    "coupler_mode_decomposition": "requires coupler.gds",
    "directional_coupler": "requires coupler.gds",
    "mpb_bragg_bands": "requires mpb module",
    "mpb_tutorial_complete": "requires mpb module",
    "waveguide_source_setup": "requires h5topng",
    "dft_field_monitor_3d": "code fragment only - sim not defined",
    "grating2d_triangular_lattice": "simulation too slow (>300s)",
    "polarization_grating": "simulation too slow (>300s)",
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
            stderr_tail = (r.stderr[-500:] if r.stderr else r.stdout[-200:]).strip()
            return {"pattern": name, "status": "error", "elapsed_s": round(elapsed, 2), "error": stderr_tail}
    except subprocess.TimeoutExpired:
        return {"pattern": name, "status": "timeout", "elapsed_s": timeout, "error": f"Exceeded {timeout}s"}
    except Exception as e:
        return {"pattern": name, "status": "error", "elapsed_s": 0, "error": str(e)}


all_patterns = sorted(PATTERNS_DIR.glob("*.py"))

# 실행 대상: OK가 아닌 것 + 아직 안 한 것 (permanent skip 제외)
to_run = []
for pf in all_patterns:
    name = pf.stem
    if name in PERMANENT_SKIP:
        continue
    prev = existing.get(name)
    if prev and prev["status"] == "ok":
        continue  # 이미 OK는 스킵
    to_run.append(pf)

print(f"=== 재실행 대상: {len(to_run)}개 패턴 ===\n")

results_new = []
ok = err = timeout_c = 0

for i, pf in enumerate(to_run, 1):
    name = pf.stem
    prev_status = existing.get(name, {}).get("status", "new")
    timeout = 300 if any(x in name for x in ["adjoint_solver_complete", "adjoint_jax", "adjoint_multilayer", "MsoptBeta", "metasurface", "waveguide_crossing"]) else 120
    print(f"[{i:2d}/{len(to_run)}] {name} (prev={prev_status}, timeout={timeout}s)...", end=" ", flush=True)
    r = run_one(pf, timeout)
    results_new.append(r)
    st = r["status"]
    if st == "ok":
        ok += 1
        print(f"OK {r['elapsed_s']:.1f}s")
    elif st == "timeout":
        timeout_c += 1
        print(f"TIMEOUT")
    else:
        err += 1
        first_err = str(r.get("error", ""))[:100]
        print(f"FAIL: {first_err}")

print(f"\n{'='*60}")
print(f"결과: {ok} OK / {err} FAIL / {timeout_c} TIMEOUT / {len(to_run)} total")
print(f"{'='*60}")

# permanent skip 항목 업데이트
for name, reason in PERMANENT_SKIP.items():
    existing[name] = {
        "pattern": name, "status": "skip", "elapsed_s": 0,
        "outputs": [], "error": None, "skip_reason": reason
    }

# 결과 병합 후 저장
for r in results_new:
    existing[r["pattern"]] = r
SUMMARY_FILE.write_text(json.dumps(list(existing.values()), indent=2, ensure_ascii=False))
print(f"\nSummary updated: {SUMMARY_FILE}")

# 실패 목록
fails = [r for r in results_new if r["status"] != "ok"]
if fails:
    print(f"\n[실패/타임아웃 목록 - {len(fails)}개]")
    for r in fails:
        print(f"  {r['status']:8s} | {r['pattern']}")
        if r.get("error"):
            print(f"           | {str(r['error'])[:120]}")
