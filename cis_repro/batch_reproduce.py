"""
남은 6개 논문 순차 재현 + Agent 수정 사항 상세 추적
=====================================================
각 논문마다:
  1. params.json 자동 생성 (notebook에서 파라미터 파싱)
  2. pipeline_v2 실행
  3. Agent 탐지/수정 내용 상세 로깅
  4. 결과 JSON 저장
"""
import sys, re, json, time, subprocess, shutil
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from detector import classify_all, auto_fix_loop

BASE         = Path(__file__).parent
NB_DIR       = Path(r"C:\Users\user\.openclaw\workspace\dev\cis_reproduce")
RESULTS_DIR  = BASE / "results"
DOCKER       = "meep-pilot-worker"

# ──────────────────────────────────────────────────────────────
# 논문별 params.json 정의 (notebook 파싱 기반)
# ──────────────────────────────────────────────────────────────
PAPERS = [
    {
        "paper_id": "Freeform2022",
        "paper_title": "Freeform metasurface color router for deep submicron pixel image sensors",
        "nb_file": "Freeform metasurface color router for deep submicron pixel image sensors/Freeform_Re.ipynb",
        "material_name": "SiN", "n_material": 1.92,
        "SP_size": 0.6, "Layer_thickness": 0.6, "FL_thickness": 0.6,
        "EL_thickness": 0, "n_layers": 1, "resolution": 50,
        "focal_material": "Air", "design_type": "materialgrid",
        "weights_dir": str(NB_DIR / "Freeform metasurface color router for deep submicron pixel image sensors"),
        "decay_by": "1e-4",
        "target_efficiency": {"R": 0.45, "G": 0.45, "B": 0.45},
        "has_code": False, "has_structure": True,
        "notes": "SiN freeform adjoint, deep submicron 1.2um pixel. Layer1.txt weights. Short focal=0.6um."
    },
    {
        "paper_id": "Multilayer2022",
        "paper_title": "Multilayer topological metasurface-based color routers (2-layer)",
        "nb_file": "Multilayer topological metasurface-based color routers/multi_layer/Multi_layer_Re.ipynb",
        "material_name": "SiN", "n_material": 2.02,
        "SP_size": 0.6, "Layer_thickness": 0.6, "FL_thickness": 1.0,
        "EL_thickness": 0.2, "n_layers": 2, "resolution": 50,
        "focal_material": "Air", "design_type": "materialgrid",
        "weights_dir": str(NB_DIR / "Multilayer topological metasurface-based color routers" / "multi_layer"),
        "decay_by": "1e-3",
        "target_efficiency": {"R": 0.50, "G": 0.50, "B": 0.50},
        "has_code": False, "has_structure": True,
        "notes": "SiN 2-layer MaterialGrid. EL spacer=200nm SiN. Layer1.txt + Layer2.txt."
    },
    {
        "paper_id": "SingleLayer2022",
        "paper_title": "Single Layer Topological Metasurface Color Router (SiN)",
        "nb_file": "Multilayer topological metasurface-based color routers/single_layer/Single_layer_Re.ipynb",
        "material_name": "SiN", "n_material": 2.1,
        "SP_size": 0.6, "Layer_thickness": 0.6, "FL_thickness": 0.6,
        "EL_thickness": 0, "n_layers": 1, "resolution": 50,
        "focal_material": "Air", "design_type": "materialgrid",
        "weights_dir": str(NB_DIR / "Multilayer topological metasurface-based color routers" / "single_layer"),
        "decay_by": "1e-3",
        "target_efficiency": {"R": 0.45, "G": 0.40, "B": 0.45},
        "has_code": False, "has_structure": True,
        "notes": "SiN single-layer MaterialGrid (n=2.1). Layer_singlelayer.txt. Comparison baseline for multilayer."
    },
    {
        "paper_id": "RGBIR2025",
        "paper_title": "Pixel-level spectral routers for RGB+IR sensing (ACS 2025)",
        "nb_file": "pixel-level-spectral-routers-for-rgb-ir-sensing/RGB_IR_ACS2025_Re.ipynb",
        "material_name": "TiO2", "n_material": 2.5,
        "SP_size": 1.1, "Layer_thickness": 0.6, "FL_thickness": 4.0,
        "EL_thickness": 0, "n_layers": 1, "resolution": 50,
        "focal_material": "SiO2",
        "design_type": "discrete_pillar",
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
            [1,0,0,0,0,0,0,1,0,1,0,1,1,0,0,0,0,1,0,1,1,0]
        ],
        "wavelengths": [0.45, 0.55, 0.65],
        "target_efficiency": {"R": 0.50, "G": 0.40, "B": 0.50},
        "has_code": False, "has_structure": True,
        "notes": "TiO2 22x22 pillar, 100nm tile, FL=4.0um, RGB+IR routing, ACS Photonics 2025."
    },
    {
        "paper_id": "SMA2023",
        "paper_title": "Pixelated Bayer spectral router based on sparse meta-atom array (Chinese Optics Letters)",
        "nb_file": "Pixelated Bayer spectral router based on a sparse meta-atom array_Chinese Optics Letters/SMA_Re.ipynb",
        "material_name": "SiN", "n_material": 2.02,
        "SP_size": 1.12, "Layer_thickness": 1.0, "FL_thickness": 4.0,
        "EL_thickness": 0, "n_layers": 1, "resolution": 50,
        "focal_material": "SiO2",
        "design_type": "sparse",
        "sparse_pillars": [
            {"label": "R",  "wx": 0.92, "wy": 0.92, "cx": -0.56, "cy":  0.56},
            {"label": "G1", "wx": 0.16, "wy": 0.16, "cx": -0.56, "cy": -0.56},
            {"label": "G2", "wx": 0.16, "wy": 0.16, "cx":  0.56, "cy":  0.56},
            {"label": "B",  "wx": 0.28, "wy": 0.28, "cx":  0.56, "cy": -0.56},
        ],
        "target_efficiency": {"R": 0.45, "G": 0.35, "B": 0.40},
        "has_code": False, "has_structure": True,
        "notes": "4-pillar sparse SiN: R=920nm, G=160nm, B=280nm squares. FL=4.0um SiO2 focal."
    },
    {
        "paper_id": "Simplest2023",
        "paper_title": "Simplest but Efficient Color Router Optimized by Genetic Algorithms (Nb2O5 cylinders)",
        "nb_file": "simplest-but-efficient-design-of-a-color-router-optimized-by-genetic-algorithms/Simplest_Re.ipynb",
        "material_name": "Nb2O5", "n_material": 2.32,
        "SP_size": 0.8, "Layer_thickness": 0.51, "FL_thickness": 1.08,
        "EL_thickness": 0, "n_layers": 1, "resolution": 100,
        "focal_material": "Air",
        "design_type": "cylinder",
        "cylinders": [
            {"label": "R",  "diameter": 0.470, "cx": -0.4, "cy":  0.4},
            {"label": "G1", "diameter": 0.370, "cx":  0.4, "cy":  0.4},
            {"label": "G2", "diameter": 0.370, "cx": -0.4, "cy": -0.4},
            {"label": "B",  "diameter": 0.210, "cx":  0.4, "cy": -0.4},
        ],
        "target_efficiency": {"R": 0.60, "G": 0.55, "B": 0.55},
        "has_code": False, "has_structure": True,
        "notes": "Nb2O5 cylinders. D_R=470nm, D_G=370nm, D_B=210nm. GA optimized. resolution=100 (10nm grid)."
    },
]

# ──────────────────────────────────────────────────────────────
# Agent 수정 추적 클래스
# ──────────────────────────────────────────────────────────────
class AgentTracker:
    def __init__(self, paper_id):
        self.paper_id = paper_id
        self.events   = []
        self.t0       = time.time()

    def log(self, stage, action, detail="", code_before="", code_after=""):
        ev = {
            "t":       round(time.time() - self.t0, 1),
            "stage":   stage,
            "action":  action,
            "detail":  detail,
        }
        if code_before and code_after and code_before != code_after:
            # diff: 변경된 라인만 기록
            lines_b = code_before.splitlines()
            lines_a = code_after.splitlines()
            changed = [(i+1, lb, la) for i, (lb, la) in enumerate(zip(lines_b, lines_a)) if lb != la]
            ev["code_changes"] = [{"line": ln, "before": b[:80], "after": a[:80]}
                                   for ln, b, a in changed[:10]]
            if len(lines_a) != len(lines_b):
                ev["lines_added"] = len(lines_a) - len(lines_b)
        self.events.append(ev)
        print(f"  [{ev['t']:6.1f}s] [{stage}] {action}: {detail[:80]}")

    def save(self, out_dir):
        path = Path(out_dir) / f"{self.paper_id}_agent_log.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"paper_id": self.paper_id, "events": self.events}, f,
                      indent=2, ensure_ascii=False)
        return path


# ──────────────────────────────────────────────────────────────
# params.json MaterialGrid 보강 (weights_dir → 실제 파일 경로 주입)
# ──────────────────────────────────────────────────────────────
def enrich_materialgrid_params(params):
    """MaterialGrid 논문: weights_dir에서 Layer*.txt 로드 경로 주입"""
    if params.get("design_type") != "materialgrid":
        return params
    wdir = Path(params.get("weights_dir", ""))
    for k in range(1, params.get("n_layers", 1) + 1):
        candidates = [
            wdir / f"Layer{k}.txt",
            wdir / "Layer_singlelayer.txt",
        ]
        for c in candidates:
            if c.exists():
                params[f"weights_layer{k}"] = str(c).replace("\\", "/")
                print(f"  [weights] Layer{k}: {c.name} ({c.stat().st_size//1024}KB)")
                break
    return params


# ──────────────────────────────────────────────────────────────
# 코드 생성 + 상세 추적
# ──────────────────────────────────────────────────────────────
def generate_and_track(params, tracker):
    """pipeline.py의 generate_code 로직을 직접 호출, 각 단계 추적"""
    from pipeline import (
        pre_check_and_fix,
        _build_design_section, _build_full_code
    )

    paper_id = params["paper_id"]
    out_dir  = RESULTS_DIR / paper_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: 설계 섹션 생성
    tracker.log("Stage1", "design_section", f"design_type={params['design_type']}")
    design_section = _build_design_section(params)

    # Step 2: 전체 코드 생성
    code_v0 = _build_full_code(params, paper_id, design_section, out_dir)
    tracker.log("Stage1", "code_generated", f"{len(code_v0.splitlines())}줄 생성")

    # Step 3: detector 사전 검사
    issues = classify_all(code_v0, "", {})
    if issues:
        tracker.log("Stage1", "detector_precheck",
                    f"{len(issues)}개 탐지: {[r.error_id for r in issues]}")
        code_v1, applied = auto_fix_loop(code_v0)
        for rule_id in applied:
            tracker.log("Stage1", "auto_fix_applied", f"규칙 적용: {rule_id}",
                        code_before=code_v0, code_after=code_v1)
        code_final = code_v1
    else:
        tracker.log("Stage1", "detector_precheck", "이슈 없음 — 코드 정상")
        code_final = code_v0

    script = out_dir / f"reproduce_{paper_id}.py"
    script.write_text(code_final, encoding="utf-8")
    tracker.log("Stage1", "code_saved", str(script))
    return script


# ──────────────────────────────────────────────────────────────
# fast-check 추적
# ──────────────────────────────────────────────────────────────
def fast_check_tracked(script, paper_id, tracker):
    code     = script.read_text(encoding="utf-8")
    code_fc  = re.sub(r'resolution\s*=\s*\d+', 'resolution = 5', code, count=1)
    fc_path  = script.parent / f"fast_{paper_id}.py"
    fc_path.write_text(code_fc, encoding="utf-8")

    subprocess.run(["docker","cp",str(fc_path),f"{DOCKER}:/tmp/fc_{paper_id}.py"],
                   capture_output=True)
    r = subprocess.run(
        ["docker","exec",DOCKER,"python",f"/tmp/fc_{paper_id}.py"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
    )
    ok = r.returncode == 0
    tracker.log("Stage2", "fast_check", "PASSED" if ok else f"FAILED: {r.stderr[:100]}")
    return ok


# ──────────────────────────────────────────────────────────────
# 실행 + 오류 추적
# ──────────────────────────────────────────────────────────────
def run_tracked(script, paper_id, tracker, res=20, np=4, timeout=600):
    """res 지정 실행 + 오류 발생 시 detector 자동수정 추적"""
    code = script.read_text(encoding="utf-8")
    code = re.sub(r'\bresolution\s*=\s*\d+', f"resolution = {res}", code, count=1)
    run_script = script.parent / f"run_{paper_id}_res{res}.py"
    run_script.write_text(code, encoding="utf-8")

    remote_py  = f"/tmp/run_{paper_id}_res{res}.py"
    remote_log = f"/tmp/run_{paper_id}_res{res}.log"
    remote_out = f"/tmp/run_{paper_id}_res{res}_results"

    subprocess.run(["docker","cp",str(run_script),f"{DOCKER}:{remote_py}"], capture_output=True)
    subprocess.run(["docker","exec",DOCKER,"mkdir","-p",remote_out], capture_output=True)

    tracker.log("Stage3", "execution_start",
                f"res={res} np={np} docker={DOCKER}")

    for attempt in range(1, 4):
        r = subprocess.run(
            ["docker","exec",DOCKER,"bash","-c",
             f"mpirun -np {np} --allow-run-as-root python {remote_py} "
             f"> {remote_log} 2>&1 ; cp {remote_log} {remote_out}/"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout
        )
        # 결과 수집
        subprocess.run(["docker","cp",f"{DOCKER}:{remote_out}/.",
                        str(script.parent)], capture_output=True)
        log_path = script.parent / f"run_{paper_id}_res{res}.log"
        log_txt  = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""

        # 결과 확인
        result_json = script.parent / f"{paper_id}_results.json"
        m_result = re.search(r'\[Result\] R=([\d.]+) G=([\d.]+) B=([\d.]+)', log_txt)
        if m_result:
            eff = {"R": float(m_result.group(1)),
                   "G": float(m_result.group(2)),
                   "B": float(m_result.group(3))}
            elapsed_m = re.findall(r'Elapsed run time = ([\d.]+)', log_txt)
            elapsed = float(elapsed_m[0]) if elapsed_m else None
            tracker.log("Stage3", "execution_success",
                        f"시도{attempt}: R={eff['R']:.3f} G={eff['G']:.3f} B={eff['B']:.3f}  "
                        f"({elapsed:.0f}s)")
            return eff, elapsed

        # 오류 탐지 + 자동 수정
        stderr = log_txt if ("Error" in log_txt or "Traceback" in log_txt) else ""
        if stderr:
            issues = classify_all(code, stderr, {})
            if issues:
                tracker.log("Stage3", "error_detected",
                            f"시도{attempt}: {[r2.error_id for r2 in issues[:3]]}")
                code_before = code
                code, applied = auto_fix_loop(code, stderr=stderr)
                if applied:
                    tracker.log("Stage3", "auto_fix",
                                f"수정 적용: {applied}",
                                code_before=code_before, code_after=code)
                    run_script.write_text(code, encoding="utf-8")
                    subprocess.run(["docker","cp",str(run_script),f"{DOCKER}:{remote_py}"],
                                   capture_output=True)
                else:
                    tracker.log("Stage3", "no_fix", f"규칙 없음: {stderr[:100]}")
                    break
            else:
                tracker.log("Stage3", "unknown_error", stderr[:150])
                break
        else:
            tracker.log("Stage3", "no_result_json", "실행됐으나 결과 없음")
            break

    return None, None


# ──────────────────────────────────────────────────────────────
# 메인 배치 실행
# ──────────────────────────────────────────────────────────────
def main():
    all_results = []
    print("=" * 65)
    print("CIS 논문 순차 재현 배치 — Agent 수정 상세 추적")
    print(f"총 {len(PAPERS)}개 논문")
    print("=" * 65)

    for i, params in enumerate(PAPERS, 1):
        pid   = params["paper_id"]
        title = params["paper_title"][:55]
        print(f"\n{'─'*65}")
        print(f"[{i}/{len(PAPERS)}] {pid}: {title}")
        print(f"{'─'*65}")

        tracker = AgentTracker(pid)
        out_dir = RESULTS_DIR / pid
        out_dir.mkdir(parents=True, exist_ok=True)

        # params.json 저장
        params_full = {**params}
        if params.get("design_type") == "materialgrid":
            params_full = enrich_materialgrid_params(params_full)
        params_path = out_dir / "params.json"
        params_path.write_text(json.dumps(params_full, indent=2, ensure_ascii=False),
                               encoding="utf-8")
        tracker.log("Stage0", "params_saved", f"{len(params_full)}개 파라미터")

        # 코드 생성 + detector 추적
        try:
            script = generate_and_track(params_full, tracker)
        except Exception as e:
            tracker.log("Stage1", "code_gen_error", str(e))
            tracker.save(out_dir)
            all_results.append({"paper_id": pid, "status": "error", "error": str(e)})
            continue

        # fast-check
        ok = fast_check_tracked(script, pid, tracker)
        if not ok:
            tracker.save(out_dir)
            all_results.append({"paper_id": pid, "status": "fast_check_fail"})
            continue

        # res=20 빠른 확인
        eff20, t20 = run_tracked(script, pid, tracker, res=20, np=4,
                                  timeout=300 if params.get("resolution",50)<60 else 600)

        # res=50 최종 (Simplest는 res=100 그대로)
        final_res = params.get("resolution", 50)
        eff_final, t_final = run_tracked(script, pid, tracker, res=final_res,
                                          np=4, timeout=7200)

        # 결과 저장
        result = {
            "paper_id": pid,
            "title": params["paper_title"],
            "design_type": params["design_type"],
            "material": params["material_name"],
            "res20": {"eff": eff20, "elapsed": t20} if eff20 else None,
            "final": {"res": final_res, "eff": eff_final, "elapsed": t_final} if eff_final else None,
            "target": params.get("target_efficiency"),
            "status": "done" if eff_final else "partial",
        }
        # 오차 계산
        if eff_final and params.get("target_efficiency"):
            tgt = params["target_efficiency"]
            errs = {ch: abs(eff_final[ch]-tgt[ch])/tgt[ch]*100
                    for ch in ["R","G","B"] if ch in tgt and ch in eff_final}
            result["avg_error_pct"] = round(sum(errs.values())/len(errs), 1)

        (out_dir / f"{pid}_results.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        tracker.save(out_dir)
        all_results.append(result)

        # 간단 출력
        if eff_final:
            err_str = f"avg_err={result.get('avg_error_pct','?')}%"
            print(f"  결과: R={eff_final['R']:.3f} G={eff_final['G']:.3f} B={eff_final['B']:.3f}  {err_str}")
        else:
            print(f"  결과: 실패")

    # 전체 요약
    print("\n" + "=" * 65)
    print("전체 결과 요약")
    print("=" * 65)
    print(f"{'논문':<20} {'design':>12} {'R':>7} {'G':>7} {'B':>7} {'avg_err':>9} {'status'}")
    print("─" * 65)
    for r in all_results:
        eff = r.get("final", {}) or {}
        eff = eff.get("eff") or {}
        rv = f"{eff.get('R','?'):.3f}" if isinstance(eff.get('R'), float) else "—"
        gv = f"{eff.get('G','?'):.3f}" if isinstance(eff.get('G'), float) else "—"
        bv = f"{eff.get('B','?'):.3f}" if isinstance(eff.get('B'), float) else "—"
        err_str = f"{r.get('avg_error_pct','?')}%" if r.get("avg_error_pct") else "—"
        print(f"  {r['paper_id']:<18} {r.get('design_type','?'):>12} {rv:>7} {gv:>7} {bv:>7} {err_str:>9} {r.get('status','?')}")

    # 전체 결과 저장
    (BASE / "results" / "batch_summary.json").write_text(
        json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n상세 결과: {BASE}/results/batch_summary.json")
    print("각 논문별 agent 로그: results/{{paper_id}}/{{paper_id}}_agent_log.json")


if __name__ == "__main__":
    main()
