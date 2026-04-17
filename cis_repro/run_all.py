"""
6개 논문 순차 재현 — 간소화 버전
Agent 수정 사항을 _agent_log.json에 상세 기록
"""
import sys, re, json, time, subprocess
from pathlib import Path
from datetime import datetime

BASE     = Path(__file__).parent
NB_DIR   = Path(r"C:\Users\user\.openclaw\workspace\dev\cis_reproduce")
RESULTS  = BASE / "results"
DOCKER   = "meep-pilot-worker"
sys.path.insert(0, str(BASE))

from detector import classify_all, auto_fix_loop
from pipeline import _build_design_section, _build_full_code

# ── 논문 파라미터 ──────────────────────────────────────────────
PAPERS = [
    {
        "paper_id": "Freeform2022",
        "paper_title": "Freeform metasurface color router (deep submicron)",
        "material_name": "SiN", "n_material": 1.92,
        "SP_size": 0.6, "Layer_thickness": 0.6, "FL_thickness": 0.6,
        "EL_thickness": 0, "n_layers": 1, "resolution": 50,
        "focal_material": "Air", "design_type": "materialgrid",
        "weights_layer1": str(NB_DIR/"Freeform metasurface color router for deep submicron pixel image sensors"/"Layer1.txt").replace("\\","/"),
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
        "weights_layer1": str(NB_DIR/"Multilayer topological metasurface-based color routers"/"multi_layer"/"Layer1.txt").replace("\\","/"),
        "weights_layer2": str(NB_DIR/"Multilayer topological metasurface-based color routers"/"multi_layer"/"Layer2.txt").replace("\\","/"),
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
        "weights_layer1": str(NB_DIR/"Multilayer topological metasurface-based color routers"/"single_layer"/"Layer_singlelayer.txt").replace("\\","/"),
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
            {"label":"R",  "wx":0.92, "wy":0.92, "cx":-0.56, "cy": 0.56},
            {"label":"G1", "wx":0.16, "wy":0.16, "cx":-0.56, "cy":-0.56},
            {"label":"G2", "wx":0.16, "wy":0.16, "cx": 0.56, "cy": 0.56},
            {"label":"B",  "wx":0.28, "wy":0.28, "cx": 0.56, "cy":-0.56},
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
            {"label":"R",  "diameter":0.470, "cx":-0.4, "cy": 0.4},
            {"label":"G1", "diameter":0.370, "cx": 0.4, "cy": 0.4},
            {"label":"G2", "diameter":0.370, "cx":-0.4, "cy":-0.4},
            {"label":"B",  "diameter":0.210, "cx": 0.4, "cy":-0.4},
        ],
        "target_efficiency": {"R": 0.60, "G": 0.55, "B": 0.55},
        "has_code": False, "has_structure": True,
    },
]

# ── 유틸 함수 ─────────────────────────────────────────────────
def docker_run(script, paper_id, res, np=4, timeout=7200):
    code = script.read_text(encoding="utf-8")
    code = re.sub(r'\bresolution\s*=\s*\d+', f"resolution = {res}", code, count=1)
    rscript = script.parent / f"run_{paper_id}_res{res}.py"
    rscript.write_text(code, encoding="utf-8")
    remote = f"/tmp/run_{paper_id}_res{res}.py"
    rlog   = f"/tmp/run_{paper_id}_res{res}.log"
    rout   = f"/tmp/run_{paper_id}_res{res}_out"
    subprocess.run(["docker","cp",str(rscript),f"{DOCKER}:{remote}"], capture_output=True)
    subprocess.run(["docker","exec",DOCKER,"mkdir","-p",rout], capture_output=True)
    r = subprocess.run(
        ["docker","exec",DOCKER,"bash","-c",
         f"mpirun -np {np} --allow-run-as-root python {remote} > {rlog} 2>&1 ; cp {rlog} {rout}/"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
    )
    subprocess.run(["docker","cp",f"{DOCKER}:{rout}/.",str(script.parent)], capture_output=True)
    log = (script.parent/f"run_{paper_id}_res{res}.log")
    return log.read_text(encoding="utf-8",errors="replace") if log.exists() else ""

def parse_result(log_txt):
    m = re.search(r'\[Result\] R=([\d.]+) G=([\d.]+) B=([\d.]+)', log_txt)
    e = re.findall(r'Elapsed run time = ([\d.]+)', log_txt)
    if m:
        return {"R":float(m.group(1)),"G":float(m.group(2)),"B":float(m.group(3))}, float(e[0]) if e else None
    return None, None

# ── 메인 ─────────────────────────────────────────────────────
summary = []
print("="*65)
print("CIS 6개 논문 배치 재현 시작")
print("="*65)

for i, p in enumerate(PAPERS, 1):
    pid = p["paper_id"]
    print(f"\n{'─'*65}")
    print(f"[{i}/6] {pid}")
    print(f"{'─'*65}")

    log_entries = []  # agent 수정 로그

    out = RESULTS / pid
    out.mkdir(parents=True, exist_ok=True)
    (out/"params.json").write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding="utf-8")

    # ── 코드 생성 ──
    print("  [Stage1] 코드 생성...")
    ds   = _build_design_section(p)
    code = _build_full_code(p, pid, ds, out)
    log_entries.append({"stage":"1-generate","lines":len(code.splitlines()),"design_type":p["design_type"]})

    # ── Detector 사전 검사 ──
    issues = classify_all(code, "", {})
    if issues:
        eids = [r.error_id for r in issues]
        print(f"  [Stage1] 탐지: {eids}")
        code_before = code
        code, applied = auto_fix_loop(code)
        for rule_id in applied:
            # 변경 라인 추적
            lb = code_before.splitlines(); la = code.splitlines()
            changed = [(n+1, a, b) for n,(a,b) in enumerate(zip(lb,la)) if a!=b][:5]
            log_entries.append({
                "stage": "1-autofix",
                "rule_id": rule_id,
                "lines_before": len(lb),
                "lines_after": len(la),
                "changed_lines": [{"line":n,"before":a[:70],"after":b[:70]} for n,a,b in changed]
            })
            print(f"  [Stage1] 자동수정: {rule_id}  ({len(changed)}줄 변경)")
    else:
        print("  [Stage1] 탐지 없음 — 코드 정상")
        log_entries.append({"stage":"1-precheck","result":"clean"})

    script = out / f"reproduce_{pid}.py"
    script.write_text(code, encoding="utf-8")
    print(f"  [Stage1] 저장: {script.name} ({len(code.splitlines())}줄)")

    # ── Fast-check ──
    print("  [Stage2] Fast-check...")
    code_fc = re.sub(r'resolution\s*=\s*\d+','resolution = 5',code,count=1)
    fc = out / f"fast_{pid}.py"
    fc.write_text(code_fc, encoding="utf-8")
    subprocess.run(["docker","cp",str(fc),f"{DOCKER}:/tmp/fc_{pid}.py"], capture_output=True)
    r = subprocess.run(["docker","exec",DOCKER,"python",f"/tmp/fc_{pid}.py"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    fc_ok = r.returncode == 0
    fc_err = r.stderr[:150] if not fc_ok else ""
    log_entries.append({"stage":"2-fastcheck","result":"PASS" if fc_ok else "FAIL","error":fc_err})
    print(f"  [Stage2] {'PASS' if fc_ok else 'FAIL: '+fc_err}")

    if not fc_ok:
        (out/f"{pid}_agent_log.json").write_text(json.dumps(log_entries,indent=2,ensure_ascii=False),encoding="utf-8")
        summary.append({"paper_id":pid,"status":"fast_check_fail"})
        continue

    # ── res=20 빠른 실행 ──
    print("  [Stage3] res=20 실행...")
    t0 = time.time()
    log20 = docker_run(script, pid, res=20, np=4, timeout=600)
    eff20, elapsed20 = parse_result(log20)

    if eff20:
        print(f"  [Stage3] res=20: R={eff20['R']:.3f} G={eff20['G']:.3f} B={eff20['B']:.3f}  ({elapsed20:.0f}s)")
        log_entries.append({"stage":"3-res20","eff":eff20,"elapsed":elapsed20,"error":None})
    else:
        # 오류 처리
        errs = re.findall(r'(?:Error|Traceback)[^\n]*\n(?:[^\n]+\n){0,2}', log20)
        err_str = errs[0][:200] if errs else log20[-200:]
        print(f"  [Stage3] res=20 오류: {err_str[:100]}")

        issues2 = classify_all(code, log20, {})
        if issues2:
            eids2 = [r.error_id for r in issues2]
            print(f"  [Stage3] 오류 탐지: {eids2}")
            code_before2 = code
            code, applied2 = auto_fix_loop(code, stderr=log20)
            for rid in applied2:
                lb2=code_before2.splitlines(); la2=code.splitlines()
                changed2=[(n+1,a,b) for n,(a,b) in enumerate(zip(lb2,la2)) if a!=b][:5]
                log_entries.append({
                    "stage":"3-runtime-fix","rule_id":rid,
                    "error_snippet":err_str[:150],
                    "changed_lines":[{"line":n,"before":a[:70],"after":b[:70]} for n,a,b in changed2]
                })
                print(f"  [Stage3] 런타임 수정: {rid}")
            script.write_text(code, encoding="utf-8")
            # 재실행
            log20 = docker_run(script, pid, res=20, np=4, timeout=600)
            eff20, elapsed20 = parse_result(log20)
            if eff20:
                print(f"  [Stage3] 재실행 성공: R={eff20['R']:.3f} G={eff20['G']:.3f} B={eff20['B']:.3f}")
                log_entries.append({"stage":"3-res20-retry","eff":eff20,"elapsed":elapsed20})
        else:
            log_entries.append({"stage":"3-res20","eff":None,"error":err_str[:200]})

    # ── 최종 resolution 실행 ──
    final_res = p.get("resolution", 50)
    print(f"  [Stage3] res={final_res} 최종 실행...")
    log_final = docker_run(script, pid, res=final_res, np=4, timeout=10800)
    eff_final, elapsed_final = parse_result(log_final)

    if eff_final:
        print(f"  [Stage3] res={final_res}: R={eff_final['R']:.3f} G={eff_final['G']:.3f} B={eff_final['B']:.3f}  ({elapsed_final:.0f}s)")
        log_entries.append({"stage":f"3-res{final_res}","eff":eff_final,"elapsed":elapsed_final})
    else:
        errs_f = re.findall(r'(?:Error|Traceback)[^\n]*\n(?:[^\n]+\n){0,2}', log_final)
        err_f  = errs_f[0][:200] if errs_f else log_final[-200:]
        print(f"  [Stage3] res={final_res} 오류: {err_f[:100]}")
        log_entries.append({"stage":f"3-res{final_res}","eff":None,"error":err_f[:200]})

    # ── 결과 정리 ──
    tgt = p.get("target_efficiency", {})
    if eff_final and tgt:
        errs = {ch: abs(eff_final[ch]-tgt[ch])/tgt[ch]*100 for ch in ["R","G","B"] if ch in tgt and ch in eff_final}
        avg_err = round(sum(errs.values())/len(errs), 1)
    else:
        avg_err = None

    row = {
        "paper_id": pid, "title": p["paper_title"],
        "design_type": p["design_type"], "material": p["material_name"],
        "n": p["n_material"],
        "res20": {"eff":eff20, "elapsed":elapsed20} if eff20 else None,
        "final": {"res":final_res, "eff":eff_final, "elapsed":elapsed_final} if eff_final else None,
        "target": tgt, "avg_error_pct": avg_err,
        "status": "done" if eff_final else "partial"
    }
    (out/f"{pid}_results.json").write_text(json.dumps(row,indent=2,ensure_ascii=False),encoding="utf-8")
    (out/f"{pid}_agent_log.json").write_text(json.dumps(log_entries,indent=2,ensure_ascii=False),encoding="utf-8")
    summary.append(row)

# ── 전체 요약 ─────────────────────────────────────────────────
print("\n" + "="*65)
print("전체 결과 요약")
print("="*65)
print(f"{'논문':20} {'타입':12} {'R':>7} {'G':>7} {'B':>7} {'오차':>7} {'상태'}")
print("─"*65)
for r in summary:
    f = (r.get("final") or {}).get("eff") or {}
    rv = f"{f.get('R','?'):.3f}" if isinstance(f.get('R'), float) else "—"
    gv = f"{f.get('G','?'):.3f}" if isinstance(f.get('G'), float) else "—"
    bv = f"{f.get('B','?'):.3f}" if isinstance(f.get('B'), float) else "—"
    ev = f"{r.get('avg_error_pct','?')}%" if r.get("avg_error_pct") else "—"
    print(f"  {r['paper_id']:<18} {r.get('design_type','?'):>12} {rv:>7} {gv:>7} {bv:>7} {ev:>7}  {r.get('status','?')}")

(RESULTS/"batch_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
print(f"\n배치 완료. 결과: {RESULTS}/batch_summary.json")
