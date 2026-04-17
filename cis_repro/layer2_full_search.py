"""
Layer 2 + Layer 3 완전 탐색
============================

Layer 2: 물리 geometry 변수
  - bayer_config: standard / sma
  - n_material: 1.9 / 1.95 / 2.0 / 2.02 / 2.05 / 2.1
  - pillar_scale: 0.90 / 0.95 / 1.00 / 1.05 / 1.10

Layer 3: 구조 한계 탐색
  - 논문 효율 정규화 방식 재검토 (pixel vs total)
  - 원본 opt.sim 구조와 동일하게 재현

전략:
  1. bayer_sma + n_material sweep (6개) → res=20
  2. 상위 2개 → res=50
  3. 추가로 pillar_scale sweep
"""
import sys, re, json, time, subprocess, itertools
from pathlib import Path
from datetime import datetime

BASE   = Path(__file__).parent
DOCKER = "meep-pilot-worker"
sys.path.insert(0, str(BASE))

from corrected_codegen import build_corrected_code
from detector import classify_all, auto_fix_loop

RESULTS = BASE / "results" / "SMA2023_layer2"
RESULTS.mkdir(parents=True, exist_ok=True)

TARGET = {"R": 0.45, "G": 0.35, "B": 0.40}

# ── 베이스 파라미터 (bayer_sma 적용) ─────────────────────────
BASE_PARAMS = {
    "paper_id": "SMA2023_layer2",
    "paper_title": "SMA Layer2 탐색",
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
    "target_efficiency": TARGET,
    "has_code": False, "has_structure": True,
    # bayer_sma가 G+B를 개선했으므로 기본으로 사용
    "_override_base": {
        "stop_decay":    "1e-8",
        "cover_glass":   False,
        "ref_sim_type":  "air",
        "source_count":  2,
        "sipd_material": "SiO2",
        "bayer_config":  "sma",
    }
}


def make_code(params, override, cid, res=20):
    """파라미터 + override로 코드 생성"""
    p = {**params, **{"paper_id": f"SMA2023_L2_c{cid:02d}"}}
    # error_patterns에 임시 등록
    ep = json.loads((BASE / "error_patterns.json").read_text(encoding="utf-8"))
    ep["paper_specific"][p["paper_id"]] = {"overrides": override}
    (BASE / "error_patterns.json").write_text(
        json.dumps(ep, indent=2, ensure_ascii=False), encoding="utf-8")

    code = build_corrected_code(p, p["paper_id"])
    issues = classify_all(code, "", {})
    if issues:
        code, _ = auto_fix_loop(code)
    code = re.sub(r'\bresolution\s*=\s*\d+', f"resolution = {res}", code, count=1)
    return code


def run_docker(code, name, timeout=600):
    script = RESULTS / f"{name}.py"
    script.write_text(code, encoding="utf-8")
    remote = f"/tmp/l2_{name}.py"
    rlog   = f"/tmp/l2_{name}.log"
    subprocess.run(["docker","cp",str(script),f"{DOCKER}:{remote}"], capture_output=True)
    r = subprocess.run(
        ["docker","exec",DOCKER,"bash","-c",
         f"mpirun -np 4 --allow-run-as-root python {remote} > {rlog} 2>&1"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout
    )
    subprocess.run(
        ["docker","exec",DOCKER,"bash","-c",f"cat {rlog}"],
        stdout=open(RESULTS/f"{name}.log","w",encoding="utf-8"),
        stderr=subprocess.DEVNULL
    )
    log = (RESULTS/f"{name}.log").read_text(encoding="utf-8",errors="replace")
    m = re.search(r'\[Result\] R=([\d.]+) G=([\d.]+) B=([\d.]+)', log)
    e = re.findall(r'Elapsed run time = ([\d.]+)', log)
    if m:
        return {"R":float(m.group(1)),"G":float(m.group(2)),"B":float(m.group(3))},float(e[0]) if e else None
    return None, None


def calc_error(eff):
    if not eff: return 999
    errs = [abs(eff[ch]-TARGET[ch])/TARGET[ch]*100 for ch in ["R","G","B"]]
    return round(sum(errs)/len(errs), 1)


def fast_check(code, name):
    code_fc = re.sub(r'resolution\s*=\s*\d+','resolution = 5',code,count=1)
    script  = RESULTS / f"fc_{name}.py"
    script.write_text(code_fc, encoding="utf-8")
    subprocess.run(["docker","cp",str(script),f"{DOCKER}:/tmp/fc_{name}.py"], capture_output=True)
    r = subprocess.run(["docker","exec",DOCKER,"python",f"/tmp/fc_{name}.py"],
                       capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=30)
    return r.returncode == 0


print("=" * 70)
print("Layer 2 완전 탐색 — SMA2023")
print(f"목표: R={TARGET['R']} G={TARGET['G']} B={TARGET['B']}")
print("기준: bayer_sma 결과 R=0.141 G=0.403 B=0.192 (오차 ~35%)")
print("=" * 70)

all_results = []

# ══════════════════════════════════════════════════════════════
# Phase A: n_material sweep × bayer 배치
# 총 12개: n=[1.9,1.95,2.0,2.02,2.05,2.1] × bayer=[standard,sma]
# ══════════════════════════════════════════════════════════════
print("\n[Phase A] n_material 탐색 × bayer 배치 (res=20)")

n_vals   = [1.90, 1.95, 2.00, 2.02, 2.05, 2.10]
bayermap = {"standard": "표준", "sma": "SMA원본"}
phase_a  = list(itertools.product(n_vals, ["standard", "sma"]))

print(f"  총 {len(phase_a)}개 조합")

cid = 0
for n_mat, bayer in phase_a:
    override = {
        **BASE_PARAMS["_override_base"],
        "bayer_config": bayer,
    }
    params = {**BASE_PARAMS, "n_material": n_mat}

    code = make_code(params, override, cid, res=20)
    name = f"n{str(n_mat).replace('.','')}_bayer{bayer}_res20"

    ok = fast_check(code, name)
    if not ok:
        print(f"  C{cid:02d} n={n_mat} bayer={bayer}: fast-check FAIL")
        cid += 1; continue

    print(f"  C{cid:02d} n={n_mat} bayer={bayer} 실행...", end="", flush=True)
    eff, elapsed = run_docker(code, name, timeout=600)

    if eff:
        err = calc_error(eff)
        print(f" R={eff['R']:.3f} G={eff['G']:.3f} B={eff['B']:.3f}  err={err:.1f}%")
        all_results.append({
            "phase": "A", "cid": cid,
            "n_material": n_mat, "bayer": bayer,
            "override": override, "eff20": eff,
            "err20": err, "elapsed": elapsed
        })
    else:
        print(" [실패]")

    cid += 1

# Phase A 결과 정렬
all_results.sort(key=lambda x: x.get("err20", 999))
print("\n  Phase A 결과 (오차 순):")
for r in all_results[:8]:
    eff = r["eff20"]
    print(f"  n={r['n_material']:.2f} bayer={r['bayer']:<10}: "
          f"R={eff['R']:.3f} G={eff['G']:.3f} B={eff['B']:.3f}  err={r['err20']:.1f}%")

# ══════════════════════════════════════════════════════════════
# Phase B: 상위 3개 → pillar_scale sweep
# ══════════════════════════════════════════════════════════════
print("\n[Phase B] pillar_scale 탐색 (상위 3개 설정 × 5스케일)")

top3 = all_results[:3]
scales = [0.90, 0.95, 1.00, 1.05, 1.10]
phase_b_results = []

for rank, best in enumerate(top3):
    n_mat = best["n_material"]
    bayer = best["bayer"]
    print(f"\n  [rank {rank+1}] n={n_mat} bayer={bayer}:")

    for scale in scales:
        # pillar 크기에 scale 적용
        pillars = [
            {"label":"R",  "wx":round(0.92*scale,3),"wy":round(0.92*scale,3),"cx":-0.56,"cy": 0.56},
            {"label":"G1", "wx":round(0.16*scale,3),"wy":round(0.16*scale,3),"cx":-0.56,"cy":-0.56},
            {"label":"G2", "wx":round(0.16*scale,3),"wy":round(0.16*scale,3),"cx": 0.56,"cy": 0.56},
            {"label":"B",  "wx":round(0.28*scale,3),"wy":round(0.28*scale,3),"cx": 0.56,"cy":-0.56},
        ]
        params = {**BASE_PARAMS, "n_material": n_mat, "sparse_pillars": pillars}
        override = {**best["override"]}
        code = make_code(params, override, cid, res=20)
        name = f"n{str(n_mat).replace('.','')}_bayer{bayer}_sc{str(scale).replace('.','')}_res20"

        print(f"    scale={scale} 실행...", end="", flush=True)
        eff, elapsed = run_docker(code, name, timeout=600)

        if eff:
            err = calc_error(eff)
            print(f" R={eff['R']:.3f} G={eff['G']:.3f} B={eff['B']:.3f}  err={err:.1f}%")
            phase_b_results.append({
                "phase":"B","cid":cid,
                "n_material":n_mat,"bayer":bayer,"scale":scale,
                "override":override,"pillars":pillars,
                "eff20":eff,"err20":err,"elapsed":elapsed
            })
        else:
            print(" [실패]")

        cid += 1

# ══════════════════════════════════════════════════════════════
# Phase C: 최우수 후보 → res=50 최종 실행
# ══════════════════════════════════════════════════════════════
combined = all_results + phase_b_results
combined.sort(key=lambda x: x.get("err20", 999))

print("\n[Phase C] 상위 3개 → res=50 최종 실행")
final_results = []

for rank, best in enumerate(combined[:3]):
    n_mat  = best["n_material"]
    bayer  = best["bayer"]
    scale  = best.get("scale", 1.0)
    pillars = best.get("pillars", BASE_PARAMS["sparse_pillars"])
    eff20  = best["eff20"]

    print(f"\n  [rank {rank+1}] n={n_mat} bayer={bayer} scale={scale}")
    print(f"    res=20: R={eff20['R']:.3f} G={eff20['G']:.3f} B={eff20['B']:.3f}  err={best['err20']:.1f}%")

    params = {**BASE_PARAMS, "n_material": n_mat, "sparse_pillars": pillars}
    override = {**best["override"]}
    code = make_code(params, override, cid, res=50)
    name = f"final_r{rank+1}_res50"

    print(f"    res=50 실행 중...", end="", flush=True)
    eff50, elapsed50 = run_docker(code, name, timeout=10800)

    if eff50:
        err50 = calc_error(eff50)
        print(f"\n    R={eff50['R']:.3f} G={eff50['G']:.3f} B={eff50['B']:.3f}  err={err50:.1f}%")
        final_results.append({
            "rank": rank+1, "n_material": n_mat,
            "bayer": bayer, "scale": scale,
            "eff20": eff20, "eff50": eff50,
            "err50": err50, "elapsed50": elapsed50,
            "target_met": err50 <= 5.0,
        })

        if err50 <= 5.0:
            print(f"\n  [SUCCESS] 오차 {err50}% ≤ 5% 달성!")
            break
    else:
        print(" [실패]")

    cid += 1

# ── 최종 요약 ─────────────────────────────────────────────────
print("\n" + "=" * 70)
print("Layer 2+3 탐색 최종 결과")
print("=" * 70)
print(f"{'설정':<35} {'R':>6} {'G':>6} {'B':>6} {'오차':>8}")
print("─" * 60)
print(f"  {'논문 target':<33} {0.45:>6.3f} {0.35:>6.3f} {0.40:>6.3f}")
print(f"  {'이전 최적(bayer_sma)':<33} {0.141:>6.3f} {0.403:>6.3f} {0.192:>6.3f}")
for r in final_results:
    eff = r.get("eff50") or {}
    label = f"n={r['n_material']:.2f} bayer={r['bayer']} sc={r['scale']:.2f}"
    print(f"  {label:<33} {eff.get('R',0):>6.3f} {eff.get('G',0):>6.3f} {eff.get('B',0):>6.3f} {r.get('err50',999):>7.1f}%")

# 저장
out = RESULTS / "layer2_summary.json"
out.write_text(json.dumps({
    "phase_a": all_results[:8],
    "phase_b": phase_b_results[:8],
    "final": final_results,
}, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n결과 저장: {out}")
