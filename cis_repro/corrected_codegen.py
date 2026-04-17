"""
오차 패턴 DB를 반영한 교정된 코드 생성기
==========================================

아키텍처:
  params.json  ←→  error_patterns.json (논문별 override)
       ↓
  CodeGenerator (override 적용)
       ↓
  corrected_reproduce_{pid}.py
       ↓
  Docker 실행 → 결과
       ↓
  결과 오차 계산 → error_patterns.json 업데이트 (학습)

핵심 수정 사항:
  1. stop_decay:     논문별 원본값 사용
  2. source_count:   정확히 2개 (Ex+Ey)
  3. ref_sim_type:   'air' or 'with_cover'
  4. cover_glass:    논문별 on/off
  5. extra_materials: 실제 사용 재료 모두 포함
  6. sipd_material:  논문별 Air/SiO2
"""
import json, re, subprocess, time
from pathlib import Path
from datetime import datetime
import sys

BASE     = Path(__file__).parent
NB_DIR   = Path(r"C:\Users\user\.openclaw\workspace\dev\cis_reproduce")
RESULTS  = BASE / "results"
DOCKER   = "meep-pilot-worker"

sys.path.insert(0, str(BASE))
from detector import classify_all, auto_fix_loop
from pipeline import _build_design_section

# 오차 패턴 DB 로드
EP = json.loads((BASE / "error_patterns.json").read_text(encoding="utf-8"))
GLOBAL_RULES = EP["global_rules"]
PAPER_OVERRIDES = EP["paper_specific"]


# ══════════════════════════════════════════════════════════════
# 교정된 코드 생성
# ══════════════════════════════════════════════════════════════

def build_corrected_code(params: dict, paper_id: str) -> str:
    """
    error_patterns.json override를 적용한 수정 코드 생성
    """
    p = params
    ov = PAPER_OVERRIDES.get(paper_id, {}).get("overrides", {})

    mat      = p["material_name"]
    n_mat    = p["n_material"]
    sp       = p["SP_size"]
    lt       = p["Layer_thickness"]
    fl       = p["FL_thickness"]
    res      = p["resolution"]
    el       = p.get("EL_thickness", 0)
    nl       = p.get("n_layers", 1)
    paper_t  = p.get("paper_title", paper_id)
    wls      = p.get("wavelengths", [0.45, 0.55, 0.65])
    ts       = datetime.now().isoformat()

    # Override 적용
    stop_decay    = ov.get("stop_decay", "1e-6")
    ref_sim_type  = ov.get("ref_sim_type", "air")
    cover_glass   = ov.get("cover_glass", True)
    source_count  = ov.get("source_count", 2)
    sipd_mat      = ov.get("sipd_material", "Air")
    extra_mats    = ov.get("extra_materials", ["SiO2", mat])

    # [신규] Bayer 4분면 배치 설정
    # "standard": R(-x,-y) Gr(-x,+y) B(+x,+y) Gb(+x,-y) — Single2022 등
    # "sma":      R(-x,+y) Gr(-x,-y) B(+x,-y) Gb(+x,+y) — SMA 원본
    bayer_cfg = ov.get("bayer_config", "standard")

    # focal material
    focal_mat_str = p.get("focal_material", "Air")

    # Bayer 4분면 flux 코드 (bayer_config에 따라 분기)
    if bayer_cfg == "sma":
        # SMA 원본: R(-x,+y) Gr(-x,-y) B(+x,-y) Gb(+x,+y)
        _bayer_flux_code = (
            "tR  = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(-dx/4,+dy/4,z_mon),size=q))\n"
            "tGr = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(-dx/4,-dy/4,z_mon),size=q))\n"
            "tB  = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(+dx/4,-dy/4,z_mon),size=q))\n"
            "tGb = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(+dx/4,+dy/4,z_mon),size=q))"
        )
    else:
        # standard: R(-x,-y) Gr(-x,+y) B(+x,+y) Gb(+x,-y) — Single2022 등
        _bayer_flux_code = (
            "tR  = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(-dx/4,-dy/4,z_mon),size=q))\n"
            "tGr = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(-dx/4,+dy/4,z_mon),size=q))\n"
            "tB  = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(+dx/4,+dy/4,z_mon),size=q))\n"
            "tGb = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(+dx/4,-dy/4,z_mon),size=q))"
        )

    # 설계 섹션 (design_type별)
    design_section = _build_design_section(p)

    # Source 섹션
    if source_count == 1:
        src_lines = "    mp.Source(src, component=mp.Ex, size=source_size, center=source_center),"
    else:
        src_lines = (
            "    mp.Source(src, component=mp.Ex, size=source_size, center=source_center),\n"
            "    mp.Source(src, component=mp.Ey, size=source_size, center=source_center),"
        )

    # Cover glass 섹션
    cover_block = ""
    if cover_glass:
        cover_block = f"""    mp.Block(
        center=mp.Vector3(0,0,round(Sz/2-Lpml/2-pml_2_src/2-src_2_geo/2,3)),
        size=mp.Vector3(Sx,Sy,round(Lpml+pml_2_src+src_2_geo,3)),
        material=SiO2,
    ),"""

    # 참조 시뮬 geometry
    if ref_sim_type == "with_cover":
        ref_geo = f"""[mp.Block(
        center=mp.Vector3(0,0,round(Sz/2-Lpml/2-pml_2_src/2-src_2_geo/2,2)),
        size=mp.Vector3(Sx,Sy,round(Lpml+pml_2_src+src_2_geo,3)),
        material=SiO2,
    )]"""
    else:  # 'air'
        ref_geo = "[mp.Block(center=mp.Vector3(0,0,0), size=mp.Vector3(Sx,Sy,Sz), material=Air)]"

    # extra_materials 문자열
    extra_str = ", ".join(extra_mats)

    # EL spacer (multilayer)
    el_spacer = ""
    if nl > 1 and el > 0:
        el_mat = PAPER_OVERRIDES.get(paper_id, {}).get("overrides", {}).get("el_spacer_material", "SiN")
        el_spacer = f"""    mp.Block(
        center=mp.Vector3(0, 0, round(Sz/2-Lpml-pml_2_src-src_2_geo-Layer_thickness-EL_thickness/2, 3)),
        size=mp.Vector3(Sx, Sy, EL_thickness),
        material={el_mat},
    ),"""

    # 오차 패턴 주석 생성
    errors = PAPER_OVERRIDES.get(paper_id, {}).get("confirmed_errors", [])
    error_comments = "\n".join(
        f"#   [{e['id']}] {e['name']}: {e['description'][:60]}..." if len(e['description'])>60
        else f"#   [{e['id']}] {e['name']}: {e['description']}"
        for e in errors
    )
    if error_comments:
        error_comments = f"\n# [적용된 오차 수정]\n{error_comments}\n"

    out_dir = RESULTS / paper_id
    results_dir = str(out_dir).replace("\\", "/")

    code = f'''"""
CIS Color Router MEEP 재현 스크립트 (교정 버전)
논문: {paper_t}
생성: {ts}
paper_id: {paper_id}
{error_comments}
[교정 내용 요약]
  stop_decay   = {stop_decay}  (원본값)
  ref_sim_type = {ref_sim_type}
  cover_glass  = {cover_glass}
  source_count = {source_count}
  extra_materials = {extra_mats}
"""
import meep as mp
import meep.adjoint as mpa
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os, json, time
from pathlib import Path

mp.verbosity(1)

# ─── 재료 ────────────────────────────────────────────────────
um_scale = 1
Air   = mp.Medium(index=1.0)
SiO2  = mp.Medium(index=1.45)
SiN   = mp.Medium(index=2.02)   # extra_materials에 포함될 수 있음
{mat}  = mp.Medium(index={n_mat})

# ─── 파라미터 ─────────────────────────────────────────────────
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

design_region_x = round(SP_size * 2, 3)
design_region_y = round(SP_size * 2, 3)
design_region_z = round(layer_num * Layer_thickness + EL_thickness, 3)
Sx = design_region_x
Sy = design_region_y
Sz = round(Lpml+pml_2_src+src_2_geo+design_region_z+FL_thickness+mon_2_pml+Lpml, 3)
cell_size = mp.Vector3(Sx, Sy, Sz)

z_src  = round(Sz/2 - Lpml - pml_2_src, 3)
z_meta = round(Sz/2 - Lpml - pml_2_src - src_2_geo - design_region_z/2, 3)
z_fl   = round(Sz/2 - Lpml - pml_2_src - src_2_geo - design_region_z - FL_thickness/2, 3)
z_sipd = round(Sz/2 - Lpml - pml_2_src - src_2_geo - design_region_z - FL_thickness - mon_2_pml/2 - Lpml/2, 3)
z_mon  = round(-Sz/2 + Lpml + mon_2_pml - 1/resolution, 3)
z_refl = round(Sz/2 - Lpml - 1/resolution, 3)

assert z_src > z_meta, f"소스 위치 오류: z_src={{z_src}} z_meta={{z_meta}}"
assert z_mon > -Sz/2 + Lpml, f"모니터 PML 내부: z_mon={{z_mon}}"

pml_layers = [mp.PML(thickness=Lpml, direction=mp.Z)]

# ─── 소스 ({source_count}개, 교정됨) ─────────────────────────────────
source_center = mp.Vector3(0, 0, z_src)
source_size   = mp.Vector3(Sx, Sy, 0)
frequency = 1/(0.545*um_scale)
fwidth    = frequency * 2
src = mp.GaussianSource(frequency=frequency, fwidth=fwidth)
source = [
{src_lines}
]
wavelengths     = np.array({wls})
frequencies_rgb = 1 / wavelengths

# ─── Geometry ─────────────────────────────────────────────────
geometry = [
{cover_block}
{el_spacer}
    mp.Block(center=mp.Vector3(0,0,z_fl), size=mp.Vector3(Sx,Sy,FL_thickness),
             material={focal_mat_str}),
    mp.Block(center=mp.Vector3(0,0,z_sipd), size=mp.Vector3(Sx,Sy,round(mon_2_pml+Lpml,3)),
             material={sipd_mat}),
]

{design_section}

# ─── Simulation ───────────────────────────────────────────────
sim = mp.Simulation(
    cell_size=cell_size, boundary_layers=pml_layers,
    geometry=geometry, sources=source,
    default_material=Air, resolution=resolution,
    k_point=mp.Vector3(0,0,0),
    eps_averaging=False,
    extra_materials=[{extra_str}],
)
print(f"[Setup] Sz={{Sz}} Nvox={{int(Sx*resolution)**2*int(Sz*resolution):,}} z_meta={{z_meta}} z_mon={{z_mon}}")

# ─── 참조 시뮬 ({ref_sim_type}) ──────────────────────────────
fcen  = (1/0.350 + 1/0.800)/2
df    = 1/0.350 - 1/0.800
nfreq = 400
src_b = mp.GaussianSource(frequency=fcen, fwidth=df)
# [교정] source는 정확히 1개 (참조용)
src_ref = [mp.Source(src_b, component=mp.Ex, size=source_size, center=source_center)]

sim_ref = mp.Simulation(
    cell_size=cell_size, boundary_layers=pml_layers,
    geometry={ref_geo},
    sources=src_ref, default_material=Air, resolution=resolution,
    k_point=mp.Vector3(0,0,0),
    extra_materials=[{extra_str}],
)
refl_fr = mp.FluxRegion(center=mp.Vector3(0,0,z_refl), size=mp.Vector3(Sx,Sy,0))
tran_fr = mp.FluxRegion(center=mp.Vector3(0,0,z_mon),  size=mp.Vector3(Sx,Sy,0))
rr = sim_ref.add_flux(fcen,df,nfreq,refl_fr)
tr = sim_ref.add_flux(fcen,df,nfreq,tran_fr)
print("[Ref Sim] 실행 중...")
t0 = time.time()
sim_ref.run(until_after_sources=mp.stop_when_dft_decayed({stop_decay}, 0))
print(f"[Ref Sim] 완료 ({{time.time()-t0:.1f}}s)")
srd       = sim_ref.get_flux_data(rr)
tot_flux  = mp.get_fluxes(tr)
flux_freq = mp.get_flux_freqs(tr)
wl_arr    = np.array([1/flux_freq[d]*um_scale for d in range(nfreq)])

# ─── 메인 시뮬 ────────────────────────────────────────────────
sim.change_sources(src_ref)
rfl = sim.add_flux(fcen,df,nfreq,refl_fr)
tpx = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(
    center=mp.Vector3(0,0,z_mon), size=mp.Vector3(Sx,Sy,0)))
dx, dy = design_region_x, design_region_y
q = mp.Vector3(dx/2, dy/2, 0)
# bayer_config = {bayer_cfg}
{_bayer_flux_code}
sim.load_minus_flux_data(rfl, srd)

print("[Main Sim] 실행 중...")
t0 = time.time()
sim.run(until_after_sources=mp.stop_when_dft_decayed({stop_decay}, 0))
elapsed = time.time()-t0
print(f"[Main Sim] 완료 ({{elapsed:.1f}}s)")

# ─── 효율 계산 ────────────────────────────────────────────────
tp   = mp.get_fluxes(tpx)
rf   = mp.get_fluxes(tR)
grf  = mp.get_fluxes(tGr)
bf   = mp.get_fluxes(tB)
gbf  = mp.get_fluxes(tGb)

Tr  = np.array([rf[d]/(tp[d]+1e-20)              for d in range(nfreq)])
Tg  = np.array([(grf[d]+gbf[d])/(tp[d]+1e-20)    for d in range(nfreq)])
Tb  = np.array([bf[d]/(tp[d]+1e-20)              for d in range(nfreq)])
Trt = np.array([rf[d]/(tot_flux[d]+1e-20)        for d in range(nfreq)])
Tgt = np.array([(grf[d]+gbf[d])/(tot_flux[d]+1e-20) for d in range(nfreq)])
Tbt = np.array([bf[d]/(tot_flux[d]+1e-20)        for d in range(nfreq)])

def _at(wl_t, T):
    return float(T[np.argmin(np.abs(wl_arr - wl_t))])

out = Path("{results_dir}")
out.mkdir(parents=True, exist_ok=True)

if mp.am_master():
    fig, ax = plt.subplots(figsize=(7,5), dpi=150)
    ax.plot(wl_arr,Tr,'r',label='R'); ax.plot(wl_arr,Tg,'g',label='G'); ax.plot(wl_arr,Tb,'b',label='B')
    ax.plot(wl_arr,Trt,'r--'); ax.plot(wl_arr,Tgt,'g--'); ax.plot(wl_arr,Tbt,'b--')
    ax.fill_between([0.38,0.48],0,1,alpha=0.1,color='blue')
    ax.fill_between([0.48,0.58],0,1,alpha=0.1,color='green')
    ax.fill_between([0.58,0.78],0,1,alpha=0.1,color='red')
    ax.set(xlim=[0.38,0.78],ylim=[0,1.05],xlabel='Wavelength (μm)',ylabel='Efficiency')
    ax.set_title('{paper_t[:50]}')
    ax.legend(fontsize=8); ax.tick_params(direction='in')
    plt.tight_layout()
    plt.savefig(out / "{paper_id}_efficiency.png")
    plt.close()

    result = {{
        "paper_id":"{paper_id}", "paper_title":"{paper_t}",
        "elapsed_sec":elapsed, "resolution":{res}, "stop_decay":"{stop_decay}",
        "ref_sim_type":"{ref_sim_type}", "cover_glass":{cover_glass},
        "efficiency_pixel_norm":{{"R":_at(0.65,Tr),"G":_at(0.55,Tg),"B":_at(0.45,Tb)}},
        "efficiency_total_norm":{{"R":_at(0.65,Trt),"G":_at(0.55,Tgt),"B":_at(0.45,Tbt)}},
    }}
    with open(out / "{paper_id}_results.json","w") as f:
        json.dump(result,f,indent=2,ensure_ascii=False)
    print(f"[Result] R={{result['efficiency_pixel_norm']['R']:.3f}} "
          f"G={{result['efficiency_pixel_norm']['G']:.3f}} "
          f"B={{result['efficiency_pixel_norm']['B']:.3f}}")
    print(f"[Done] {{out}}/")
'''
    return code


# ══════════════════════════════════════════════════════════════
# 실행 + 로깅
# ══════════════════════════════════════════════════════════════

def run_docker(script, pid, res, np_=4, timeout=10800):
    code = script.read_text(encoding="utf-8")
    code = re.sub(r'\bresolution\s*=\s*\d+', f"resolution = {res}", code, count=1)
    rs   = script.parent / f"corrected_{pid}_res{res}.py"
    rs.write_text(code, encoding="utf-8")
    remote = f"/tmp/corr_{pid}_res{res}.py"
    rlog   = f"/tmp/corr_{pid}_res{res}.log"
    subprocess.run(["docker","cp",str(rs),f"{DOCKER}:{remote}"], capture_output=True)
    subprocess.run(["docker","exec",DOCKER,"mkdir","-p",f"/tmp/corr_{pid}_results"],
                   capture_output=True)
    r = subprocess.run(
        ["docker","exec",DOCKER,"bash","-c",
         f"mpirun -np {np_} --allow-run-as-root python {remote} > {rlog} 2>&1 ; "
         f"cp {rlog} /tmp/corr_{pid}_results/"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
    )
    subprocess.run(["docker","cp",f"{DOCKER}:/tmp/corr_{pid}_results/.",
                    str(script.parent)], capture_output=True)
    log_path = script.parent / f"corr_{pid}_res{res}.log"
    return log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""


def parse_result(log_txt):
    m = re.search(r'\[Result\] R=([\d.]+) G=([\d.]+) B=([\d.]+)', log_txt)
    e = re.findall(r'Elapsed run time = ([\d.]+)', log_txt)
    if m:
        return {"R":float(m.group(1)),"G":float(m.group(2)),"B":float(m.group(3))}, float(e[0]) if e else None
    return None, None


def fast_check_docker(script):
    code = script.read_text(encoding="utf-8")
    code_fc = re.sub(r'resolution\s*=\s*\d+','resolution = 5',code,count=1)
    fc = script.parent / f"fc_{script.stem}.py"
    fc.write_text(code_fc, encoding="utf-8")
    subprocess.run(["docker","cp",str(fc),f"{DOCKER}:/tmp/fc_{script.stem}.py"],
                   capture_output=True)
    r = subprocess.run(
        ["docker","exec",DOCKER,"python",f"/tmp/fc_{script.stem}.py"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
    )
    return r.returncode == 0, r.stderr[:200]


# ══════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════

PAPERS = [
    {
        "paper_id": "SMA2023",
        "paper_title": "Pixelated Bayer spectral router (sparse meta-atom, Chinese Optics Letters)",
        "material_name": "SiN", "n_material": 2.02,
        "SP_size": 1.12, "Layer_thickness": 1.0, "FL_thickness": 4.0,
        "EL_thickness": 0, "n_layers": 1, "resolution": 50,
        "focal_material": "SiO2", "design_type": "sparse",
        "sparse_pillars": [
            {"label":"R",  "wx":0.92,"wy":0.92,"cx":-0.56,"cy": 0.56},
            {"label":"G1", "wx":0.16,"wy":0.16,"cx":-0.56,"cy":-0.56},
            {"label":"G2", "wx":0.16,"wy":0.16,"cx": 0.56,"cy": 0.56},
            {"label":"B",  "wx":0.28,"wy":0.28,"cx": 0.56,"cy":-0.56},
        ],
        "target_efficiency": {"R":0.45,"G":0.35,"B":0.40},
        "has_code":False,"has_structure":True,
    },
    {
        "paper_id": "Simplest2023",
        "paper_title": "Simplest GA cylinder router (Nb2O5, Genetic Algorithm)",
        "material_name": "Nb2O5", "n_material": 2.32,
        "SP_size": 0.8, "Layer_thickness": 0.51, "FL_thickness": 1.08,
        "EL_thickness": 0, "n_layers": 1, "resolution": 100,
        "focal_material": "Air", "design_type": "cylinder",
        "cylinders": [
            {"label":"R",  "diameter":0.470,"cx":-0.4,"cy": 0.4},
            {"label":"G1", "diameter":0.370,"cx": 0.4,"cy": 0.4},
            {"label":"G2", "diameter":0.370,"cx":-0.4,"cy":-0.4},
            {"label":"B",  "diameter":0.210,"cx": 0.4,"cy":-0.4},
        ],
        "target_efficiency": {"R":0.60,"G":0.55,"B":0.55},
        "has_code":False,"has_structure":True,
    },
    {
        "paper_id": "RGBIR2025",
        "paper_title": "RGB+IR spectral router (TiO2, ACS Photonics 2025)",
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
        "target_efficiency": {"R":0.50,"G":0.40,"B":0.50},
        "has_code":False,"has_structure":True,
    },
]


def main():
    print("=" * 65)
    print("교정된 CIS 재현 파이프라인 (오차 패턴 DB 적용)")
    print("=" * 65)

    summary = []
    for p in PAPERS:
        pid   = p["paper_id"]
        tgt   = p.get("target_efficiency",{})
        ov    = PAPER_OVERRIDES.get(pid,{}).get("overrides",{})
        errs  = PAPER_OVERRIDES.get(pid,{}).get("confirmed_errors",[])

        print(f"\n{'─'*65}")
        print(f"[{pid}]  ({p['design_type']}, {p['material_name']} n={p['n_material']})")
        print(f"  오차 패턴 수정: {len(errs)}개")
        for e in errs:
            print(f"    [{e['id']}] {e['name']} (impact={e['impact']})")
        print(f"  override: {ov}")

        out = RESULTS / pid
        out.mkdir(parents=True, exist_ok=True)

        # 교정 코드 생성
        code = build_corrected_code(p, pid)

        # detector 사전 검사
        issues = classify_all(code, "", {})
        if issues:
            print(f"  [detector] 탐지: {[r.error_id for r in issues]}")
            code, applied = auto_fix_loop(code)
            print(f"  [detector] 수정: {applied}")

        script = out / f"corrected_{pid}.py"
        script.write_text(code, encoding="utf-8")
        print(f"  [코드] {script.name} ({len(code.splitlines())}줄)")

        # Fast-check
        ok, fc_err = fast_check_docker(script)
        print(f"  [fast-check] {'PASS' if ok else 'FAIL: '+fc_err[:60]}")
        if not ok:
            summary.append({"paper_id":pid,"status":"fast_check_fail"})
            continue

        # res=20 빠른 확인
        print(f"  [res=20] 실행 중...")
        log20 = run_docker(script, pid, res=20, np_=4, timeout=600)
        eff20, t20 = parse_result(log20)
        if eff20:
            print(f"  [res=20] R={eff20['R']:.3f} G={eff20['G']:.3f} B={eff20['B']:.3f}  ({t20:.0f}s)")

        # 최종 resolution
        final_res = p.get("resolution",50)
        print(f"  [res={final_res}] 실행 중...")
        log_f = run_docker(script, pid, res=final_res, np_=4, timeout=10800)
        eff_f, t_f = parse_result(log_f)

        if eff_f and tgt:
            errs_pct = {ch: abs(eff_f[ch]-tgt[ch])/tgt[ch]*100
                        for ch in ["R","G","B"] if ch in tgt}
            avg_err = round(sum(errs_pct.values())/len(errs_pct),1)
            print(f"  [res={final_res}] R={eff_f['R']:.3f} G={eff_f['G']:.3f} B={eff_f['B']:.3f}  "
                  f"({t_f:.0f}s)  avg_err={avg_err}%")
        else:
            avg_err = None
            print(f"  [res={final_res}] 실패")

        row = {
            "paper_id": pid, "title": p["paper_title"],
            "res20": eff20, "final": eff_f,
            "elapsed": t_f, "target": tgt,
            "avg_error_pct": avg_err,
            "overrides_applied": list(ov.keys()),
            "status": "done" if eff_f else "failed",
        }
        (out/f"corrected_{pid}_results.json").write_text(
            json.dumps(row,indent=2,ensure_ascii=False), encoding="utf-8")
        summary.append(row)

    # 전체 요약
    print("\n" + "="*65)
    print("교정 후 결과 vs 교정 전 결과 비교")
    print("="*65)
    prev = {"SMA2023":82,"Simplest2023":89,"RGBIR2025":76}
    print(f"{'논문':<20} {'교정전':>8} {'교정후':>8} {'개선'}")
    print("─"*50)
    for r in summary:
        pid = r["paper_id"]
        new_err = r.get("avg_error_pct","—")
        old_err = prev.get(pid,"—")
        impr = f"{old_err-new_err:.1f}%p 개선" if isinstance(new_err,float) and isinstance(old_err,(int,float)) else "—"
        print(f"  {pid:<18} {str(old_err):>8} {str(new_err):>8}  {impr}")

    (RESULTS/"corrected_summary.json").write_text(
        json.dumps(summary,indent=2,ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
