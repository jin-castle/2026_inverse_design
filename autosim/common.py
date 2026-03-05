"""
autosim/common.py — 모든 패턴이 공유하는 표준 setup
"""
import sys, os, json, time as _time
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any, Union, NamedTuple
from collections import namedtuple

# ── typing 별칭 / stub 타입 정의 (패턴 코드에서 사용) ────────────────────
BacktrackingResult = namedtuple('BacktrackingResult', ['success', 'alpha', 'count', 'message'], defaults=[None])

# ── MEEP & 수치 라이브러리 ──────────────────────────────────────────────────
import meep as mp
import meep.adjoint as mpa
import numpy as np
try:
    import autograd.numpy as npa
except ImportError:
    npa = np

# ── matplotlib 헤드리스 ────────────────────────────────────────────────────
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── 표준 재료 (SOI 220nm 플랫폼) ──────────────────────────────────────────
n_Si    = 3.48
n_SiO2  = 1.44
silicon = mp.Medium(index=n_Si)
oxide   = mp.Medium(index=n_SiO2)
air     = mp.Medium(index=1.0)
# 별칭
SILICON = silicon
OXIDE   = oxide
Si      = silicon
SiO2    = oxide

# ── 표준 파라미터 ─────────────────────────────────────────────────────────
wavelength  = 1.55          # μm
fcen        = 1.0 / wavelength
fwidth      = 0.2 * fcen
resolution  = 20            # px/μm (검증용 저해상도)
dpml        = 1.0           # μm PML 두께
wg_width    = 0.5           # μm 입력 도파로 폭
slab_h      = 0.22          # μm Si slab 두께
design_len  = 3.0           # μm 디자인 영역 길이
design_wid  = 2.0           # μm 디자인 영역 폭
Nx          = int(design_len * resolution)
Ny          = int(design_wid * resolution)

# ── numpy 별칭 (일부 패턴에서 사용) ──────────────────────────────────────
import numpy.linalg as LA        # solve_cw_steady_state 등

# ── 셀 크기 기본값 (패턴별로 오버라이드 가능) ───────────────────────────────
cell_x      = 10.0          # μm
cell_y      = 6.0           # μm
cell_z      = 0             # 2D 시뮬레이션 기본

# ── 소스/모니터 위치 기본값 ────────────────────────────────────────────────
source_x    = -(cell_x / 2) + dpml + 0.5   # μm
source_y    = 0.0
monitor_x   = (cell_x / 2) - dpml - 0.1   # μm

# ── 설계 해상도 (adjoint filter 등) ──────────────────────────────────────
DESIGN_RESOLUTION = resolution

# ── 도파로 길이 기본값 ─────────────────────────────────────────────────────
L           = design_len    # μm (EigenModeSource_parameters 등)
R_me        = 0.0           # 모드 반사율 기본값 (mode_coeff_phase 등)

# ── 추가 크기/위치 변수 (자주 쓰이는 코드 단편 지원) ────────────────────────
Sx          = cell_x        # 셀 X 크기 별칭
Sy          = cell_y        # 셀 Y 크기 별칭 (EigenModeSource_parameters 등)
Sz          = slab_h + 2*dpml  # 3D 셀 Z 크기

input_x     = source_x     # 입력 측 x 위치 별칭
output_x    = monitor_x    # 출력 측 x 위치 별칭
input_monitor_x  = source_x + 0.5
output_monitor_x = monitor_x - 0.5

z_center    = slab_h / 2   # Si slab 중심 z 위치
FREQUENCY   = fcen          # 주파수 별칭

monitor_size_y  = cell_y - 2*dpml
monitor_size_z  = slab_h + 1.0

# ── 추가 파라미터 (sio2_substrate_pml_geometry, EigenModeSource_parameters 등) ──
df              = fwidth        # GaussianSource fwidth 별칭
nfreq           = 1             # 주파수 포인트 수 기본값
input_length    = design_len / 2
output_length   = design_len / 2
output_width    = wg_width
input_width     = 12.0          # 넓은 입력 도파로 (mctp 타입)
cell_size       = mp.Vector3(cell_x, cell_y, 0)

# ── 최소 sim 객체 (단편 코드 실행을 위한 placeholder) ───────────────────────
_default_sim_cell    = mp.Vector3(cell_x, cell_y, 0)
_default_sim_sources = [mp.EigenModeSource(
    src=mp.GaussianSource(fcen, fwidth=fwidth),
    center=mp.Vector3(source_x, 0, 0),
    size=mp.Vector3(0, Sy, 0),
    eig_band=1,
)]
_default_sim_geo     = [mp.Block(
    size=mp.Vector3(mp.inf, wg_width, mp.inf),
    center=mp.Vector3(0, 0, 0),
    material=silicon,
)]
sim = mp.Simulation(
    cell_size=_default_sim_cell,
    geometry=_default_sim_geo,
    sources=_default_sim_sources,
    boundary_layers=[mp.PML(dpml)],
    resolution=resolution,
)

# ── Pipeline 패턴용 변수 (cat1~cat4 standalone 실행을 위한 기본값) ────────
wg_thick    = slab_h        # Si waveguide 두께 (= slab_h = 0.22 μm)
sub_thick   = 2.0           # SiO2 substrate 두께 (μm)
air_gap     = 1.0           # Air cladding gap (μm)
wg_length   = 1.0           # 입출력 도파로 길이 (μm)

# 2D cell
_sxy_x      = design_len + 4.0 + 2 * dpml
_sxy_y      = design_wid + 2.0 + 2 * dpml
cell_2d     = mp.Vector3(_sxy_x, _sxy_y, 0)

# 3D cell
_sz         = wg_thick + sub_thick + dpml + air_gap
cell_3d     = mp.Vector3(_sxy_x, _sxy_y, _sz)

# parity
parity_2d   = mp.ODD_Z + mp.EVEN_Y
parity_3d   = mp.ODD_Z

# source / monitor 위치
src_x       = -(design_len / 2 + wg_length * 0.7)
mon_x       = design_len / 2 + wg_length * 0.7

# boundary
boundary_layers = [mp.PML(dpml)]

# geometry placeholder (빈 리스트 → 패턴 코드에서 채움)
geometry    = []

# 3D substrate
z_center_sub = -(wg_thick / 2 + sub_thick / 2)
substrate_3d = mp.Block(
    size=mp.Vector3(mp.inf, mp.inf, sub_thick),
    center=mp.Vector3(0, 0, z_center_sub),
    material=oxide,
)

# ── 경로 ─────────────────────────────────────────────────────────────────
AUTOSIM_DIR = Path("/root/autosim")
RESULT_DIR  = AUTOSIM_DIR / "results"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

# ── 결과 저장 유틸 ────────────────────────────────────────────────────────
def save_result(pattern_name: str, outputs=None, error=None, elapsed: float = 0.0):
    d = RESULT_DIR / pattern_name
    d.mkdir(exist_ok=True)
    data = {
        "pattern":   pattern_name,
        "status":    "error" if error else "ok",
        "elapsed_s": round(elapsed, 2),
        "outputs":   outputs or [],
        "error":     str(error) if error else None,
    }
    (d / "result.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data

def savefig_safe(pattern_name: str, filename: str = "output.png", dpi: int = 100):
    """현재 matplotlib figure를 results/{pattern_name}/{filename}에 저장"""
    if not plt.get_fignums():
        return None
    out = RESULT_DIR / pattern_name / filename
    out.parent.mkdir(exist_ok=True)
    plt.savefig(str(out), dpi=dpi, bbox_inches="tight")
    plt.close("all")
    return str(out)
