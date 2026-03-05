"""
rerun_failed.py
수정된 패턴들만 선택적으로 재실행하고 run_summary.json 업데이트.
Docker 컨테이너 내에서 실행.
"""
import subprocess, json, sys, time
from pathlib import Path

PYTHON       = "/home/js/miniconda/envs/pmp/bin/python"
PATTERNS_DIR = Path("/root/autosim/patterns")
RESULTS_DIR  = Path("/root/autosim/results")
SUMMARY_PATH = Path("/root/autosim/run_summary.json")

# 재실행 대상 (수정 완료된 것들)
FIXED_PATTERNS = [
    "solve_cw_steady_state",         # LA → common.py에서 제공
    "sio2_substrate_pml_geometry",   # cell_x/cell_y → common.py에서 제공
    "source_monitor_size_substrate", # source_x → common.py에서 제공
    "eig_parity_2d_vs_3d",           # source_x → common.py에서 제공
    "harmonic_dilation",             # DESIGN_RESOLUTION → common.py에서 제공
    "harmonic_erosion",              # DESIGN_RESOLUTION → common.py에서 제공
    "EigenModeSource_parameters",    # L → common.py에서 제공
    "binary_grating_diffraction",    # shading='auto' 패치됨
]

# timeout 패턴 (더 긴 timeout으로 재실행)
TIMEOUT_PATTERNS = [
    "grating2d_triangular_lattice",
    "metal_cavity_ldos",
    "polarization_grating",
]

def run_pattern(name, timeout=120):
    py_file = PATTERNS_DIR / f"{name}.py"
    if not py_file.exists():
        return {"pattern": name, "status": "error", "error": "file not found", "elapsed_s": 0}

    t0 = time.time()
    print(f"  Running: {name} (timeout={timeout}s)...", flush=True)
    try:
        r = subprocess.run(
            [PYTHON, str(py_file)],
            capture_output=True, text=True,
            timeout=timeout, cwd="/root/autosim"
        )
        elapsed = round(time.time() - t0, 2)
        result_file = RESULTS_DIR / name / "result.json"
        if result_file.exists():
            data = json.loads(result_file.read_text())
            return data
        if r.returncode == 0:
            return {"pattern": name, "status": "ok", "elapsed_s": elapsed, "outputs": []}
        else:
            err = r.stderr[-300:] if r.stderr else r.stdout[-300:]
            return {"pattern": name, "status": "error", "error": err, "elapsed_s": elapsed}
    except subprocess.TimeoutExpired:
        return {"pattern": name, "status": "timeout", "error": f"Exceeded {timeout}s", "elapsed_s": timeout}
    except Exception as e:
        return {"pattern": name, "status": "error", "error": str(e), "elapsed_s": 0}


def load_summary():
    if SUMMARY_PATH.exists():
        return json.loads(SUMMARY_PATH.read_text())
    return []

def update_summary(results, new_results):
    """기존 summary에서 재실행 패턴 결과 교체"""
    new_map = {r["pattern"]: r for r in new_results}
    updated = []
    for item in results:
        if item["pattern"] in new_map:
            updated.append(new_map.pop(item["pattern"]))
        else:
            updated.append(item)
    # 새로운 패턴이 있으면 추가
    updated.extend(new_map.values())
    return updated


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "fixed"

    if mode == "timeout":
        targets = [(name, 300) for name in TIMEOUT_PATTERNS]
    elif mode == "all":
        targets = [(name, 120) for name in FIXED_PATTERNS] + [(name, 300) for name in TIMEOUT_PATTERNS]
    else:
        targets = [(name, 120) for name in FIXED_PATTERNS]

    print(f"=== 재실행: {len(targets)}개 패턴 (mode={mode}) ===\n")

    new_results = []
    ok = err = timeout_cnt = 0
    for name, t in targets:
        r = run_pattern(name, timeout=t)
        new_results.append(r)
        s = r["status"]
        if s == "ok":
            ok += 1
            print(f"    ✓ OK ({r.get('elapsed_s',0):.1f}s)")
        elif s == "timeout":
            timeout_cnt += 1
            print(f"    ✗ TIMEOUT")
        else:
            err += 1
            print(f"    ✗ FAIL: {str(r.get('error',''))[:100]}")
        print()

    print(f"=== 재실행 결과: OK {ok} / ERR {err} / TIMEOUT {timeout_cnt} / {len(targets)} ===\n")

    # run_summary.json 업데이트
    all_results = load_summary()
    all_results = update_summary(all_results, new_results)
    SUMMARY_PATH.write_text(json.dumps(all_results, indent=2, ensure_ascii=False))
    print(f"run_summary.json 업데이트 완료 ({len(all_results)}개)")

    # 최종 통계
    ok_total   = sum(1 for d in all_results if d["status"] == "ok")
    err_total  = sum(1 for d in all_results if d["status"] == "error")
    skip_total = sum(1 for d in all_results if d["status"] == "skip")
    to_total   = sum(1 for d in all_results if d["status"] == "timeout")
    print(f"\n최종: OK {ok_total} | ERR {err_total} | SKIP {skip_total} | TIMEOUT {to_total} | TOTAL {len(all_results)}")
