"""각 논문 코드 생성 + fast-check + res=20 시작"""
import sys, re, json, subprocess, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from detector import classify_all, auto_fix_loop
from pipeline import _build_design_section, _build_full_code

NB_DIR   = Path(r"C:\Users\user\.openclaw\workspace\dev\cis_reproduce")
RESULTS  = Path(__file__).parent / "results"
DOCKER   = "meep-pilot-worker"

PAPERS = [
    {
        "paper_id": "Freeform2022",
        "paper_title": "Freeform metasurface color router (deep submicron)",
        "material_name": "SiN", "n_material": 1.92,
        "SP_size": 0.6, "Layer_thickness": 0.6, "FL_thickness": 0.6,
        "EL_thickness": 0, "n_layers": 1, "resolution": 50,
        "focal_material": "Air", "design_type": "materialgrid",
        "weights_layer1": '/tmp/Freeform_Layer1.txt',
        "decay_by": "1e-4",
        "target_efficiency": {"R": 0.45, "G": 0.45, "B": 0.45},
        "has_code": False, "has_structure": True,
    },
    {
        "paper_id": "Multilayer2022",
        "paper_title": "Multilayer topological metasurface (2-layer SiN)",
        "material_name": "SiN", "n_material": 2.02,
        "SP_size": 0.6, "Layer_thickness": 0.6, "FL_thickness": 1.0,
        "EL_thickness": 0.2, "n_layers": 2, "resolution": 50,
        "focal_material": "Air", "design_type": "materialgrid",
        "weights_layer1": '/tmp/Multi_Layer1.txt',
        "weights_layer2": '/tmp/Multi_Layer2.txt',
        "decay_by": "1e-3",
        "target_efficiency": {"R": 0.50, "G": 0.50, "B": 0.50},
        "has_code": False, "has_structure": True,
    },
    {
        "paper_id": "SingleLayer2022",
        "paper_title": "Single layer topological metasurface (SiN n=2.1)",
        "material_name": "SiN", "n_material": 2.1,
        "SP_size": 0.6, "Layer_thickness": 0.6, "FL_thickness": 0.6,
        "EL_thickness": 0, "n_layers": 1, "resolution": 50,
        "focal_material": "Air", "design_type": "materialgrid",
        "weights_layer1": '/tmp/Single_Layer_singlelayer.txt',
        "decay_by": "1e-3",
        "target_efficiency": {"R": 0.45, "G": 0.40, "B": 0.45},
        "has_code": False, "has_structure": True,
    },
    {
        "paper_id": "RGBIR2025",
        "paper_title": "RGB+IR spectral router (TiO2 22x22, ACS 2025)",
        "material_name": "TiO2", "n_material": 2.5,
        "SP_size": 1.1, "Layer_thickness": 0.6, "FL_thickness": 4.0,
        "EL_thickness": 0, "n_layers": 1, "resolution": 50,
        "focal_material": "SiO2", "design_type": "discrete_pillar",
        "grid_n": 22, "tile_w": 0.1, "min_feature_um": 0.1,
        "pillar_mask": [
            [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
            [1,0,0,0,1,1,0,0,0,0,0,1,1,0,0,1,0,1,0,1,0,0],
            [1,0,0,1,0,0,1,1,1,0,0,1,1,0,1,0,0,1,0,0,0,0],
            [0,1,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,1,0],
            [0,1,1,0,0,0,0,0,1,0,0,0,0,0,0,0,0,1,0,0,0,0],
            [1,1,1,1,0,1,1,0,1,1,0,0,0,1,1,0,0,1,0,0,0,0],
            [0,0,0,0,0,0,0,1,1,1,0,0,0,1,1,0,0,1,0,0,1,0],
            [0,1,0,1,0,1,0,1,0,0,0,0,0,1,0,0,0,1,0,1,1,0],
            [0,0,0,0,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,1,0],
            [0,1,0,1,1,0,0,0,1,1,0,0,0,1,0,1,0,1,0,0,0,0],
            [0,0,0,0,0,1,0,0,1,1,0,1,0,0,0,0,0,0,0,0,1,0],
            [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
            [1,0,0,0,1,1,0,0,0,0,0,0,1,0,0,0,0,0,0,1,0,0],
            [0,0,0,0,0,0,1,0,0,1,0,0,0,0,1,0,1,0,0,0,0,0],
            [1,1,1,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
            [1,0,0,1,1,1,1,1,1,0,0,0,1,0,0,0,1,1,1,0,1,0],
            [0,1,1,0,0,1,1,1,1,0,0,1,1,0,0,0,1,1,0,1,1,0],
            [1,0,0,0,0,0,1,0,0,0,0,0,0,1,1,0,0,1,0,1,0,0],
            [1,0,0,0,0,0,0,0,1,1,0,0,0,1,0,0,1,0,0,0,1,0],
            [1,1,1,1,1,1,1,1,0,1,0,1,1,0,1,1,0,0,1,1,0,0],
            [0,0,1,1,1,1,1,0,1,0,0,0,0,1,0,1,0,0,0,0,0,0],
            [1,0,0,0,0,0,0,1,0,1,0,1,1,0,0,0,0,1,0,1,1,0],
        ],
        "wavelengths": [0.45, 0.55, 0.65],
        "target_efficiency": {"R": 0.50, "G": 0.40, "B": 0.50},
        "has_code": False, "has_structure": True,
    },
    {
        "paper_id": "SMA2023",
        "paper_title": "Sparse meta-atom array (Chinese Optics Letters)",
        "material_name": "SiN", "n_material": 2.02,
        "SP_size": 1.12, "Layer_thickness": 1.0, "FL_thickness": 4.0,
        "EL_thickness": 0, "n_layers": 1, "resolution": 50,
        "focal_material": "SiO2", "design_type": "sparse",
        "sparse_pillars": [
            {"label": "R",  "wx": 0.92, "wy": 0.92, "cx": -0.56, "cy":  0.56},
            {"label": "G1", "wx": 0.16, "wy": 0.16, "cx": -0.56, "cy": -0.56},
            {"label": "G2", "wx": 0.16, "wy": 0.16, "cx":  0.56, "cy":  0.56},
            {"label": "B",  "wx": 0.28, "wy": 0.28, "cx":  0.56, "cy": -0.56},
        ],
        "target_efficiency": {"R": 0.45, "G": 0.35, "B": 0.40},
        "has_code": False, "has_structure": True,
    },
    {
        "paper_id": "Simplest2023",
        "paper_title": "Simplest GA cylinder router (Nb2O5)",
        "material_name": "Nb2O5", "n_material": 2.32,
        "SP_size": 0.8, "Layer_thickness": 0.51, "FL_thickness": 1.08,
        "EL_thickness": 0, "n_layers": 1, "resolution": 100,
        "focal_material": "Air", "design_type": "cylinder",
        "cylinders": [
            {"label": "R",  "diameter": 0.470, "cx": -0.4, "cy":  0.4},
            {"label": "G1", "diameter": 0.370, "cx":  0.4, "cy":  0.4},
            {"label": "G2", "diameter": 0.370, "cx": -0.4, "cy": -0.4},
            {"label": "B",  "diameter": 0.210, "cx":  0.4, "cy": -0.4},
        ],
        "target_efficiency": {"R": 0.60, "G": 0.55, "B": 0.55},
        "has_code": False, "has_structure": True,
    },
]


def make_script(p):
    """코드 생성 + detector 수정 + 저장 → (script, agent_log)"""
    pid = p["paper_id"]
    out = RESULTS / pid
    out.mkdir(parents=True, exist_ok=True)
    log = []

    ds   = _build_design_section(p)
    code = _build_full_code(p, pid, ds, out)
    log.append({"step": "generated", "lines": len(code.splitlines()), "design_type": p["design_type"]})

    issues = classify_all(code, "", {})
    if issues:
        eids = [r.error_id for r in issues]
        code_before = code
        code, applied = auto_fix_loop(code)
        for rid in applied:
            lb = code_before.splitlines()
            la = code.splitlines()
            changed = [{"line": n+1, "before": b[:70], "after": a[:70]}
                       for n, (b, a) in enumerate(zip(lb, la)) if b != a][:8]
            log.append({"step": "autofix", "rule_id": rid, "changed_lines": changed,
                        "lines_delta": len(la) - len(lb)})
    else:
        log.append({"step": "precheck_clean"})

    script = out / f"reproduce_{pid}.py"
    script.write_text(code, encoding="utf-8")
    return script, log


def fast_check(script, pid):
    code_fc = re.sub(r'resolution\s*=\s*\d+', 'resolution = 5',
                     script.read_text(encoding="utf-8"), count=1)
    fc = script.parent / f"fast_{pid}.py"
    fc.write_text(code_fc, encoding="utf-8")
    subprocess.run(["docker", "cp", str(fc), f"{DOCKER}:/tmp/fc_{pid}.py"], capture_output=True)
    r = subprocess.run(["docker", "exec", DOCKER, "python", f"/tmp/fc_{pid}.py"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    return r.returncode == 0, r.stderr[:150]


def start_docker(script, pid, res, np=4):
    code = re.sub(r'\bresolution\s*=\s*\d+', f"resolution = {res}",
                  script.read_text(encoding="utf-8"), count=1)
    rs = script.parent / f"run_{pid}_res{res}.py"
    rs.write_text(code, encoding="utf-8")
    remote = f"/tmp/run_{pid}_res{res}.py"
    rlog   = f"/tmp/run_{pid}_res{res}.log"
    subprocess.run(["docker", "cp", str(rs), f"{DOCKER}:{remote}"], capture_output=True)
    subprocess.Popen(
        ["docker", "exec", DOCKER, "bash", "-c",
         f"mpirun -np {np} --allow-run-as-root python {remote} > {rlog} 2>&1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return remote, rlog


def wait_result(pid, res, timeout=10800):
    rlog = f"/tmp/run_{pid}_res{res}.log"
    deadline = time.time() + timeout
    prev_step = 0
    while time.time() < deadline:
        r = subprocess.run(
            ["docker", "exec", DOCKER, "bash", "-c", f"tail -3 {rlog} 2>/dev/null"],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        txt = r.stdout
        # 완료 체크
        if "[Result]" in txt or "[Done]" in txt or "Elapsed run time" in txt:
            break
        # 진행 상황
        m = re.search(r'time=(\d+)', txt)
        if m:
            step = int(m.group(1))
            if step - prev_step >= 20:
                print(f"    time={step}...", end="", flush=True)
                prev_step = step
        time.sleep(10)
    # 로그 수집
    local_log = RESULTS / pid / f"run_{pid}_res{res}.log"
    subprocess.run(
        ["docker", "exec", DOCKER, "bash", "-c", f"cat {rlog}"],
        stdout=open(local_log, "w", encoding="utf-8"), stderr=subprocess.DEVNULL
    )
    log_txt = local_log.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'\[Result\] R=([\d.]+) G=([\d.]+) B=([\d.]+)', log_txt)
    e = re.findall(r'Elapsed run time = ([\d.]+)', log_txt)
    if m:
        return {"R": float(m.group(1)), "G": float(m.group(2)), "B": float(m.group(3))}, float(e[0]) if e else None
    return None, None


# ── 메인 ──────────────────────────────────────────────────────
print("=" * 65)
print("CIS 6개 논문 배치 재현")
print("=" * 65)

all_results = []
all_logs    = {}

# PHASE 1: 모든 논문 코드 생성 + fast-check
print("\n[Phase 1] 코드 생성 + Fast-check")
scripts = {}
for p in PAPERS:
    pid = p["paper_id"]
    print(f"\n  {pid}")
    script, log = make_script(p)
    all_logs[pid] = log
    ok, err = fast_check(script, pid)
    status = "PASS" if ok else f"FAIL: {err[:60]}"
    print(f"    fast-check: {status}")
    log.append({"step": "fast_check", "result": "PASS" if ok else "FAIL", "error": err})
    if ok:
        scripts[pid] = script
    else:
        all_results.append({"paper_id": pid, "status": "fast_check_fail"})

print(f"\n  통과: {len(scripts)}/{len(PAPERS)}개")

# PHASE 2: res=20 순차 실행
print("\n[Phase 2] res=20 순차 실행 (색 분리 방향 확인)")
res20_results = {}
for pid, script in scripts.items():
    p = next(x for x in PAPERS if x["paper_id"] == pid)
    print(f"\n  {pid} res=20...")
    start_docker(script, pid, res=20)
    eff, elapsed = wait_result(pid, res=20, timeout=600)
    if eff:
        print(f"    R={eff['R']:.3f} G={eff['G']:.3f} B={eff['B']:.3f}  ({elapsed:.0f}s)")
        all_logs[pid].append({"step": "res20", "eff": eff, "elapsed": elapsed})
    else:
        # 오류 체크 + 자동 수정
        log_path = RESULTS / pid / f"run_{pid}_res20.log"
        log_txt  = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        errs = re.findall(r'(?:Error|Traceback)[^\n]*', log_txt)
        print(f"    오류: {errs[0][:80] if errs else 'unknown'}")

        code_before = script.read_text(encoding="utf-8")
        issues = classify_all(code_before, log_txt, {})
        if issues:
            eids = [r.error_id for r in issues]
            print(f"    탐지: {eids} → 자동 수정 후 재실행")
            code_fixed, applied = auto_fix_loop(code_before, stderr=log_txt)
            script.write_text(code_fixed, encoding="utf-8")
            lb = code_before.splitlines(); la = code_fixed.splitlines()
            changed = [{"line": n+1, "before": b[:70], "after": a[:70]}
                       for n, (b, a) in enumerate(zip(lb, la)) if b != a][:8]
            all_logs[pid].append({
                "step": "runtime_fix", "rule_ids": applied,
                "trigger_error": errs[0][:100] if errs else "",
                "changed_lines": changed
            })
            start_docker(script, pid, res=20)
            eff, elapsed = wait_result(pid, res=20, timeout=600)
            if eff:
                print(f"    재실행: R={eff['R']:.3f} G={eff['G']:.3f} B={eff['B']:.3f}")
                all_logs[pid].append({"step": "res20_retry", "eff": eff, "elapsed": elapsed})
    res20_results[pid] = eff

# PHASE 3: 최종 resolution 실행
print("\n[Phase 3] 최종 resolution 실행")
for pid, script in scripts.items():
    p     = next(x for x in PAPERS if x["paper_id"] == pid)
    final = p.get("resolution", 50)
    print(f"\n  {pid} res={final}...")
    start_docker(script, pid, res=final, np=4)
    eff_f, elapsed_f = wait_result(pid, res=final, timeout=10800)
    if eff_f:
        tgt = p.get("target_efficiency", {})
        if tgt:
            errs = {ch: abs(eff_f[ch]-tgt[ch])/tgt[ch]*100 for ch in ["R","G","B"] if ch in tgt}
            avg_err = round(sum(errs.values())/len(errs), 1)
        else:
            avg_err = None
        print(f"    R={eff_f['R']:.3f} G={eff_f['G']:.3f} B={eff_f['B']:.3f}  ({elapsed_f:.0f}s)  avg_err={avg_err}%")
        all_logs[pid].append({"step": f"res{final}", "eff": eff_f, "elapsed": elapsed_f, "avg_error_pct": avg_err})
        row = {"paper_id": pid, "design_type": p["design_type"], "material": p["material_name"],
               "res20": res20_results.get(pid), "final": {"res": final, "eff": eff_f, "elapsed": elapsed_f},
               "target": tgt, "avg_error_pct": avg_err, "status": "done"}
    else:
        print(f"    실패")
        row = {"paper_id": pid, "status": "failed"}
    all_results.append(row)
    out = RESULTS / pid
    (out / f"{pid}_results.json").write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / f"{pid}_agent_log.json").write_text(json.dumps(all_logs[pid], indent=2, ensure_ascii=False), encoding="utf-8")

# 요약
print("\n" + "="*65)
print("전체 결과")
print("="*65)
print(f"{'논문':<20} {'타입':>12} {'R':>7} {'G':>7} {'B':>7} {'오차':>8}")
print("─"*65)
for r in all_results:
    f = (r.get("final") or {}).get("eff") or {}
    rv = f"{f.get('R',0):.3f}" if f.get('R') else "—"
    gv = f"{f.get('G',0):.3f}" if f.get('G') else "—"
    bv = f"{f.get('B',0):.3f}" if f.get('B') else "—"
    ev = f"{r.get('avg_error_pct','?')}%" if r.get("avg_error_pct") else "—"
    print(f"  {r['paper_id']:<18} {r.get('design_type','?'):>12} {rv:>7} {gv:>7} {bv:>7} {ev:>8}")

(RESULTS / "batch_summary.json").write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n완료. 결과: {RESULTS}/batch_summary.json")
