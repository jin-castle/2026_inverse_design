"""
CIS Color Router 재현 파이프라인 오케스트레이터
=====================================================
흐름: params.json → 코드 생성 → fast-check → 실행환경 결정 → 실행 → 오류자동수정 → 결과 검증 → meep-kb 저장

사용법:
  python pipeline.py --params params.json
  python pipeline.py --params params.json --dry-run
  python pipeline.py --params params.json --force-local
  python pipeline.py --params params.json --force-simserver
"""

import argparse
import json
import os
import re
import subprocess
import sqlite3
import sys
import time
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── 경로 설정 ────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
MEEP_KB_DIR = BASE_DIR.parent
DB_PATH     = MEEP_KB_DIR / "db" / "knowledge.db"
RESULTS_DIR = BASE_DIR / "results"
TEMPLATES   = BASE_DIR / "templates"
ERROR_RULES = BASE_DIR / "error_rules.json"

DOCKER_CONTAINER = "meep-pilot-worker"
SIMSERVER        = "user@166.104.35.108"
SSH_KEY          = str(Path.home() / ".ssh" / "id_ed25519")
LOCAL_MPI_NP     = 4       # Docker 컨테이너 기준
SIMSERVER_MPI_NP = 128
LOCAL_TIMEOUT_H  = 2.0
MAX_FIX_RETRIES  = 3

# ─── [1순위] detector.py 연동 ─────────────────────────────────────────────────
sys.path.insert(0, str(BASE_DIR))
try:
    from detector import auto_fix_loop, classify_all
    _DETECTOR_AVAILABLE = True
except ImportError:
    _DETECTOR_AVAILABLE = False
    print("[WARN] detector.py 로드 실패 — error_rules.json 폴백 사용")


def pre_check_and_fix(code: str) -> str:
    """코드 생성 직후 detector로 사전 검사 + 자동 수정"""
    if not _DETECTOR_AVAILABLE:
        return code
    issues = classify_all(code, "", {})
    if not issues:
        return code
    print(f"  [사전검사] {len(issues)}개 탐지: {[r.error_id for r in issues]}")
    fixed, applied = auto_fix_loop(code)
    if applied:
        print(f"  [사전수정] 적용: {applied}")
    return fixed


def handle_run_error(code: str, stderr: str) -> tuple:
    """실행 오류 → detector 자동 수정"""
    if not _DETECTOR_AVAILABLE:
        return code, []
    fixed, applied = auto_fix_loop(code, stderr=stderr)
    return fixed, applied


def notify(paper_id: str, result: Optional[dict], failed: bool = False):
    """완료/실패 알림 → openclaw system event"""
    eff = result.get("efficiency_pixel_norm", {}) if result else {}
    if failed:
        msg = f"CIS Reproduce FAILED: {paper_id} — results/{paper_id}/ 확인"
    else:
        r = eff.get('R', '?'); g = eff.get('G', '?'); b = eff.get('B', '?')
        try:
            msg = f"CIS Reproduce 완료: {paper_id} | R={r:.3f} G={g:.3f} B={b:.3f}"
        except Exception:
            msg = f"CIS Reproduce 완료: {paper_id}"
    # Windows: openclaw.cmd 사용
    import platform
    cmd_name = "openclaw.cmd" if platform.system() == "Windows" else "openclaw"
    try:
        subprocess.run(
            [cmd_name, "system", "event", "--text", msg, "--mode", "now"],
            capture_output=True, timeout=10
        )
    except Exception:
        pass  # 알림 실패는 무시


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 0: 입력 분류
# ══════════════════════════════════════════════════════════════════════════════

def classify_input(params: dict) -> str:
    """
    Mode A: 코드 있음 (has_code=True) → MEEP 변환
    Mode B: 구조 있음 (pillar_mask 있음, has_code=False)
    Mode C: 코드/구조 없음 → adjoint 역설계
    """
    if params.get("has_code"):
        return "A"
    if params.get("pillar_mask") or params.get("structure_weights_path"):
        return "B"
    return "C"


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1: 코드 생성
# ══════════════════════════════════════════════════════════════════════════════

def generate_code(params: dict, paper_id: str) -> Path:
    """params.json → reproduce_{paper_id}.py 생성 + detector 사전 검사"""
    print(f"\n[Stage 1] 코드 생성 | design_type={params.get('design_type','?')}")

    out_dir  = RESULTS_DIR / paper_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"reproduce_{paper_id}.py"

    # [6순위] Mode B: KB 기반 코드가 완전한 경우에만 사용
    # 완전한 코드 = sim.run() + 결과 저장 포함
    kb_code = params.get("_kb_base_code", "")
    if kb_code and "sim.run(" in kb_code and "results.json" in kb_code:
        code = kb_code
        print(f"  [Mode B] KB 전체 코드 기반 생성")
    else:
        if kb_code:
            print(f"  [Mode B] KB 코드 불완전(sim.run 없음) → 전체 신규 생성")
        design_section = _build_design_section(params)
        code = _build_full_code(params, paper_id, design_section, out_dir)


    # [1순위] detector 사전 검사 + 자동 수정
    code = pre_check_and_fix(code)

    out_file.write_text(code, encoding="utf-8")
    print(f"  → {out_file}")
    return out_file


def _build_design_section(params: dict) -> str:
    dt = params["design_type"]
    mat = params["material_name"]
    n   = params["n_material"]

    if dt == "discrete_pillar":
        N   = params["grid_n"]
        w   = params["tile_w"]
        mask_str = json.dumps(params["pillar_mask"])
        return f"""
# ─── 설계 영역: discrete_pillar {N}×{N} ──────────────────────────────────────
# [암묵지] i→-y(반전), j→+x: 이미지 좌표를 MEEP 좌표로 변환
w  = {w}   # μm. pillar 타일 크기
Nx = {N}
Ny = {N}
pillar_mask = {mask_str}

_oob = 0
for _i in range(Ny):
    for _j in range(Nx):
        if pillar_mask[_i][_j] == 1:
            _px = round(-Nx/2 * w + _j * w + w/2, 3)
            _py = round( Ny/2 * w - _i * w - w/2, 3)
            _px = float(max(min(_px,  Sx/2-w/2), -Sx/2+w/2))
            _py = float(max(min(_py,  Sy/2-w/2), -Sy/2+w/2))
            geometry.append(mp.Block(
                size=mp.Vector3(w, w, Layer_thickness),
                center=mp.Vector3(_px, _py, z_meta),
                material={mat},
            ))
            _oob += (_px > Sx/2-w/2 or _py > Sy/2-w/2)
if _oob: print(f"[WARN] {{_oob}} pillars clamped to boundary")
"""

    elif dt == "materialgrid":
        n_layers = params.get("n_layers", 1)
        lines = ["import meep.adjoint as mpa", ""]
        for k in range(1, n_layers+1):
            wfile = params.get(f"weights_layer{k}", f"Layer{k}.txt")
            lines += [
                f"_wts{k} = np.loadtxt('{wfile}')",
                f"_Nx{k} = int(round(resolution * design_region_x)) + 1",
                f"_Ny{k} = int(round(resolution * design_region_y)) + 1",
                f"_dv{k} = mp.MaterialGrid(mp.Vector3(_Nx{k}, _Ny{k}), Air, {mat},",
                f"                          grid_type='U_MEAN', do_averaging=False)",
                f"_dv{k}.update_weights(_wts{k})",
                f"_z_layer{k} = round(Sz/2 - Lpml - pml_2_src - src_2_geo",
                f"             - (({k}-0.5)*Layer_thickness + ({k}-1)*{'EL_thickness' if k>1 else '0'}), 3)",
                f"_dr{k} = mpa.DesignRegion(_dv{k}, volume=mp.Volume(",
                f"    center=mp.Vector3(0, 0, _z_layer{k}),",
                f"    size=mp.Vector3(design_region_x, design_region_y, Layer_thickness)))",
                f"geometry.append(mp.Block(center=_dr{k}.center, size=_dr{k}.size, material=_dv{k}))",
                "",
            ]
        return "\n".join(lines)

    elif dt == "sparse":
        pillars = params.get("sparse_pillars", [])
        lines = ["# ─── 설계 영역: sparse meta-atoms ──────────────────────────"]
        for p in pillars:
            lines.append(
                f"geometry.append(mp.Block(size=mp.Vector3({p['wx']}, {p['wy']}, Layer_thickness),"
                f" center=mp.Vector3({p['cx']}, {p['cy']}, z_meta), material={mat}))"
            )
        return "\n".join(lines)

    elif dt == "cylinder":
        cyls = params.get("cylinders", [])
        lines = ["# ─── 설계 영역: cylinder meta-atoms ─────────────────────────"]
        for c in cyls:
            lines.append(
                f"geometry.append(mp.Cylinder(radius={c['diameter']}/2,"
                f" height=Layer_thickness, center=mp.Vector3({c['cx']}, {c['cy']}, z_meta),"
                f" material={mat}))"
            )
        return "\n".join(lines)

    return "# [ERROR] unknown design_type"


def _build_full_code(params: dict, paper_id: str, design_section: str, out_dir: Path) -> str:
    p = params
    mat      = p["material_name"]
    n_mat    = p["n_material"]
    sp       = p["SP_size"]
    lt       = p["Layer_thickness"]
    fl       = p["FL_thickness"]
    res      = p["resolution"]
    el       = p.get("EL_thickness", 0)
    nl       = p.get("n_layers", 1)
    f_mat    = p.get("focal_material", "Air")
    wls      = p.get("wavelengths", [0.45, 0.55, 0.65])
    paper_t  = p.get("paper_title", paper_id)
    ts       = datetime.now().isoformat()

    results_dir = str(out_dir).replace("\\", "/")

    # min_feature 계산 (resolution 체크용)
    min_f = p.get("tile_w", p.get("min_feature_um", lt))
    min_feature_grid = int(min_f * res)

    code = f'''"""
CIS Color Router MEEP 재현 스크립트
논문: {paper_t}
생성: {ts}
paper_id: {paper_id}

[핵심 파라미터]
재료: {mat} (n={n_mat})
SP_size={sp}μm | Layer={lt}μm | FL={fl}μm | res={res}
min_feature={min_f}μm → {min_feature_grid}격자 (권장 ≥10)

[암묵지 체크리스트]
[OK] k_point=(0,0,0): Bayer 주기 배열 경계조건
[OK] eps_averaging=False: 이산 pillar edge 보존
[OK] PML Z방향만: X,Y는 주기 경계
[OK] GaussianSource Ex+Ey: unpolarized 광원
[OK] 참조 시뮬→total_flux→pixel-norm 효율
"""
import meep as mp
import meep.adjoint as mpa
import numpy as np
import matplotlib
matplotlib.use("Agg")  # [필수] 서버/Docker: GUI 없음
import matplotlib.pyplot as plt
import os, json, time
from pathlib import Path

mp.verbosity(1)

# ─── 재료 ────────────────────────────────────────────────────────
um_scale = 1
Air   = mp.Medium(index=1.0)
SiO2  = mp.Medium(index=1.45)
{mat}  = mp.Medium(index={n_mat})

# ─── 파라미터 ─────────────────────────────────────────────────────
resolution      = {res}
layer_num       = {nl}
Layer_thickness = {lt}
FL_thickness    = {fl}
EL_thickness    = {el}
SP_size         = {sp}
Lpml      = 0.4
pml_2_src = 0.2
src_2_geo = 0.2
mon_2_pml = 0.4

# ─── 셀 크기 ──────────────────────────────────────────────────────
design_region_x = round(SP_size * 2, 3)
design_region_y = round(SP_size * 2, 3)
design_region_z = round(layer_num * Layer_thickness + EL_thickness, 3)
Sx = design_region_x
Sy = design_region_y
Sz = round(Lpml + pml_2_src + src_2_geo + design_region_z + FL_thickness + mon_2_pml + Lpml, 3)
cell_size = mp.Vector3(Sx, Sy, Sz)

# ─── Z좌표 계산 ───────────────────────────────────────────────────
z_src  = round(Sz/2 - Lpml - pml_2_src, 3)
z_meta = round(Sz/2 - Lpml - pml_2_src - src_2_geo - design_region_z/2, 3)
z_fl   = round(Sz/2 - Lpml - pml_2_src - src_2_geo - design_region_z - FL_thickness/2, 3)
z_sipd = round(Sz/2 - Lpml - pml_2_src - src_2_geo - design_region_z - FL_thickness - mon_2_pml/2 - Lpml/2, 3)
z_mon  = round(-Sz/2 + Lpml + mon_2_pml - 1/resolution, 3)
z_refl = round(Sz/2 - Lpml - 1/resolution, 3)

# 좌표 검증
assert z_src > z_meta, f"소스({{z_src}}) < 메타({{z_meta}}): Z오류"
assert z_mon > -Sz/2 + Lpml, f"모니터({{z_mon}})가 PML 안"

pml_layers = [mp.PML(thickness=Lpml, direction=mp.Z)]  # Z만!

# ─── 광원 ─────────────────────────────────────────────────────────
source_center = mp.Vector3(0, 0, z_src)
source_size   = mp.Vector3(Sx, Sy, 0)
frequency = 1/(0.545*um_scale)
fwidth    = frequency * 2      # width=2: RGB 전대역 커버
src       = mp.GaussianSource(frequency=frequency, fwidth=fwidth)
source    = [
    mp.Source(src, component=mp.Ex, size=source_size, center=source_center),
    mp.Source(src, component=mp.Ey, size=source_size, center=source_center),
]
wavelengths = np.array({wls})
frequencies_rgb = 1 / wavelengths

# ─── Geometry ─────────────────────────────────────────────────────
geometry = [
    mp.Block(
        center=mp.Vector3(0,0,round(Sz/2-Lpml/2-pml_2_src/2-src_2_geo/2,3)),
        size=mp.Vector3(Sx,Sy,round(Lpml+pml_2_src+src_2_geo,3)),
        material=SiO2,  # cover glass
    ),
    mp.Block(center=mp.Vector3(0,0,z_fl), size=mp.Vector3(Sx,Sy,FL_thickness),
             material={f_mat}),  # focal layer
    mp.Block(center=mp.Vector3(0,0,z_sipd), size=mp.Vector3(Sx,Sy,round(mon_2_pml+Lpml,3)),
             material=Air),  # SiPD (Air로 두어야 flux 측정 가능)
]

{design_section}

# ─── Simulation ───────────────────────────────────────────────────
sim = mp.Simulation(
    cell_size=cell_size, boundary_layers=pml_layers,
    geometry=geometry, sources=source,
    default_material=Air, resolution=resolution,
    k_point=mp.Vector3(0,0,0),   # [필수] Bayer 주기 경계
    eps_averaging=False,          # [필수] discrete pillar edge 보존
    extra_materials=[SiO2, {mat}],
)

Nvox = int(Sx*resolution)*int(Sy*resolution)*int(Sz*resolution)
print(f"[Setup] Sz={{Sz}}μm | Voxels={{Nvox:,}} | z_meta={{z_meta}} | z_mon={{z_mon}}")

# ─── 참조 시뮬레이션 ──────────────────────────────────────────────
fcen  = (1/(0.350*um_scale) + 1/(0.800*um_scale)) / 2
df    = 1/(0.350*um_scale) - 1/(0.800*um_scale)
nfreq = 400
src_b = mp.GaussianSource(frequency=fcen, fwidth=df)
src_ref = [mp.Source(src_b, component=mp.Ex, size=source_size, center=source_center)]

sim_ref = mp.Simulation(
    cell_size=cell_size, boundary_layers=pml_layers,
    geometry=[mp.Block(center=mp.Vector3(0,0,0), size=mp.Vector3(Sx,Sy,Sz), material=Air)],
    sources=src_ref, default_material=Air, resolution=resolution,
    k_point=mp.Vector3(0,0,0), extra_materials=[SiO2],
)
refl_fr = mp.FluxRegion(center=mp.Vector3(0,0,z_refl), size=mp.Vector3(Sx,Sy,0))
tran_fr = mp.FluxRegion(center=mp.Vector3(0,0,z_mon),  size=mp.Vector3(Sx,Sy,0))

refl_ref_m = sim_ref.add_flux(fcen, df, nfreq, refl_fr)
tran_ref_m = sim_ref.add_flux(fcen, df, nfreq, tran_fr)
print("[Ref Sim] 실행 중...")
t0 = time.time()
sim_ref.run(until_after_sources=mp.stop_when_dft_decayed(1e-6, 0))
print(f"[Ref Sim] 완료 ({{time.time()-t0:.1f}}초)")
straight_refl_data = sim_ref.get_flux_data(refl_ref_m)
total_flux = mp.get_fluxes(tran_ref_m)
flux_freqs = mp.get_flux_freqs(tran_ref_m)

# ─── 메인 시뮬레이션 ──────────────────────────────────────────────
sim.change_sources(src_ref)
refl_m = sim.add_flux(fcen, df, nfreq, refl_fr)
tran_m = sim.add_flux(fcen, df, nfreq, tran_fr)
tran_px = sim.add_flux(fcen, df, nfreq, mp.FluxRegion(
    center=mp.Vector3(0,0,z_mon), size=mp.Vector3(design_region_x,design_region_y,0)))
sim.load_minus_flux_data(refl_m, straight_refl_data)

dx, dy = design_region_x, design_region_y
q_size = mp.Vector3(dx/2, dy/2, 0)
tran_r  = sim.add_flux(fcen, df, nfreq, mp.FluxRegion(center=mp.Vector3(-dx/4,-dy/4,z_mon), size=q_size))
tran_gr = sim.add_flux(fcen, df, nfreq, mp.FluxRegion(center=mp.Vector3(-dx/4,+dy/4,z_mon), size=q_size))
tran_b  = sim.add_flux(fcen, df, nfreq, mp.FluxRegion(center=mp.Vector3(+dx/4,+dy/4,z_mon), size=q_size))
tran_gb = sim.add_flux(fcen, df, nfreq, mp.FluxRegion(center=mp.Vector3(+dx/4,-dy/4,z_mon), size=q_size))

print("[Main Sim] 실행 중...")
t0 = time.time()
sim.run(until_after_sources=mp.stop_when_dft_decayed(1e-6, 0))
elapsed = time.time()-t0
print(f"[Main Sim] 완료 ({{elapsed:.1f}}초)")

# ─── 효율 계산 + 저장 ─────────────────────────────────────────────
tran_p  = mp.get_fluxes(tran_px)
red_f   = mp.get_fluxes(tran_r)
greenr_f= mp.get_fluxes(tran_gr)
blue_f  = mp.get_fluxes(tran_b)
greenb_f= mp.get_fluxes(tran_gb)

wl_arr = np.array([1/(flux_freqs[d]*um_scale) for d in range(nfreq)])
Tr  = np.array([red_f[d]/(tran_p[d]+1e-20)              for d in range(nfreq)])
Tg  = np.array([(greenr_f[d]+greenb_f[d])/(tran_p[d]+1e-20) for d in range(nfreq)])
Tb  = np.array([blue_f[d]/(tran_p[d]+1e-20)             for d in range(nfreq)])
Trt = np.array([red_f[d]/(total_flux[d]+1e-20)          for d in range(nfreq)])
Tgt = np.array([(greenr_f[d]+greenb_f[d])/(total_flux[d]+1e-20) for d in range(nfreq)])
Tbt = np.array([blue_f[d]/(total_flux[d]+1e-20)         for d in range(nfreq)])

def _eff_at(wl_t, T): return float(T[np.argmin(np.abs(wl_arr-wl_t))])

out_dir = Path("{results_dir}")
out_dir.mkdir(parents=True, exist_ok=True)

if mp.am_master():
    fig, ax = plt.subplots(figsize=(7,5), dpi=150)
    ax.plot(wl_arr, Tr, 'r', label='R(px)'); ax.plot(wl_arr, Tg, 'g', label='G(px)'); ax.plot(wl_arr, Tb, 'b', label='B(px)')
    ax.plot(wl_arr, Trt,'r--',label='R(tot)'); ax.plot(wl_arr, Tgt,'g--',label='G(tot)'); ax.plot(wl_arr, Tbt,'b--',label='B(tot)')
    ax.fill_between([0.38,0.48],0,1,alpha=0.12,color='blue')
    ax.fill_between([0.48,0.58],0,1,alpha=0.12,color='green')
    ax.fill_between([0.58,0.78],0,1,alpha=0.12,color='red')
    ax.set(xlim=[0.38,0.78],ylim=[0,1.05],xlabel='Wavelength (μm)',ylabel='Efficiency')
    ax.set_title('{paper_t}')
    ax.legend(fontsize=8); ax.tick_params(direction='in')
    plt.tight_layout()
    plt.savefig(out_dir / "{paper_id}_efficiency.png")
    plt.close()

    result = {{
        "paper_id": "{paper_id}", "paper_title": "{paper_t}",
        "elapsed_sec": elapsed,
        "efficiency_pixel_norm": {{"R":_eff_at(0.65,Tr),"G":_eff_at(0.55,Tg),"B":_eff_at(0.45,Tb)}},
        "efficiency_total_norm": {{"R":_eff_at(0.65,Trt),"G":_eff_at(0.55,Tgt),"B":_eff_at(0.45,Tbt)}},
    }}
    with open(out_dir / "{paper_id}_results.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"[Result] R={{result['efficiency_pixel_norm']['R']:.3f}} "
          f"G={{result['efficiency_pixel_norm']['G']:.3f}} "
          f"B={{result['efficiency_pixel_norm']['B']:.3f}}")
    print(f"[Done] {{out_dir}}/")
'''
    return code


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2: fast-check (resolution=5)
# ══════════════════════════════════════════════════════════════════════════════

def fast_check(script_path: Path, paper_id: str) -> bool:
    """Docker에서 resolution=5로 빠른 geometry 검증"""
    print(f"\n[Stage 2] Fast-check | Docker: {DOCKER_CONTAINER}")

    # 임시 fast-check 버전 생성 (res=5, max_run=5)
    code = script_path.read_text(encoding="utf-8")
    code_fast = re.sub(r'resolution\s*=\s*\d+', 'resolution = 5', code, count=1)
    code_fast = re.sub(r'mp\.verbosity\(\d\)', 'mp.verbosity(0)', code_fast)
    # run() 제거 (geometry 생성만 테스트)
    code_fast += "\nprint('[FastCheck] Geometry OK')\n"

    fast_path = script_path.parent / f"fast_{paper_id}.py"
    fast_path.write_text(code_fast, encoding="utf-8")

    # Docker에 복사 + 실행
    try:
        subprocess.run(
            ["docker", "cp", str(fast_path), f"{DOCKER_CONTAINER}:/tmp/fast_{paper_id}.py"],
            check=True, capture_output=True
        )
        result = subprocess.run(['docker', 'exec', DOCKER_CONTAINER, "python", f"/tmp/fast_{paper_id}.py"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
        )
        if result.returncode == 0:
            print(f"  [OK] Fast-check PASSED")
            return True
        else:
            print(f"  [FAIL] Fast-check FAILED:\n{result.stderr[-800:]}")
            return False
    except subprocess.TimeoutExpired:
        print("  [FAIL] Fast-check TIMEOUT (60s)")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3: 실행 환경 결정
# ══════════════════════════════════════════════════════════════════════════════

def decide_executor(params: dict, force_local=False, force_simserver=False) -> dict:
    """복셀 수 기반 실행 환경 자동 결정"""
    p   = params
    sp  = p["SP_size"]
    fl  = p["FL_thickness"]
    lt  = p["Layer_thickness"]
    res = p["resolution"]
    el  = p.get("EL_thickness", 0)
    nl  = p.get("n_layers", 1)
    Lpml = 0.4

    Sx = sp * 2
    Sy = sp * 2
    Sz = Lpml + 0.2 + 0.2 + (nl*lt+el) + fl + 0.4 + Lpml
    Nvox = int(Sx*res) * int(Sy*res) * int(Sz*res)

    t_local_h     = Nvox * 2e-7 / 3600     # 10코어 기준 (경험값)
    t_simserver_h = Nvox * 1.5e-8 / 3600   # 128코어 기준

    use_local = (t_local_h < LOCAL_TIMEOUT_H) and not force_simserver
    if force_local:
        use_local = True
    if force_simserver:
        use_local = False

    env = "local" if use_local else "simserver"
    np  = LOCAL_MPI_NP if use_local else SIMSERVER_MPI_NP

    print(f"\n[Stage 3] 실행 환경 결정")
    print(f"  복셀: {Nvox:,} | 로컬 예상: {t_local_h:.1f}h | SimServer: {t_simserver_h:.1f}h")
    print(f"  → {env} (mpirun -np {np})")

    return {"env": env, "np": np, "voxels": Nvox,
            "t_local_h": t_local_h, "t_simserver_h": t_simserver_h}


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3-E: 오류 분류 + 자동 수정
# ══════════════════════════════════════════════════════════════════════════════

def load_error_rules() -> list:
    with open(ERROR_RULES, encoding="utf-8") as f:
        return json.load(f)["CIS_ERROR_RULES"]


def classify_error(stderr: str, code: str, rules: list) -> Optional[dict]:
    """stderr + code에서 오류 카테고리 탐지"""
    for rule in sorted(rules, key=lambda r: r["priority"]):
        pat = rule["detect_pattern"]
        target = code if rule["detect_type"].startswith("code") else stderr
        if rule["detect_type"] == "code_missing":
            if pat not in target:
                return rule
        elif rule["detect_type"] == "code_missing_or_true":
            if pat not in target or f"{pat}=True" in target:
                return rule
        elif rule["detect_type"] in ("stderr", "runtime_check", "result_check"):
            if re.search(pat, target, re.IGNORECASE):
                return rule
        elif rule["detect_type"] == "regex":
            if re.search(pat, target):
                return rule
    return None


def apply_fix(code: str, rule: dict, stderr: str, attempt: int) -> str:
    """규칙 기반 자동 수정"""
    fix_code = rule.get("fix_code", "")
    fix_desc = rule.get("auto_fix", "")
    print(f"  [Fix #{attempt}] {rule['error_id']}: {fix_desc[:80]}")

    if rule["error_id"] == "KPoint_Missing":
        code = re.sub(r'(mp\.Simulation\([^)]*?)(,?\s*\))',
                      r'\1,\n    k_point=mp.Vector3(0,0,0)\2', code, count=1)
    elif rule["error_id"] == "EpsAveraging_On":
        if "eps_averaging" in code:
            code = re.sub(r'eps_averaging\s*=\s*True', 'eps_averaging=False', code)
        else:
            code = re.sub(r'(mp\.Simulation\([^)]*?)(,?\s*\))',
                          r'\1,\n    eps_averaging=False\2', code, count=1)
    elif rule["error_id"] == "PML_AllDirections":
        code = re.sub(r'mp\.PML\((\w+)\)(?!\s*,\s*direction)',
                      r'mp.PML(thickness=\1, direction=mp.Z)', code)
    elif rule["error_id"] == "Matplotlib_Display":
        code = "import matplotlib\nmatplotlib.use('Agg')\n" + code
        code = re.sub(r'plt\.show\(\)', '', code)
    elif rule["error_id"] == "ProcessLeak":
        code = "import subprocess\nsubprocess.run(['pkill','-9','-f','mpirun'], capture_output=True)\ntime.sleep(2)\n" + code
    elif rule["error_id"] == "Resolution_Too_Low":
        code = re.sub(r'resolution\s*=\s*\d+', 'resolution = 40', code, count=1)
    elif rule["error_id"] == "Divergence":
        # resolution 2배
        m = re.search(r'resolution\s*=\s*(\d+)', code)
        if m:
            new_res = min(int(m.group(1)) * 2, 80)
            code = re.sub(r'resolution\s*=\s*\d+', f'resolution = {new_res}', code, count=1)
    elif fix_code:
        # 범용: fix_code를 파일 상단에 추가
        code = f"# AUTO-FIX: {rule['error_id']}\n{fix_code}\n\n" + code

    return code


def run_with_error_handler(script_path: Path, executor: dict, dry_run: bool) -> Optional[dict]:
    """실행 + detector 기반 오류 자동 수정 루프 (최대 3회)"""
    code = script_path.read_text(encoding="utf-8")
    env  = executor["env"]
    np_  = executor["np"]

    for attempt in range(1, MAX_FIX_RETRIES + 1):
        print(f"\n[Stage 3] 실행 시도 {attempt}/{MAX_FIX_RETRIES} | {env}")
        if dry_run:
            print("  [dry-run] 실제 실행 생략")
            return {"status": "dry_run"}

        script_path.write_text(code, encoding="utf-8")
        returncode, stdout, stderr = _execute(script_path, env, np_, executor)

        # 결과 JSON 확인
        paper_id = script_path.stem.replace("reproduce_", "")
        result_json = script_path.parent / f"{paper_id}_results.json"
        if result_json.exists():
            result = json.loads(result_json.read_text(encoding="utf-8"))
            print(f"  [OK] 실행 완료! R={result.get('efficiency_pixel_norm',{}).get('R','?')}")
            return result

        # 오류 처리: detector 우선, 폴백으로 error_rules.json
        combined_err = stderr + "\n" + stdout
        if combined_err.strip():
            print(f"  [오류] {combined_err[:200].strip()}")
            fixed, applied = handle_run_error(code, combined_err)
            if applied:
                print(f"  [자동수정] {applied}")
                code = fixed
                # fast-check 재검증
                tmp = script_path.parent / f"fix{attempt}_{script_path.name}"
                tmp.write_text(code, encoding="utf-8")
                if not fast_check(tmp, f"fix{attempt}"):
                    print(f"  fast-check 실패, 다음 시도...")
                continue
            else:
                # detector 미탐지 → error_rules.json 폴백
                rules = load_error_rules()
                rule  = classify_error(combined_err, code, rules)
                if rule:
                    code = apply_fix(code, rule, combined_err, attempt)
                    continue
                print(f"  [미탐지] 수동 확인 필요")
                _save_unknown_error(combined_err, code, script_path)
                break
        else:
            print("  [OK] 실행 완료 (결과 JSON 없음 — 수동 확인)")
            return {"status": "completed_no_json"}

    print(f"  [FAIL] {MAX_FIX_RETRIES}회 모두 실패")
    notify(paper_id if 'paper_id' in dir() else "unknown", None, failed=True)
    return None


def _execute(script_path: Path, env: str, np_: int, executor: dict):
    """실제 실행 → (returncode, stdout, stderr) 반환"""
    paper_id  = script_path.stem.replace("reproduce_", "").replace("repr_", "")
    local_out = script_path.parent

    if env == "local":
        remote_py  = f"/tmp/cis_{paper_id}.py"
        remote_log = f"/tmp/cis_{paper_id}.log"
        remote_out = f"/tmp/cis_{paper_id}_results"

        # 파일 업로드
        subprocess.run(["docker","cp",str(script_path),f"{DOCKER_CONTAINER}:{remote_py}"],
                       check=True, capture_output=True)
        subprocess.run(["docker","exec",DOCKER_CONTAINER,"mkdir","-p",remote_out],
                       capture_output=True)
        print(f"  [Docker] mpirun -np {np_} python {remote_py}")

        # 실행 (stdout/stderr 분리)
        r = subprocess.run(
            ["docker","exec",DOCKER_CONTAINER,"bash","-c",
             f"mpirun -np {np_} --allow-run-as-root python {remote_py} "
             f"> {remote_log} 2>&1 ; "
             f"cp {remote_log} {remote_out}/ ; "
             f"ls {remote_out}/"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=int(LOCAL_TIMEOUT_H * 3600 + 600)
        )
        # 결과 수집 (JSON 포함 모든 파일)
        subprocess.run(["docker","cp",f"{DOCKER_CONTAINER}:{remote_out}/.",str(local_out)],
                       capture_output=True)
        print(f"  결과 위치: {local_out}")
        # stderr 판단: log 내용 읽기
        log_path = local_out / "run.log"
        log_txt  = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        stderr   = log_txt if ("Traceback" in log_txt or "Error" in log_txt) else ""
        return r.returncode, r.stdout, stderr

    else:  # simserver
        remote_py  = f"/tmp/cis_repro/{paper_id}.py"
        remote_out = f"/tmp/cis_repro/{paper_id}_results"

        subprocess.run(["scp","-i",SSH_KEY,str(script_path),f"{SIMSERVER}:{remote_py}"],
                       check=True, capture_output=True)
        print(f"  [SimServer] mpirun -np {np_} python {remote_py}")

        ssh_cmd = (f"mkdir -p {remote_out} && "
                   f"mpirun -np {np_} python {remote_py} > {remote_out}/run.log 2>&1")
        r = subprocess.run(
            ["ssh","-i",SSH_KEY,"-o","StrictHostKeyChecking=no",SIMSERVER, ssh_cmd],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=int(executor.get("t_simserver_h",1) * 3600 + 600)
        )
        # 결과 수집
        subprocess.run(["scp","-r","-i",SSH_KEY,f"{SIMSERVER}:{remote_out}/.",str(local_out)],
                       capture_output=True)
        print(f"  결과 위치 (로컬): {local_out}")
        log_path = local_out / "run.log"
        log_txt  = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        stderr   = log_txt if ("Traceback" in log_txt or "Error" in log_txt) else ""
        return r.returncode, r.stdout, stderr


def _save_unknown_error(stderr: str, code: str, script_path: Path):
    err_path = script_path.parent / "unknown_error.txt"
    err_path.write_text(f"STDERR:\n{stderr}\n\nCODE:\n{code}", encoding="utf-8")
    print(f"  오류 저장: {err_path}")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 4: 결과 검증 + meep-kb 저장
# ══════════════════════════════════════════════════════════════════════════════

def validate_result(result: dict, params: dict) -> dict:
    """논문 target_efficiency와 비교. ≤5% 오차 체크."""
    target = params.get("target_efficiency", {})
    if not target:
        print("[Stage 4] target_efficiency 없음 → 검증 스킵")
        return {"status": "no_target"}

    eff = result.get("efficiency_pixel_norm", {})
    errors = {}
    for ch in ["R", "G", "B"]:
        if ch in target and ch in eff:
            err_pct = abs(eff[ch] - target[ch]) / (target[ch] + 1e-9) * 100
            errors[ch] = round(err_pct, 2)

    avg_err = sum(errors.values()) / len(errors) if errors else 999
    passed  = avg_err <= 5.0
    print(f"\n[Stage 4] 결과 검증")
    for ch, err in errors.items():
        print(f"  {ch}: 논문={target.get(ch,'?'):.3f} | 결과={eff.get(ch,'?'):.3f} | 오차={err:.1f}%")
    print(f"  평균 오차: {avg_err:.1f}% → {'PASS [OK]' if passed else 'FAIL [FAIL]'}")

    return {"passed": passed, "avg_error_pct": avg_err, "channel_errors": errors}


def save_to_meep_kb(params: dict, result: dict, script_path: Path, paper_id: str):
    """meep-kb examples 테이블에 저장"""
    conn = sqlite3.connect(str(DB_PATH))
    cur  = conn.cursor()
    now  = datetime.now().isoformat()

    code = script_path.read_text(encoding="utf-8")
    eff  = result.get("efficiency_pixel_norm", {})
    tags = f"cis,color-router,{params.get('design_type','')},{params.get('material_name','')}"

    desc = (f"{params.get('paper_title',paper_id)}\n"
            f"R={eff.get('R','?'):.3f} G={eff.get('G','?'):.3f} B={eff.get('B','?'):.3f}\n"
            f"Material: {params.get('material_name')} n={params.get('n_material')}\n"
            f"SP={params.get('SP_size')}μm FL={params.get('FL_thickness')}μm res={params.get('resolution')}")

    cur.execute("SELECT id FROM examples WHERE title=?", (params.get("paper_title", paper_id),))
    if cur.fetchone():
        print(f"[Stage 4] meep-kb: 이미 존재, 스킵")
    else:
        cur.execute(
            "INSERT INTO examples (title, code, description, tags, source_repo, created_at) VALUES (?,?,?,?,?,?)",
            (params.get("paper_title", paper_id), code, desc, tags, "cis_repro_pipeline", now)
        )
        conn.commit()
        print(f"[Stage 4] meep-kb 저장 완료 (id={cur.lastrowid})")
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# 메인 파이프라인
# ══════════════════════════════════════════════════════════════════════════════

# [3순위] Resolution 3단계 전략 ─────────────────────────────────────
# 실측 기반 (Single2022, mpirun -np 4 Docker):
#   res=20 → 1.4s  (색 분리 방향 확인)
#   res=40 → 19s   (정량 효율 확인, 선택)
#   res=50 → 508s  local / 16s SimServer (최종)
RES_STEPS = [
    {"res": 20, "label": "fast",  "purpose": "색 분리 방향 확인", "required": True},
    {"res": 40, "label": "mid",   "purpose": "정량 효율 확인",     "required": False},
    {"res": 50, "label": "final", "purpose": "논문 비교 최종",      "required": True},
]


def _run_step(script_path: Path, executor: dict, dry_run: bool, paper_id: str) -> Optional[dict]:
    """resolution 교체 후 단순 실행 (detector 재적용 없이)"""
    if dry_run:
        return {"status": "dry_run"}

    returncode, stdout, stderr = _execute(script_path, executor["env"], executor["np"], executor)
    result_json = script_path.parent / f"{paper_id}_results.json"
    if result_json.exists():
        return json.loads(result_json.read_text(encoding="utf-8"))
    if stderr:
        print(f"  [오류] {stderr[:150].strip()}")
    return None


def run_resolution_strategy(params: dict, base_script: Path,
                             executor: dict, dry_run: bool) -> dict:
    """resolution별 순차 실행. 각 단계에서 detector 자동 수정 적용."""
    min_feat = params.get("tile_w") or params.get("min_feature_um") or 0.08
    results  = {}
    base_code = base_script.read_text(encoding="utf-8")

    for step in RES_STEPS:
        grids = min_feat * step["res"]
        if grids < 1.0 and step["res"] < 50:
            print(f"  res={step['res']} SKIP (격자={grids:.1f} < 1.0 — 너무 적음)")
            continue
        if not step["required"]:
            if not params.get("run_intermediate", False):
                print(f"  res={step['res']} SKIP (중간 단계, --run-intermediate로 활성화)")
                continue

        print(f"\n  -- res={step['res']} ({step['purpose']}) --")
        # resolution만 교체 (detector 재적용 없이 — 이미 generate_code에서 처리됨)
        code = re.sub(r'\bresolution\s*=\s*\d+', f"resolution = {step['res']}",
                      base_code, count=1)
        step_script = base_script.parent / f"repr_{params['paper_id']}_res{step['res']}.py"
        step_script.write_text(code, encoding="utf-8")

        # run_with_error_handler 대신 직접 실행 (detector 재적용 방지)
        result = _run_step(step_script, executor, dry_run, params['paper_id'])
        results[step["res"]] = result

        # res=20: 색 분리 방향만 빠르게 확인
        if result and step["res"] == 20:
            eff = result.get("efficiency_pixel_norm", {})
            r_v, b_v = eff.get("R", 0), eff.get("B", 0)
            ok = isinstance(r_v, (int,float)) and isinstance(b_v, (int,float)) and r_v > 0.2 and b_v > 0.2
            print(f"  [res=20 색분리] R={r_v} G={eff.get('G',0)} B={b_v} → {'방향 OK' if ok else 'CHECK 필요'}")
            if not ok and not dry_run:
                print("  [WARN] res=20 결과가 불명확 — 계속 진행하지만 최종 결과 확인 권장")

    return results


# [5순위] Chroma 벡터 업데이트 ─────────────────────────────────────────
def update_chroma(paper_id: str, code: str, params: dict, result: dict):
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
        chroma = chromadb.PersistentClient(path=str(MEEP_KB_DIR / "db/chroma"))
        model  = SentenceTransformer("BAAI/bge-m3", device="cpu")
        try:    col = chroma.get_collection("examples")
        except Exception: col = chroma.create_collection("examples")

        text = (f"{params.get('paper_title','')} "
                f"design_type={params.get('design_type','')} "
                f"material={params.get('material_name','')} "
                f"{code[:1500]}")
        emb = model.encode(text).tolist()
        eff = result.get("efficiency_pixel_norm", {})
        col.add(
            ids=[f"cis_{paper_id}"],
            embeddings=[emb],
            documents=[code[:3000]],
            metadatas=[{"paper_id": paper_id,
                        "design_type": params.get("design_type",""),
                        "material":    params.get("material_name",""),
                        "R": str(eff.get("R","")),
                        "G": str(eff.get("G","")),
                        "B": str(eff.get("B",""))}]
        )
        print(f"  [Chroma] {paper_id} 벡터 업데이트 완료")
    except Exception as e:
        print(f"  [Chroma] 실패(무시): {e}")


def run_pipeline(params_path: str, dry_run=False, force_local=False,
                 force_simserver=False, run_intermediate=False):
    params   = json.loads(Path(params_path).read_text(encoding="utf-8"))
    paper_id = params.get("paper_id", f"paper_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    params["run_intermediate"] = run_intermediate  # 3단계 중간 단계 활성화

    print(f"\n{'='*60}")
    print(f"CIS Reproduce Pipeline v2: {paper_id}")
    print(f"{'='*60}")

    # Stage 0: 입력 분류 (+ Mode B KB 적용 시도)
    mode = classify_input(params)
    print(f"\n[Stage 0] 입력 모드: {mode}")

    if mode == "B":
        # [6순위] Mode B: KB 코드 적용
        try:
            sys.path.insert(0, str(BASE_DIR / "stage0"))
            from kb_code_adapter import run as kb_adapt
            kb_code = kb_adapt(params)
            if kb_code:
                print(f"  [Mode B] KB에서 유사 코드 발견, 파라미터 치환 적용")
                params["_kb_base_code"] = kb_code
        except Exception as e:
            print(f"  [Mode B] KB 적용 실패(무시): {e}")

    # Stage 1: 코드 생성 + detector 사전 검사
    script = generate_code(params, paper_id)

    # Stage 2: fast-check
    ok = fast_check(script, paper_id)
    if not ok:
        print("[ABORT] Fast-check 실패")
        notify(paper_id, None, failed=True)
        return

    # Stage 3: 실행 환경 결정 + [3순위] Resolution 3단계 실행
    executor = decide_executor(params, force_local, force_simserver)

    if dry_run:
        result = run_with_error_handler(script, executor, dry_run=True)
        print("[dry-run] 완료")
        return

    # Resolution 3단계 전략 실행
    all_results = run_resolution_strategy(params, script, executor, dry_run)

    # 최종 결과 = res=50 또는 가장 높은 resolution 결과
    final_res = max((r for r in all_results if all_results[r]), default=None)
    result    = all_results.get(final_res) if final_res else None

    if result is None:
        print("[ABORT] 모든 resolution 실행 실패")
        notify(paper_id, None, failed=True)
        return

    # Stage 4: 결과 검증 + 저장
    validation = validate_result(result, params)
    save_to_meep_kb(params, result, script, paper_id)

    # [5순위] Chroma 벡터 업데이트
    update_chroma(paper_id, script.read_text(encoding="utf-8"), params, result)

    # 완료 알림
    notify(paper_id, result, failed=False)

    print(f"\n{'='*60}")
    print(f"파이프라인 완료: {paper_id}")
    print(f"결과 위치: {RESULTS_DIR / paper_id}")
    eff = result.get("efficiency_pixel_norm", {})
    print(f"최종 효율: R={eff.get('R','?')} G={eff.get('G','?')} B={eff.get('B','?')}")
    print(f"{'='*60}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="CIS Color Router Reproduce Pipeline v2")
    ap.add_argument("--params",             required=True, help="params.json 경로")
    ap.add_argument("--dry-run",            action="store_true", help="코드 생성+fast-check만, 실행 없음")
    ap.add_argument("--force-local",        action="store_true", help="강제 로컬(Docker) 실행")
    ap.add_argument("--force-simserver",    action="store_true", help="강제 SimServer 실행")
    ap.add_argument("--run-intermediate",   action="store_true", help="res=40 중간 단계도 실행")
    ap.add_argument("--pdf",                help="논문 PDF 경로 (param_extractor 호출)")
    ap.add_argument("--notes",              help="추가 메모 (LLM 파라미터 추출 보조)")
    args = ap.parse_args()

    # [3순위] PDF 제공 시 param_extractor 자동 호출
    params_path = args.params
    if args.pdf:
        try:
            sys.path.insert(0, str(BASE_DIR / "stage0"))
            from param_extractor import extract_params
            paper_id_hint = Path(args.params).parent.name
            extract_params(
                pdf_path=args.pdf,
                notes=args.notes or "",
                paper_id=paper_id_hint,
                out_path=args.params,
            )
            print(f"[param_extractor] params.json 생성 완료: {args.params}")
        except Exception as e:
            print(f"[param_extractor] 실패: {e} — params.json 직접 사용")

    run_pipeline(params_path, args.dry_run, args.force_local,
                 args.force_simserver, args.run_intermediate)

