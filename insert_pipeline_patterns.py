"""
Inverse Design Pipeline Patterns — DB 삽입 스크립트
6대 카테고리 + 역설계 루프 5단계

실행:
  python insert_pipeline_patterns.py                  # 로컬 (db/knowledge.db)
  docker exec <container> python insert_pipeline_patterns.py  # Docker
"""

import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "db", "knowledge.db"))
AUTHOR  = "jin/inverse-design-pipeline"

# ─────────────────────────────────────────────────────────────────────────────
# 패턴 정의: (pattern_name, description, code_snippet, use_case)
#
# 구조 원칙:
#   description = 핵심 개념 + 주의사항 (검색 텍스트 역할)
#   code_snippet = 검증된 실행 가능 코드 (메인 콘텐츠)
#   use_case     = 카테고리 태그 + 키워드 (검색 라우팅용)
# ─────────────────────────────────────────────────────────────────────────────

PATTERNS = [

# ══════════════════════════════════════════════════════════════════════════════
# Category 1: 시뮬레이션 환경 설정
# ══════════════════════════════════════════════════════════════════════════════

(
"pipeline_cat1_basic_environment",
"""[Category 1: 시뮬레이션 환경 설정] SOI 220nm 역설계 기본 환경 파라미터.

주요 주의사항:
- resolution: 최소 50 px/μm (20nm grid). 검증용은 10~20 가능하나 최종 결과는 50 필수.
- PML 두께: 최소 λ/2 = 0.775 μm. 보통 1.0 μm 사용. PML 내부에 geometry가 걸리면 오류.
- cell_size: PML 포함 크기. geometry + 2*dpml + margin으로 계산.
- 재료: n_Si=3.48 (ε=12.11), n_SiO2=1.44 (ε=2.07), air=1.0.
- SiO2 배경은 mp.inf로 PML까지 연장 필수 (mp.inf 없으면 반사 심함).
- fcen: 1/wavelength_um = 1/1.55 ≈ 0.6452.
""",
"""\
import meep as mp
import meep.adjoint as mpa
import numpy as np
import autograd.numpy as npa
from pathlib import Path

# ── 기본 단위: μm ──────────────────────────────────────────────────────────
wavelength = 1.55        # μm (1550 nm)
fcen       = 1.0 / wavelength  # ~0.6452 (MEEP 주파수 단위)
fwidth     = 0.2 * fcen  # 가우시안 소스 대역폭

# ── 재료 ──────────────────────────────────────────────────────────────────
n_Si   = 3.48            # Silicon @ 1550 nm
n_SiO2 = 1.44            # Silica
silicon = mp.Medium(index=n_Si)
oxide   = mp.Medium(index=n_SiO2)

# ── SOI 스택 ──────────────────────────────────────────────────────────────
wg_thick = 0.22          # μm (220 nm Si slab)
sub_thick = 0.5          # μm (SiO2 기판)

# ── PML + Cell ────────────────────────────────────────────────────────────
dpml = 1.0               # μm — PML 두께 (λ/2 = 0.775 이상)
# cell_size는 디자인 영역 크기에 따라 결정 (아래는 예시)
# sxy = design_region_x + 2*wg_length + 2*dpml
# sz  = wg_thick + sub_thick + dpml + air_gap (3D)

boundary_layers = [mp.PML(thickness=dpml)]

# ── 해상도 ────────────────────────────────────────────────────────────────
resolution = 50          # px/μm (최종 최적화용)
# resolution = 10        # 빠른 검증용 (구조 확인만)

# ── SiO2 배경 (PML까지 연장 필수) ─────────────────────────────────────────
# 2D 예시: SiO2 배경을 cell 전체에 깔기
# geometry_bg = [mp.Block(size=mp.Vector3(mp.inf, mp.inf, mp.inf),
#                         material=oxide)]
# 주의: mp.inf 없으면 SiO2가 cell 경계에서 잘려 반사 발생
""",
"pipeline_category:env_setup | 시뮬레이션 환경 설정 | resolution PML cell_size SOI 재료 설정 | inverse design 시작 전 환경"
),

(
"pipeline_cat1_2d_vs_3d_setup",
"""[Category 1: 시뮬레이션 환경 설정] 2D vs 3D 시뮬레이션 설정 차이.

주요 주의사항:
- 2D: cell_size z=0. 빠르지만 z-leakage 고려 안 됨. 초기 topology opt에 적합.
- 3D: cell_size z=wg_thick+sub_thick+dpml+cladding. 느리지만 실제 물리와 일치.
- 3D 소스 크기: source_size_z=wg_thick+sub_thick+2.0 (기판 포함 충분히).
- MPI: 3D는 -np 10 이상 권장. 2D는 -np 4~8.
- eig_parity: 2D는 mp.ODD_Z+mp.EVEN_Y (TE), 3D는 mp.ODD_Z.
""",
"""\
# ── 2D 설정 ───────────────────────────────────────────────────────────────
wg_width   = 0.5         # μm
design_len = 3.0         # μm (디자인 영역 길이)
design_wid = 2.0         # μm (디자인 영역 폭)

# 2D Cell
sxy_x = design_len + 4.0 + 2 * dpml   # 디자인 + 입출력 도파로 + PML
sxy_y = design_wid + 2.0 + 2 * dpml   # 디자인 + 여유 + PML
cell_2d = mp.Vector3(sxy_x, sxy_y, 0)

# eig_parity for 2D TE
parity_2d = mp.ODD_Z + mp.EVEN_Y

# ── 3D 설정 ───────────────────────────────────────────────────────────────
# 기판 포함 z 크기
air_gap = 1.0
sz = wg_thick + sub_thick + dpml + air_gap   # ≈ 2.72 μm
cell_3d = mp.Vector3(sxy_x, sxy_y, sz)

# 3D SiO2 기판 (z 아래쪽)
# z_center_sub = -wg_thick/2 - sub_thick/2  (Si slab 아래)
z_center_sub = -(wg_thick / 2 + sub_thick / 2)
substrate_3d = mp.Block(
    size=mp.Vector3(mp.inf, mp.inf, sub_thick),
    center=mp.Vector3(0, 0, z_center_sub),
    material=oxide
)

# eig_parity for 3D TE
parity_3d = mp.ODD_Z   # TE mode
""",
"pipeline_category:env_setup | 2D 3D 설정 차이 | cell_size z-leakage eig_parity MPI | 2D vs 3D 선택"
),

# ══════════════════════════════════════════════════════════════════════════════
# Category 2: 지오메트리 구성 + 레이아웃 플롯
# ══════════════════════════════════════════════════════════════════════════════

(
"pipeline_cat2_geometry_layout",
"""[Category 2: 지오메트리 구성] 입출력 도파로 + 레이아웃 플롯.

주요 주의사항:
- geometry 목록 순서: 배경 Block 먼저, 디자인 영역 Block 마지막 (덮어쓰기 순서).
- 입출력 도파로는 mp.Block으로 정의, center/size를 정확히 계산.
- 레이아웃 플롯은 sim.run() 전에 sim.init_sim() 후 plot2D() 사용.
- mp.am_master() 없이 저장하면 MPI에서 중복 저장 오류.
- plot2D는 z=0 단면만 보임. 3D에서 Si slab 단면 확인용.
""",
"""\
import matplotlib
matplotlib.use("Agg")   # 헤드리스 서버용 (GUI 없을 때 필수)
import matplotlib.pyplot as plt

# ── 입출력 도파로 기본 geometry ────────────────────────────────────────────
wg_width   = 0.5         # μm 입력 도파로 폭
wg_length  = 2.0         # μm 입출력 도파로 길이 (디자인 영역 양쪽)
design_len = 3.0         # μm 디자인 영역 길이
design_wid = 2.0         # μm 디자인 영역 폭

# 입력 도파로 (왼쪽)
wg_in = mp.Block(
    size=mp.Vector3(wg_length, wg_width, mp.inf),
    center=mp.Vector3(-(design_len / 2 + wg_length / 2), 0, 0),
    material=silicon
)
# 출력 도파로 (오른쪽)
wg_out = mp.Block(
    size=mp.Vector3(wg_length, wg_width, mp.inf),
    center=mp.Vector3(design_len / 2 + wg_length / 2, 0, 0),
    material=silicon
)

geometry = [wg_in, wg_out]
# 주의: 디자인 영역 Block은 Cat.3에서 추가

# ── 레이아웃 플롯 (시뮬레이션 실행 전 구조 확인) ─────────────────────────
sim_for_plot = mp.Simulation(
    resolution=resolution,
    cell_size=cell_2d,
    boundary_layers=boundary_layers,
    geometry=geometry,
    default_material=oxide,    # 배경 재료
    sources=[]
)
sim_for_plot.init_sim()

if mp.am_master():
    output_dir = Path("./output")
    output_dir.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    sim_for_plot.plot2D(ax=ax)
    ax.set_title("Initial Layout — Check before running simulation")
    plt.savefig(output_dir / "initial_layout.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("[Layout] Saved: output/initial_layout.png")

sim_for_plot.reset_meep()
""",
"pipeline_category:geometry | geometry 구성 레이아웃 플롯 | mp.Block mp.Cylinder plot2D init_sim | 구조 시각화 확인"
),

# ══════════════════════════════════════════════════════════════════════════════
# Category 3: 디자인 영역 설정
# ══════════════════════════════════════════════════════════════════════════════

(
"pipeline_cat3_design_region",
"""[Category 3: 디자인 영역 설정] MaterialGrid + DesignRegion 정의.

주요 주의사항:
- MaterialGrid Nx/Ny: design_region_size * resolution과 일치시킬 것.
  Nx = int(design_len * resolution), Ny = int(design_wid * resolution).
- grid_type='U_MEAN': 유전율 선형 보간. 역설계 표준.
- do_averaging=True (기본값): 서브픽셀 평균화. False로 끄면 수렴 불안정.
- 초기값 x0: 0.5 (균일)이 표준. 랜덤 초기화는 수렴이 느릴 수 있음.
- DesignRegion의 volume과 Simulation의 geometry Block 크기/위치를 반드시 일치.
""",
"""\
# ── 디자인 영역 크기 ──────────────────────────────────────────────────────
design_region_size   = mp.Vector3(design_len, design_wid)
design_region_center = mp.Vector3(0, 0, 0)

# ── MaterialGrid 해상도 (시뮬레이션 resolution과 맞춤) ─────────────────────
Nx = int(round(design_len * resolution))   # e.g. 3.0 * 50 = 150
Ny = int(round(design_wid * resolution))   # e.g. 2.0 * 50 = 100
print(f"[DesignRegion] Nx={Nx}, Ny={Ny}, total params={Nx*Ny}")

# ── MaterialGrid 정의 ─────────────────────────────────────────────────────
design_variables = mp.MaterialGrid(
    mp.Vector3(Nx, Ny),
    mp.air,          # u=0 -> air (ε=1)
    silicon,         # u=1 -> Si (ε=12.11)
    grid_type="U_MEAN",
    do_averaging=True,   # 서브픽셀 평균화 (수렴 안정성 향상)
)

# ── DesignRegion 등록 ─────────────────────────────────────────────────────
design_region = mpa.DesignRegion(
    design_variables,
    volume=mp.Volume(
        center=design_region_center,
        size=design_region_size,
    ),
)

# ── Geometry에 디자인 영역 Block 추가 (geometry 리스트에 append) ───────────
design_block = mp.Block(
    center=design_region_center,
    size=design_region_size,
    material=design_variables,
)
geometry.append(design_block)   # geometry = [wg_in, wg_out, design_block]

# ── 초기값 ────────────────────────────────────────────────────────────────
x0 = np.full(Nx * Ny, 0.5)   # 균일 초기화 (표준)
# x0 = np.random.rand(Nx * Ny) * 0.1 + 0.45  # 약한 랜덤 노이즈 버전
""",
"pipeline_category:design_region | MaterialGrid DesignRegion 디자인 영역 | Nx Ny grid_type U_MEAN do_averaging | 역설계 변수 설정"
),

# ══════════════════════════════════════════════════════════════════════════════
# Category 4: 시뮬레이션 설정 (Sources / Monitors / PML)
# ══════════════════════════════════════════════════════════════════════════════

(
"pipeline_cat4_sources_monitors",
"""[Category 4: 시뮬레이션 설정] EigenModeSource + EigenmodeCoefficient 모니터.

주요 주의사항:
- eig_band: 반드시 1부터 시작. 0은 MEEP에서 유효하지 않아 효율 >100% 오류.
- 소스 위치: 디자인 영역 왼쪽 경계에서 0.5~1.0 μm 떨어진 곳.
- 소스/모니터 크기: 도파로보다 충분히 크게 (모드 에너지가 밖으로 새지 않도록).
- forward=True (기본): 포워드 진행 방향. 반사 모니터는 forward=False.
- EigenmodeCoefficient는 mpa.EigenmodeCoefficient (meep.adjoint 모듈에 있음).
- 여러 모드 동시 모니터링: mode=1,2,3 각각 별도 EigenmodeCoefficient 생성.
""",
"""\
# ── 소스/모니터 x 위치 ────────────────────────────────────────────────────
src_x = -(design_len / 2 + wg_length * 0.7)  # 디자인 영역 왼쪽 바깥
mon_x =   design_len / 2 + wg_length * 0.7   # 디자인 영역 오른쪽 바깥

# ── 소스 크기 (도파로 폭보다 충분히 크게) ────────────────────────────────
src_size_y = wg_width * 3.0    # 2D: y 방향만
# src_size_z = wg_thick + sub_thick + 1.0  # 3D: z 방향 포함

# ── EigenModeSource ────────────────────────────────────────────────────────
sources = [
    mp.EigenModeSource(
        src=mp.GaussianSource(frequency=fcen, fwidth=fwidth),
        center=mp.Vector3(src_x, 0, 0),
        size=mp.Vector3(0, src_size_y, 0),   # 2D: z=0
        eig_band=1,          # ⚠️ 반드시 1부터 (0 금지!)
        eig_parity=parity_2d,
        eig_match_freq=True,
    )
]

# ── Simulation 객체 ────────────────────────────────────────────────────────
sim = mp.Simulation(
    resolution=resolution,
    cell_size=cell_2d,
    boundary_layers=boundary_layers,
    geometry=geometry,
    sources=sources,
    default_material=oxide,
)

# ── EigenmodeCoefficient 모니터 (mpa 모듈) ─────────────────────────────────
# TE0 투과 모니터 (기본)
te0_monitor = mpa.EigenmodeCoefficient(
    sim,
    mp.Volume(center=mp.Vector3(mon_x, 0, 0),
              size=mp.Vector3(0, src_size_y, 0)),
    mode=1,          # ⚠️ eig_band와 마찬가지로 1부터
    forward=True,    # 포워드 방향 전파
    eig_parity=parity_2d,
)

# (선택) TE1 모니터 — mode demux 등에서 사용
te1_monitor = mpa.EigenmodeCoefficient(
    sim,
    mp.Volume(center=mp.Vector3(mon_x, 0, 0),
              size=mp.Vector3(0, src_size_y, 0)),
    mode=2,
    forward=True,
    eig_parity=parity_2d,
)
""",
"pipeline_category:sim_setup | EigenModeSource EigenmodeCoefficient sources monitors | eig_band eig_parity forward | 소스 모니터 설정"
),

# ══════════════════════════════════════════════════════════════════════════════
# Category 5 / Stage 5-1: Forward Simulation + DFT 필드 플롯
# ══════════════════════════════════════════════════════════════════════════════

(
"pipeline_stage51_forward_simulation",
"""[Stage 5-1: Forward Simulation] OptimizationProblem 생성 + Forward 실행 + DFT 필드 플롯.

주요 주의사항:
- opt([x0]) 호출 시 forward + adjoint 모두 실행됨. fom, grad 동시 반환.
- npa (autograd.numpy) 사용 필수. np.abs 대신 npa.abs 써야 gradient 계산됨.
- objective_functions 인수: list of callables, 각 함수는 모니터 계수 -> scalar.
- DFT 필드 추출: sim.run() 후 sim.get_array()로 eps, Ez 등 추출.
- sim.get_array()는 opt([x0]) 후에 sim이 마지막 forward 상태를 유지하므로 바로 사용 가능.
- MPI: 필드 저장은 반드시 mp.am_master() 블록 안에서.
""",
"""\
# ── Objective function (autograd.numpy 필수!) ─────────────────────────────
def J_te0(te0_coeff):
    # TE0 투과율 최대화
    return npa.abs(te0_coeff[0, 0, 0]) ** 2   # shape: (freq, mode, direction)

# ── OptimizationProblem 생성 ──────────────────────────────────────────────
opt = mpa.OptimizationProblem(
    simulation=sim,
    objective_functions=[J_te0],
    objective_arguments=[te0_monitor],
    design_regions=[design_region],
    fcen=fcen,
    df=0,
    nf=1,
)

# ── Forward + Adjoint 동시 실행 ───────────────────────────────────────────
x0 = np.full(Nx * Ny, 0.5)
fom, grad = opt([x0])
# fom:  [float] — objective value (투과율)
# grad: [ndarray shape (Nx*Ny,)] — dJ/dε 각 설계변수

if mp.am_master():
    print(f"[Stage 5-1] FOM = {fom[0]:.6f}")

# ── DFT 필드 플롯 (Forward 완료 후) ──────────────────────────────────────
if mp.am_master():
    output_dir = Path("./output")
    output_dir.mkdir(exist_ok=True)

    # Epsilon 분포
    eps_data = sim.get_array(
        center=mp.Vector3(), size=cell_2d, component=mp.Dielectric
    )
    # Ez 필드 (TE 모드)
    ez_data = sim.get_array(
        center=mp.Vector3(), size=cell_2d, component=mp.Ez
    )

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].imshow(
        eps_data.T, cmap="binary", origin="lower",
        extent=[-cell_2d.x/2, cell_2d.x/2, -cell_2d.y/2, cell_2d.y/2]
    )
    axes[0].set_title("Epsilon Distribution (Forward)")
    axes[0].set_xlabel("x (μm)"); axes[0].set_ylabel("y (μm)")

    axes[1].imshow(
        np.abs(ez_data).T, cmap="hot", origin="lower",
        extent=[-cell_2d.x/2, cell_2d.x/2, -cell_2d.y/2, cell_2d.y/2]
    )
    axes[1].set_title("|Ez| Forward Field")
    axes[1].set_xlabel("x (μm)")

    plt.tight_layout()
    plt.savefig(output_dir / "forward_field.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("[Stage 5-1] Saved: output/forward_field.png")

mp.all_wait()
""",
"pipeline_category:inv_loop pipeline_stage:forward_sim | OptimizationProblem forward simulation DFT field plot | npa autograd Ez eps | 포워드 시뮬레이션 필드 플롯"
),

# ══════════════════════════════════════════════════════════════════════════════
# Category 5 / Stage 5-2: Adjoint Simulation + Adjoint DFT 필드 플롯
# ══════════════════════════════════════════════════════════════════════════════

(
"pipeline_stage52_adjoint_simulation",
"""[Stage 5-2: Adjoint Simulation] Adjoint field 시각화 + MPI-safe 저장.

주요 주의사항:
- MEEP adjoint solver는 adjoint field를 내부적으로 계산하며 직접 접근 API 없음.
  대신 opt([x0]) 내부에서 자동 실행되며 grad로 결과가 나옴.
- Adjoint field 시각화를 원하면 opt.forward_run() / opt.adjoint_run() 분리 호출 가능
  (단, 이 API는 meep.adjoint 내부용이므로 버전에 따라 다를 수 있음).
- 실용적 접근: opt.sim의 DFT field array를 opt([x0]) 직후 get_array()로 추출.
- mp.am_master() 없이 저장 시 MPI 프로세스 수만큼 파일이 중복 저장되어 오류.
- 모든 파일 I/O, matplotlib 호출은 mp.am_master() 블록 내부에서만.
""",
"""\
# ── opt([x0]) 실행 (forward + adjoint 동시) ───────────────────────────────
# Stage 5-1에서 이미 실행했다면 아래는 생략 가능
# fom, grad = opt([x0])

# ── Adjoint 관련 DFT 필드 추출 ────────────────────────────────────────────
# MEEP는 adjoint field 자체를 직접 노출하지 않음.
# opt([x0]) 완료 후 sim의 상태는 마지막 forward run 상태.
# adjoint field와 관련된 분석은 gradient map (Stage 5-3)으로 수행.

# 그러나 forward/adjoint 필드를 모두 저장하고 싶다면:
# opt.forward_run() 직후 forward field 저장
# opt.adjoint_run() 직후 adjoint field 저장

# ── 실용적 Adjoint 시각화 (DFT array) ────────────────────────────────────
if mp.am_master():
    output_dir = Path("./output")
    output_dir.mkdir(exist_ok=True)

    # opt.sim 내부 DFT field 객체에서 추출
    # (meep.adjoint 버전에 따라 API 변동 가능 — 검증 필요)
    try:
        # forward DFT Ex, Ey, Ez 추출
        ex_fwd = opt.sim.get_array(
            center=mp.Vector3(), size=cell_2d, component=mp.Ex
        )
        ez_fwd = opt.sim.get_array(
            center=mp.Vector3(), size=cell_2d, component=mp.Ez
        )

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        axes[0].imshow(
            np.abs(ex_fwd).T, cmap="RdBu_r", origin="lower"
        )
        axes[0].set_title("|Ex| DFT (Forward)")
        axes[1].imshow(
            np.abs(ez_fwd).T, cmap="hot", origin="lower"
        )
        axes[1].set_title("|Ez| DFT (Forward -> Adjoint 확인용)")

        plt.tight_layout()
        plt.savefig(output_dir / "adjoint_dft_field.png", dpi=150, bbox_inches="tight")
        plt.close()
        print("[Stage 5-2] Saved: output/adjoint_dft_field.png")

    except Exception as e:
        print(f"[Stage 5-2] DFT field 추출 실패: {e} — gradient map으로 대체")

mp.all_wait()
""",
"pipeline_category:inv_loop pipeline_stage:adjoint_sim | adjoint simulation DFT field 어드조인트 필드 플롯 MPI | mp.am_master get_array | 어드조인트 시뮬레이션 시각화"
),

# ══════════════════════════════════════════════════════════════════════════════
# Category 5 / Stage 5-3: Gradient 계산 + Gradient Map 플롯
# ══════════════════════════════════════════════════════════════════════════════

(
"pipeline_stage53_gradient_map",
"""[Stage 5-3: Gradient 계산] Gradient map 플롯 + 수렴 로깅.

주요 주의사항:
- grad shape: (Nx*Ny,) — reshape(Nx, Ny)로 2D 맵 변환.
- gradient 부호: FOM 최대화 방향으로 업데이트. scipy.optimize는 최소화이므로
  FOM에 -1 곱해서 전달하거나 gradient에 -1 곱해야 함.
- gradient 크기가 너무 작으면 (< 1e-10): 소스/모니터 위치 또는 eig_band 오류 의심.
- gradient 크기가 NaN/Inf: beta 값이 너무 크거나, 설계변수가 0 또는 1 경계에 있음.
- gradient_map 플롯에서 빨강=양(Si로 바꾸면 좋음), 파랑=음(air로 바꾸면 좋음).
- 수렴 히스토리 저장: 매 iteration마다 fom_history, grad_norm_history 기록.
""",
"""\
# ── opt([x0]) 실행 결과 ───────────────────────────────────────────────────
fom, grad = opt([x0])
# grad: list, grad[0]이 첫 번째 design_region의 gradient

grad_arr = grad[0]   # shape: (Nx*Ny,)
grad_2d  = grad_arr.reshape(Nx, Ny)

if mp.am_master():
    print(f"[Stage 5-3] FOM={fom[0]:.6f}  |grad|={np.linalg.norm(grad_arr):.4e}")
    print(f"            grad max={grad_arr.max():.4e}  min={grad_arr.min():.4e}")

    # gradient NaN/Inf 체크
    if np.any(np.isnan(grad_arr)) or np.any(np.isinf(grad_arr)):
        print("[Stage 5-3] ⚠️ gradient에 NaN/Inf 감지! beta 낮추거나 x0 점검")

    output_dir = Path("./output")
    output_dir.mkdir(exist_ok=True)

    # Gradient Map 플롯
    fig, ax = plt.subplots(figsize=(8, 6))
    vmax = np.abs(grad_2d).max()
    im = ax.imshow(
        grad_2d.T, cmap="RdBu_r", origin="lower",
        vmin=-vmax, vmax=vmax,
        extent=[-design_len/2, design_len/2, -design_wid/2, design_wid/2]
    )
    plt.colorbar(im, ax=ax, label="dJ/dε (Gradient)")
    ax.set_title("Adjoint Gradient Map — Red: Add Si, Blue: Remove Si")
    ax.set_xlabel("x (μm)"); ax.set_ylabel("y (μm)")
    plt.tight_layout()
    plt.savefig(output_dir / "gradient_map.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("[Stage 5-3] Saved: output/gradient_map.png")

mp.all_wait()

# ── 수렴 히스토리 기록 ────────────────────────────────────────────────────
# iteration 루프 안에서 사용
fom_history      = []
grad_norm_history = []

def record_history(fom_val, grad_val):
    if mp.am_master():
        fom_history.append(float(fom_val))
        grad_norm_history.append(float(np.linalg.norm(grad_val)))
""",
"pipeline_category:inv_loop pipeline_stage:gradient | gradient map 그래디언트 맵 sensitivity | reshape NaN Inf 수렴 히스토리 | 그래디언트 시각화"
),

# ══════════════════════════════════════════════════════════════════════════════
# Category 5 / Stage 5-4: Beta Scheduling
# ══════════════════════════════════════════════════════════════════════════════

(
"pipeline_stage54_beta_scheduling",
"""[Stage 5-4: Beta Scheduling] Tanh projection + beta continuation 스케줄.

주요 주의사항:
- beta: 이진화 강도. 낮을수록 부드러운 구조, 높을수록 0/1 이진 구조.
- 너무 빠르게 올리면 FOM이 발산하거나 local minimum에 빠짐.
  표준: 10 iteration마다 2배씩 증가 (2->4->8->16->32->64->128).
- eta: threshold (0.5 = 대칭). 비대칭 구조는 0.45~0.55 조정.
- beta 변경 전후에 x0를 re-project해야 연속성 유지.
- update_design_function: opt에 등록한 후 매 iteration 자동 호출.
- beta_max 도달 후에도 FOM이 90% 미만이면 구조 재검토.
""",
"""\
from meep.adjoint import utils as mpa_utils

# ── Tanh projection 함수 ──────────────────────────────────────────────────
def tanh_projection(x, beta, eta=0.5):
    # Heaviside tanh projection for binarization
    return (npa.tanh(beta * eta) + npa.tanh(beta * (x - eta))) / \
           (npa.tanh(beta * eta) + npa.tanh(beta * (1 - eta)))

# ── Beta schedule ─────────────────────────────────────────────────────────
beta_start  = 2.0
beta_max    = 128.0
beta_update_freq = 10   # 매 N iteration마다 beta 2배

def get_beta(iteration):
    # iteration -> beta 값 반환
    doublings = iteration // beta_update_freq
    beta = beta_start * (2 ** doublings)
    return min(beta, beta_max)

# ── 최적화 루프 내 beta 적용 예시 ─────────────────────────────────────────
n_iter = 100
x      = x0.copy()

for i in range(n_iter):
    beta = get_beta(i)

    # Projected design variable (beta projection 적용 후)
    x_projected = tanh_projection(x, beta, eta=0.5)

    # opt에 현재 beta를 반영하여 실행
    # (opt의 design_region에 projection 함수를 등록한 경우)
    fom, grad = opt([x_projected])

    # gradient도 projection chain rule 적용
    # grad_projected = grad * d(tanh_proj)/dx
    chain = beta * (1 - npa.tanh(beta * (x - 0.5)) ** 2) / \
            (npa.tanh(beta * 0.5) + npa.tanh(beta * 0.5))
    grad_effective = grad[0] * chain

    if mp.am_master():
        print(f"[Stage 5-4] iter={i:03d}  beta={beta:.1f}  FOM={fom[0]:.6f}")

    # gradient descent step (scipy optimizer 사용 시 optimizer.tell(x, -fom, -grad) 형태)
    x = np.clip(x + 0.01 * grad_effective, 0, 1)   # 단순 gradient ascent 예시

mp.all_wait()
""",
"pipeline_category:inv_loop pipeline_stage:beta_scheduling | beta scheduling tanh projection 베타 스케줄링 이진화 | continuation eta binarization | beta 스케줄"
),

# ══════════════════════════════════════════════════════════════════════════════
# Category 5 / Stage 5-5: Filter (Binarization + Fabrication Constraint)
# ══════════════════════════════════════════════════════════════════════════════

(
"pipeline_stage55_filter",
"""[Stage 5-5: Filter] Conic filter + fabrication constraint 적용.

주요 주의사항:
- Conic filter: minimum length scale 보장. r=minimum_feature/2 (단위: design grid 픽셀).
  예: minimum feature 100 nm, design grid 20 nm -> r = 100/20/2 = 2.5 픽셀.
- Gaussian filter: 더 부드럽지만 length scale 보장 약함. sigma=r/3 사용.
- 필터 순서: conic_filter -> tanh_projection (반드시 이 순서).
- Filter 적용 후 x를 다시 opt에 넣을 때 x_filtered를 사용 (x 원본 아님).
- meep.adjoint.utils의 conic_filter는 2D reshape 입력을 받음.
- 최종 구조 binary 비율: (x > 0.5).mean() >= 0.9이면 잘 수렴된 것.
""",
"""\
from meep.adjoint import utils as mpa_utils

# ── Conic Filter 설정 ─────────────────────────────────────────────────────
# minimum feature size: 100 nm = 0.1 μm
min_feature_um = 0.1
design_grid_um = 1.0 / resolution    # 1/50 = 0.02 μm/pixel
r_pixels = min_feature_um / design_grid_um / 2   # ≈ 2.5 pixels

def apply_conic_filter(x, Nx, Ny, r):
    # Conic filter for minimum length scale (meep.adjoint.utils 사용)
    x_2d = x.reshape(Nx, Ny)
    x_filtered_2d = mpa_utils.conic_filter(
        x_2d,
        radius=r,
        Lx=design_len,   # μm
        Ly=design_wid,   # μm
        resolution=resolution,
    )
    return x_filtered_2d.flatten()

def apply_gaussian_filter(x, Nx, Ny, sigma):
    # Gaussian filter (대안)
    from scipy.ndimage import gaussian_filter
    x_2d = x.reshape(Nx, Ny)
    x_filtered_2d = gaussian_filter(x_2d, sigma=sigma)
    return np.clip(x_filtered_2d.flatten(), 0, 1)

# ── Filter + Projection 파이프라인 ────────────────────────────────────────
def forward_pass(x, beta, eta=0.5):
    # Filter -> Projection 순서 적용 후 opt에 전달
    # Step 1: Conic filter (fabrication constraint)
    x_filt = apply_conic_filter(x, Nx, Ny, r_pixels)
    # Step 2: Tanh projection (binarization)
    x_proj = tanh_projection(x_filt, beta, eta)
    return x_proj

# ── 최종 구조 binary 비율 확인 ────────────────────────────────────────────
def check_binary_ratio(x_final, threshold=0.5):
    ratio = np.mean((x_final > threshold) | (x_final < 1 - threshold))
    if mp.am_master():
        binary_ratio = np.mean(np.abs(x_final - 0.5) > 0.4)
        print(f"[Stage 5-5] Binary ratio: {binary_ratio:.1%}  (≥90% = good)")
        if binary_ratio < 0.9:
            print("            ⚠️ 구조가 아직 회색 영역 많음 — beta 더 높이거나 iteration 추가")
    return ratio

# ── 최종 구조 플롯 ────────────────────────────────────────────────────────
def plot_final_structure(x_final, output_dir, iteration):
    if mp.am_master():
        x_2d = x_final.reshape(Nx, Ny)
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.imshow(
            x_2d.T, cmap="binary", origin="lower", vmin=0, vmax=1,
            extent=[-design_len/2, design_len/2, -design_wid/2, design_wid/2]
        )
        ax.set_title(f"Final Structure (iter={iteration})")
        ax.set_xlabel("x (μm)"); ax.set_ylabel("y (μm)")
        plt.tight_layout()
        path = Path(output_dir) / f"design_iter{iteration:03d}.png"
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"[Stage 5-5] Saved: {path}")
""",
"pipeline_category:inv_loop pipeline_stage:filter | conic filter gaussian filter fabrication constraint 필터 이진화 | minimum length scale binary ratio | 제조 제약 필터"
),

# ══════════════════════════════════════════════════════════════════════════════
# Category 6: 결과물 출력
# ══════════════════════════════════════════════════════════════════════════════

(
"pipeline_cat6_output_results",
"""[Category 6: 결과물 출력] 수렴 플롯 + 결과 저장 + 최종 검증 시뮬레이션.

주요 주의사항:
- 모든 저장 코드는 mp.am_master() 블록 안에서만 실행.
- history.json: 매 iteration FOM, grad_norm, beta를 저장. 세션 복구에 필수.
- 수렴 플롯: FOM vs iteration + beta 스케줄 overlay.
- 최종 검증: 최적화 resolution(50)보다 높은 resolution(100~200)으로 재확인.
- field_propagation.mp4: sim.run() 중 mp.output_efield_z로 프레임 저장 후 ffmpeg 변환.
- results.txt: 최종 FOM, binary ratio, 사용 시간, resolution 등 summary.
""",
"""\
import json
import time

# ── 수렴 히스토리 저장 ────────────────────────────────────────────────────
def save_history(fom_history, grad_norm_history, beta_history, output_dir):
    if mp.am_master():
        history = {
            "fom":       fom_history,
            "grad_norm": grad_norm_history,
            "beta":      beta_history,
            "n_iter":    len(fom_history),
            "best_fom":  max(fom_history) if fom_history else 0,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(Path(output_dir) / "history.json", "w") as f:
            json.dump(history, f, indent=2)
        print(f"[Cat.6] Saved: {output_dir}/history.json")

# ── 수렴 플롯 ─────────────────────────────────────────────────────────────
def plot_convergence(fom_history, beta_history, output_dir):
    if mp.am_master():
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

        ax1.plot(fom_history, "b-o", markersize=3, label="FOM")
        ax1.set_ylabel("FOM (Transmission)")
        ax1.set_ylim(0, 1.05)
        ax1.legend(); ax1.grid(True, alpha=0.3)
        ax1.set_title("Convergence")

        ax2.semilogy(beta_history, "r-s", markersize=3, label="Beta")
        ax2.set_ylabel("Beta (log scale)")
        ax2.set_xlabel("Iteration")
        ax2.legend(); ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(Path(output_dir) / "convergence.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"[Cat.6] Saved: {output_dir}/convergence.png")

# ── results.txt summary ───────────────────────────────────────────────────
def save_results_summary(fom_history, x_final, output_dir, resolution, n_iter):
    if mp.am_master():
        binary_ratio = np.mean(np.abs(x_final - 0.5) > 0.4)
        lines = [
            "=== Inverse Design Results Summary ===",
            f"Final FOM:     {fom_history[-1]:.6f}",
            f"Best FOM:      {max(fom_history):.6f}",
            f"Binary ratio:  {binary_ratio:.1%}",
            f"Iterations:    {n_iter}",
            f"Resolution:    {resolution} px/μm",
            f"Design params: {len(x_final)} ({Nx}×{Ny})",
            f"Timestamp:     {time.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        with open(Path(output_dir) / "results.txt", "w") as f:
            f.write("\n".join(lines))
        print("[Cat.6] Saved: results.txt")
        for l in lines: print(f"  {l}")

# ── 최종 검증 시뮬레이션 (높은 resolution으로) ───────────────────────────
# resolution_verify = 100  # 최적화의 2배
# sim_verify = mp.Simulation(resolution=resolution_verify, ...)
# -> 최종 x_final을 적용한 구조로 transmission 재측정
""",
"pipeline_category:output | 결과물 출력 수렴 플롯 convergence history.json results.txt | mp.am_master 최종 검증 | 역설계 결과 저장"
),

]  # END PATTERNS


# ─────────────────────────────────────────────────────────────────────────────
# DB 삽입
# ─────────────────────────────────────────────────────────────────────────────
def insert_patterns():
    print(f"DB: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    inserted = 0
    skipped  = 0
    for pattern_name, description, code_snippet, use_case in PATTERNS:
        # 중복 체크
        exists = conn.execute(
            "SELECT id FROM patterns WHERE pattern_name = ?", (pattern_name,)
        ).fetchone()
        if exists:
            print(f"  [SKIP] {pattern_name} (already exists, id={exists[0]})")
            skipped += 1
            continue

        conn.execute(
            "INSERT INTO patterns (pattern_name, description, code_snippet, use_case, author_repo) "
            "VALUES (?, ?, ?, ?, ?)",
            (pattern_name, description, code_snippet, use_case, AUTHOR)
        )
        print(f"  [INSERT] {pattern_name}")
        inserted += 1

    conn.commit()
    conn.close()
    print(f"\nDone: {inserted} inserted, {skipped} skipped.")
    return inserted


def rebuild_chroma():
    # ChromaDB patterns 컬렉션 재구축
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer

        CHROMA_DIR = os.path.join(os.path.dirname(__file__), "db", "chroma")
        MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

        print("\n[ChromaDB] Loading embedding model...")
        model  = SentenceTransformer(MODEL_NAME)
        client = chromadb.PersistentClient(path=CHROMA_DIR)

        # 기존 컬렉션 삭제 후 재생성
        try:
            client.delete_collection("patterns")
            print("[ChromaDB] Deleted old patterns collection")
        except Exception:
            pass

        col = client.create_collection("patterns", metadata={"hnsw:space": "cosine"})

        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT id, pattern_name, description, code_snippet, use_case FROM patterns"
        ).fetchall()
        conn.close()
        print(f"[ChromaDB] Found {len(rows)} patterns")

        texts, ids, metas = [], [], []
        for pid, name, desc, code, use_case in rows:
            search_text = f"{name} {desc or ''} {use_case or ''}".strip()
            texts.append(search_text)
            ids.append(f"pattern_{pid}")
            metas.append({"id": pid, "name": name})

        print("[ChromaDB] Generating embeddings...")
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=True).tolist()

        BATCH = 50
        for i in range(0, len(texts), BATCH):
            col.add(
                ids=ids[i:i+BATCH],
                embeddings=embeddings[i:i+BATCH],
                documents=texts[i:i+BATCH],
                metadatas=metas[i:i+BATCH],
            )
        print(f"[ChromaDB] Done. patterns collection: {col.count()} entries")

        # 검색 테스트
        print("\n[ChromaDB] Search test: 'adjoint field DFT plot'")
        test_emb = model.encode(["adjoint field DFT plot 어드조인트 필드 플롯"]).tolist()
        res = col.query(query_embeddings=test_emb, n_results=5,
                        include=["distances", "metadatas"])
        for i, (did, dist, meta) in enumerate(zip(
            res["ids"][0], res["distances"][0], res["metadatas"][0]
        )):
            print(f"  [{i+1}] {meta['name']} | score={1-dist:.3f}")

    except ImportError as e:
        print(f"[ChromaDB] Skipped (missing package: {e}). Run rebuild_patterns_index.py in Docker.")


if __name__ == "__main__":
    inserted = insert_patterns()
    if inserted > 0:
        rebuild_chroma()
    else:
        print("\nNo new patterns inserted. ChromaDB rebuild skipped.")
        print("Use --force flag or delete existing patterns to re-insert.")
