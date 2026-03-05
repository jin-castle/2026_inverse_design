"""PROJ-002 MCTP patterns insert script."""
import sqlite3

DB_PATH = '/app/db/knowledge.db'
AUTHOR  = 'jin/proj-002-mctp'

PATTERNS = [
(
"mctp_core_parameters",
"Core parameters for PROJ-002 MCTP: TE0 to TE1 mode conversion with 12um to 1um "
"width taper on SOI 220nm platform. Input: 12um multimode waveguide (TE0). "
"Output: 1um few-mode waveguide (TE1 first-order mode). "
"Design region: height 13um fixed, length 5-10um sweep. Resolution 50 (20nm grid). "
"SiO2 substrate 500nm. neff_TE0_input=2.847, neff_TE1_output=2.156. "
"MCTP core parameters: 12um-1um taper, TE0-TE1 mode conversion, SOI 220nm.",
"""\
# ============================================================
# PROJ-002 MCTP Core Parameters
# TE0->TE1 Mode Conversion + 12um->1um Width Taper
# Platform: SOI 220nm
# ============================================================

wavelength = 1.55        # um (1550 nm telecom)
frequency  = 1 / wavelength  # ~0.6452 (1/um)

# Materials
n_Si   = 3.48            # Silicon @ 1550 nm
n_SiO2 = 1.44            # Silica substrate @ 1550 nm
eps_Si   = n_Si   ** 2   # ~12.11
eps_SiO2 = n_SiO2 ** 2   # ~2.07

# SOI stack
wg_height           = 0.22  # um (220 nm Si slab)
substrate_thickness = 0.50  # um (500 nm SiO2 substrate)

# Waveguide widths
input_width  = 12.0      # um -> multimode (many TE modes)
output_width = 1.0       # um -> few-mode (TE0 + TE1 guided)

# Mode assignment
# input_mode  = "TE0"  -> eig_band=1 in 12um waveguide
# output_mode = "TE1"  -> mode=2 in 1um waveguide

# Design region (2D top-view)
design_region_height  = 13.0   # um (FIXED = input_width + 1um margin)
design_region_lengths = [5.0, 6.0, 7.0, 8.0, 9.0, 10.0]  # um sweep
design_resolution     = 50     # pixels/um -> 20 nm pixel

# Simulation
dpml       = 1.0    # um PML thickness (min lambda/2 = 0.775 um)
resolution = 50     # pixels/um (2D opt); use 30 for 3D

# Source / Monitor sizes (2D)
source_size_y  = input_width  + 4.0  # 16 um (generous - covers full mode)
monitor_size_y = output_width + 2.0  # 3  um (generous)

# Source / Monitor sizes (3D -- must include SiO2 substrate)
source_z_size  = wg_height + substrate_thickness + 2.0  # 2.72 um
monitor_z_size = source_z_size  # same as source

# MPB-calculated effective indices
neff_input_TE0  = 2.847  # 12um waveguide TE0 @ 1550nm
neff_output_TE1 = 2.156  # 1um  waveguide TE1 @ 1550nm
""",
"MCTP parameters, mode converter taper parameters, TE0 TE1 mode converter, "
"12um to 1um taper, SOI 220nm mode converter, PROJ-002 parameters, "
"input_width 12um output_width 1um, design region 13um, "
"MCTP 파라미터, 모드 변환기 설계 파라미터, 12um 1um 테이퍼"
),

(
"sio2_substrate_pml_geometry",
"CRITICAL: SiO2 substrate geometry must extend to PML using mp.inf in x-direction. "
"If SiO2 ends before PML, a SiO2/air interface forms inside PML causing reflections. "
"Wrong: size=mp.Vector3(cell_x - 2*dpml, thickness, mp.inf). "
"Correct: size=mp.Vector3(mp.inf, thickness, mp.inf). "
"Set default_material=SiO2 so background is SiO2 not air. "
"SiO2 substrate must extend to mp.inf through PML - reflection prevention!",
"""\
import meep as mp

eps_Si   = 3.48 ** 2   # 12.11
eps_SiO2 = 1.44 ** 2   # 2.07
substrate_thickness = 0.5   # um
wg_height           = 0.22  # um
input_width         = 12.0  # um

# WRONG: SiO2 stops before PML -> reflection at SiO2/air interface!
geometry_wrong = [
    mp.Block(
        center=mp.Vector3(0, -substrate_thickness/2, 0),
        size=mp.Vector3(cell_x - 2*dpml, substrate_thickness, mp.inf),  # BAD
        material=mp.Medium(epsilon=eps_SiO2)
    ),
]

# CORRECT: SiO2 extends through PML in x-direction
geometry = [
    # SiO2 substrate -- use mp.inf to pass through PML
    mp.Block(
        center=mp.Vector3(0, -substrate_thickness/2, 0),
        size=mp.Vector3(mp.inf, substrate_thickness, mp.inf),  # mp.inf!
        material=mp.Medium(epsilon=eps_SiO2)
    ),
    # Si input waveguide
    mp.Block(
        center=mp.Vector3(input_x, 0, 0),
        size=mp.Vector3(input_length, input_width, mp.inf),
        material=mp.Medium(epsilon=eps_Si)
    ),
    # Si output waveguide
    mp.Block(
        center=mp.Vector3(output_x, 0, 0),
        size=mp.Vector3(output_length, output_width, mp.inf),
        material=mp.Medium(epsilon=eps_Si)
    ),
]

# Set background to SiO2 (not air!)
sim = mp.Simulation(
    cell_size=cell_size,
    boundary_layers=[mp.PML(dpml)],
    geometry=geometry,
    default_material=mp.Medium(epsilon=eps_SiO2),  # SiO2 background
    resolution=resolution,
)
""",
"SiO2 substrate PML geometry, SiO2 extend to PML mp.inf, "
"reflection at SiO2 air interface fix, substrate geometry MEEP, "
"SiO2 background material MEEP, waveguide substrate setup SOI, "
"mp.inf substrate block, PML reflection fix SiO2, "
"SiO2 기판 PML 연장, SiO2 mp.inf 설정, 기판 반사 방지"
),

(
"source_monitor_size_substrate",
"Source and Monitor must include the full waveguide cross-section including SiO2 substrate. "
"Too-small source/monitor clips the mode causing mode mismatch or efficiency > 100% errors. "
"2D rule: source_y = waveguide_width + 4um, monitor_y = out_width + 2um. "
"3D rule: z_size = Si_height + SiO2_thickness + 2um = 0.22 + 0.5 + 2 = 2.72um. "
"EigenModeSource and EigenmodeCoefficient both need generous sizes. "
"Source Monitor size rules: include substrate in 3D, generous margin in 2D.",
"""\
import meep as mp
import meep.adjoint as mpa

input_width  = 12.0   # um
output_width = 1.0    # um
wg_height    = 0.22   # um
substrate_t  = 0.50   # um
frequency    = 1/1.55

# 2D sizes
source_size_y_2d  = input_width  + 4.0   # 16 um (generous!)
monitor_size_y_2d = output_width + 2.0   # 3  um (generous!)

# 3D sizes: include SiO2 substrate in z-direction
z_size   = wg_height + substrate_t + 2.0       # 2.72 um
z_center = (wg_height - substrate_t) / 2       # midpoint Si+SiO2

# 2D EigenModeSource (TE0 input, 12um waveguide)
sources_2d = [
    mp.EigenModeSource(
        src=mp.GaussianSource(frequency, fwidth=0.1*frequency),
        center=mp.Vector3(source_x, 0, 0),
        size=mp.Vector3(0, source_size_y_2d, 0),   # 16um generous
        direction=mp.X,
        eig_band=1,               # TE0 fundamental (1-indexed)
        eig_parity=mp.ODD_Y,      # TE mode in 2D
        eig_match_freq=True,
    )
]

# 2D EigenmodeCoefficient (TE1 output monitor)
obj_2d = mpa.EigenmodeCoefficient(
    sim,
    mp.Volume(
        center=mp.Vector3(monitor_x, 0, 0),
        size=mp.Vector3(0, monitor_size_y_2d, 0),  # 3um generous
    ),
    mode=2,               # TE1 first-order (1-indexed)
    eig_parity=mp.ODD_Y,
    forward=True,
)

# 3D EigenModeSource (includes SiO2 substrate in z)
sources_3d = [
    mp.EigenModeSource(
        src=mp.GaussianSource(frequency, fwidth=0.1*frequency),
        center=mp.Vector3(source_x, 0, z_center),
        size=mp.Vector3(0, input_width + 4.0, z_size),  # includes SiO2!
        direction=mp.X,
        eig_band=1,
        eig_parity=mp.ODD_Z + mp.EVEN_Y,  # TE in 3D SOI
        eig_match_freq=True,
    )
]
""",
"source monitor size MEEP, eigenmode source size substrate, "
"source size waveguide include substrate 3D, monitor size TE1 output, "
"efficiency 100 percent fix source size, eigenmode source 12um multimode, "
"source size substrate SiO2 include, mode mismatch source too small, "
"source monitor 크기 규칙, 기판 포함 source, 3D source substrate, 효율 100% 오류"
),

(
"eig_parity_2d_vs_3d",
"eig_parity rules for TE/TM mode selection in 2D vs 3D MEEP. "
"2D (xy plane, z=infinite): TE has Ey,Hx,Hz components -> eig_parity=mp.ODD_Y. "
"TM has Hy,Ex,Ez -> eig_parity=mp.EVEN_Y. "
"3D SOI slab: quasi-TE (Ey dominant) -> eig_parity=mp.ODD_Z + mp.EVEN_Y. "
"quasi-TM (Ez dominant) -> eig_parity=mp.EVEN_Z + mp.ODD_Y. "
"Common mistake: using EVEN_Y in 2D (selects TM not TE!). "
"eig_parity 2D vs 3D: ODD_Y for 2D TE, ODD_Z+EVEN_Y for 3D SOI TE.",
"""\
import meep as mp
import meep.adjoint as mpa

# eig_parity RULES:
# 2D (x-y plane, z infinite):
#   TE mode (Ey, Hx, Hz components) -> ODD_Y
#   TM mode (Hy, Ex, Ez components) -> EVEN_Y
eig_parity_2d_TE = mp.ODD_Y    # TE in 2D (most waveguide problems)
eig_parity_2d_TM = mp.EVEN_Y   # TM in 2D

# 3D SOI slab (z = slab thickness direction):
#   quasi-TE: Ey dominant -> ODD_Z + EVEN_Y
#   quasi-TM: Ez dominant -> EVEN_Z + ODD_Y
eig_parity_3d_TE = mp.ODD_Z + mp.EVEN_Y   # quasi-TE in 3D SOI
eig_parity_3d_TM = mp.EVEN_Z + mp.ODD_Y   # quasi-TM in 3D SOI

frequency = 1/1.55

# 2D TE0 source (input, 12um waveguide):
source_2d_TE0 = mp.EigenModeSource(
    src=mp.GaussianSource(frequency, fwidth=0.1*frequency),
    center=mp.Vector3(source_x, 0, 0),
    size=mp.Vector3(0, 16.0, 0),
    eig_band=1,              # TE0: band 1 (1-indexed!)
    eig_parity=mp.ODD_Y,     # TE in 2D
)

# 3D TE0 source:
source_3d_TE0 = mp.EigenModeSource(
    src=mp.GaussianSource(frequency, fwidth=0.1*frequency),
    center=mp.Vector3(source_x, 0, 0.11),   # z = slab center
    size=mp.Vector3(0, 16.0, 2.72),
    eig_band=1,
    eig_parity=mp.ODD_Z + mp.EVEN_Y,        # quasi-TE in 3D SOI
)

# 2D TE1 monitor (output, 1um waveguide):
obj_2d = mpa.EigenmodeCoefficient(
    sim,
    mp.Volume(center=mp.Vector3(monitor_x, 0, 0),
              size=mp.Vector3(0, 3.0, 0)),
    mode=2,              # TE1: mode 2 (1-indexed!)
    eig_parity=mp.ODD_Y,
    forward=True,
)

# COMMON MISTAKES:
# eig_band=0          -> WRONG: MEEP is 1-indexed (TE0 = band 1)
# eig_parity=EVEN_Y   -> WRONG in 2D: selects TM mode not TE!
# no eig_parity in 3D -> WRONG: ambiguous, may pick wrong mode family
""",
"eig_parity 2D 3D MEEP, ODD_Y TE mode 2D, ODD_Z EVEN_Y TE mode 3D SOI, "
"eig_parity TE TM selection, quasi-TE SOI slab parity, "
"EigenModeSource parity 2D 3D, eig_parity MEEP, "
"eig_parity ODD_Y 설정, 2D TE 모드 parity, 3D SOI TE parity 설정"
),

(
"adam_optimizer_topology_opt",
"Adam optimizer for MEEP adjoint topology optimization with gradient ASCENT (maximize FOM). "
"Key difference from standard Adam: uses + update (maximize, not minimize). "
"Includes moment reset method - call reset() when changing beta (important!). "
"Clips design variables to [0, 1]. "
"Learning rate guide: grayscale 0.01-0.05, low-beta 0.01-0.02, high-beta 0.001-0.005. "
"Adam optimizer: gradient ascent for FOM maximization, moment reset on beta change.",
"""\
import numpy as np

class AdamOptimizer:
    # Adam optimizer for topology optimization.
    # Uses gradient ASCENT (+ update) to MAXIMIZE FOM.
    # Call reset() when changing beta to avoid stale moments.
    def __init__(self, learning_rate=0.01, beta1=0.9, beta2=0.999, epsilon=1e-8):
        self.lr      = learning_rate
        self.beta1   = beta1
        self.beta2   = beta2
        self.epsilon = epsilon
        self.m = None   # First moment
        self.v = None   # Second moment
        self.t = 0      # Time step

    def update(self, params: np.ndarray, grads: np.ndarray) -> np.ndarray:
        # Gradient ASCENT update - params in [0,1], grads from mpa.OptimizationProblem
        if self.m is None:
            self.m = np.zeros_like(params)
            self.v = np.zeros_like(params)
        self.t += 1

        self.m = self.beta1 * self.m + (1 - self.beta1) * grads
        self.v = self.beta2 * self.v + (1 - self.beta2) * (grads ** 2)
        m_hat  = self.m / (1 - self.beta1 ** self.t)
        v_hat  = self.v / (1 - self.beta2 ** self.t)

        # ASCENT: + not - (maximize FOM)
        params_new = params + self.lr * m_hat / (np.sqrt(v_hat) + self.epsilon)
        return np.clip(params_new, 0.0, 1.0)

    def reset(self):
        # Reset moments - call when changing beta!
        self.m = None
        self.v = None
        self.t = 0


# Learning rate guide:
# Grayscale (beta=0):  lr = 0.01 ~ 0.05
# Low beta (1-8):      lr = 0.01 ~ 0.02
# High beta (16-64):   lr = 0.005 ~ 0.01
# Very high (128+):    lr = 0.001 ~ 0.005
# -> Reduce lr as beta increases for stability

# Usage in optimization loop:
# optimizer = AdamOptimizer(learning_rate=0.01)
# design = np.random.uniform(0.4, 0.6, n_pixels)
# for i in range(n_iter):
#     fom, grad = opt([design])
#     design = optimizer.update(design, grad[0])
# # When increasing beta:
# # optimizer.reset()  <- IMPORTANT
""",
"Adam optimizer adjoint MEEP, topology optimization Adam, gradient ascent MEEP, "
"Adam optimizer maximize FOM, moment reset beta change adjoint, "
"clip design variables 0 1 Adam, AdamOptimizer class MEEP adjoint, "
"adjoint Adam update maximize, learning rate guide beta, "
"Adam optimizer 역설계, gradient ascent 최대화, beta 변경 reset"
),

(
"verify_eigenmode_coupling",
"Verify eigenmode source coupling using sim.get_eigenmode(). "
"Computes neff = k.x / frequency for each band to confirm correct mode selection. "
"Essential for multimode waveguides (12um has many TE modes). "
"Call after sim.init_sim() but before sim.run(). "
"Expected: 12um waveguide band1=TE0 neff~2.847, band2=TE1 neff~2.71. "
"1um waveguide band2=TE1 neff~1.98 (verify not cutoff). "
"verify eigenmode coupling: get_eigenmode neff check before optimization.",
"""\
import meep as mp

def verify_eigenmode_coupling(sim, source_x: float, source_size: mp.Vector3,
                               frequency: float, num_bands: int = 5,
                               parity=mp.ODD_Y):
    # Check eigenmode neff at source position.
    # Call after sim.init_sim() to verify band numbers before running.
    print(f"Eigenmode verification at x={source_x:.2f}")
    print(f"Source size y={source_size.y:.2f} um")
    print("-" * 40)

    for band in range(1, num_bands + 1):
        try:
            em = sim.get_eigenmode(
                frequency,
                mp.X,
                mp.Volume(
                    center=mp.Vector3(source_x, 0, 0),
                    size=source_size
                ),
                band_num=band,
                parity=parity,
            )
            neff = em.k.x / frequency
            print(f"  Band {band}: neff = {neff:.4f}")
        except Exception as e:
            print(f"  Band {band}: cutoff ({e})")

# Expected for 12um SOI waveguide @ 1550nm:
# Band 1: neff ~ 2.847  <- TE0 (eig_band=1 for source)
# Band 2: neff ~ 2.710  <- TE1
# Band 3: neff ~ 2.561  <- TE2
# ... many modes in 12um multimode waveguide

# Expected for 1um output waveguide:
# Band 1: neff ~ 2.45   <- TE0
# Band 2: neff ~ 1.98   <- TE1  (our target, check > 1.44 = not cutoff)
""",
"verify eigenmode coupling MEEP, get_eigenmode MEEP, eigenmode neff verification, "
"multimode waveguide mode check, band number check MEEP, "
"check mode before optimization, eigenmode effective index neff, "
"TE0 TE1 verification 12um waveguide, mode not cutoff check, "
"eigenmode 검증, neff 확인, 멀티모드 모드 선택 검증"
),

(
"optimization_5stage_workflow",
"5-stage inverse design workflow for SOI photonic devices. "
"Stage 1: MPB mode analysis - verify TE1 not cutoff in 1um, get neff. "
"Stage 2: 2D grayscale (beta=0) - theoretical efficiency upper bound, ~87% expected. "
"Stage 3: 2D projection (beta increasing) - binarization to > 0.95. "
"Stage 4: 2D MFS conic filter (50nm or 100nm) - fabrication constraints. "
"Stage 5: 3D verification - final check, expect ~10-20% FOM drop vs 2D. "
"5-stage inverse design: MPB, 2D gray, projection, MFS, 3D verification.",
"""\
# ============================================================
# 5-Stage Inverse Design Workflow (SOI Photonics)
# ============================================================

# STAGE 1: MPB Mode Analysis (~5 min)
# Purpose: Verify TE1 guided in 1um output; get neff for 2.5D
# Key checks:
#   1um waveguide TE1: neff > 1.44? (must be guided)
#   12um waveguide: how many TE modes? (many - source needs to be selective)
# Output: neff_TE0=2.847 (input 12um), neff_TE1=2.156 (output 1um)

# STAGE 2: 2D Grayscale (beta=0, ~30min-2hr at resolution=50)
# Purpose: Find theoretical efficiency upper bound
# - Continuous design vars rho in [0,1], no binarization pressure
# - Optimizer: Adam lr=0.02, 100 iterations
# - Target FOM > 0.85 (if < 0.7, design_length may be too short -> increase)
# - No filter or projection in this stage

# STAGE 3: 2D Projection Optimization
# Purpose: Binarize grayscale result
# - Start from Stage 2 design, apply tanh_projection with increasing beta
beta_schedule = [1, 2, 4, 8, 16, 32, 64, 128, 256]
# - At each beta: run ~20-50 iter until convergence
# - IMPORTANT: call optimizer.reset() when changing beta!
# - Reduce lr as beta increases: beta<16 lr=0.01, beta>16 lr=0.005
# - Target: binarization metric > 0.95

# STAGE 4: 2D MFS Application (Minimum Feature Size)
# Purpose: Enforce fabrication constraints
# - Apply conic filter: radius = MFS / (2 * pixel_size)
#   MFS 50nm:  filter_radius = 0.025 um  (pixel = 1/50 = 0.02 um)
#   MFS 100nm: filter_radius = 0.050 um
# - Expect FOM drop ~5-15% after MFS enforcement (acceptable)

# STAGE 5: 3D Verification (2-10 hr, SimServer -np 128 recommended)
# Purpose: Confirm 2D result holds in full 3D SOI simulation
# - Use Stage 4 final design extruded through 220nm Si slab
# - resolution=30 (lower than 2D due to compute)
# - Expect FOM drop ~10-20% vs 2D (3D z-leakage effects)
# - Key outputs: TE1 transmission, TE0 crosstalk, field animation (Ey)

# DESIGN LENGTH SWEEP (run Stages 2-4 for each):
import os
for length in [5.0, 6.0, 7.0, 8.0, 9.0, 10.0]:  # um
    result_dir = f"results/length_{length:.0f}um"
    os.makedirs(result_dir, exist_ok=True)
    # run_optimization(design_length=length, output_dir=result_dir)

# Select shortest length with FOM > 0.90, then run Stage 5 for that one only
""",
"inverse design workflow 5 stages, MPB mode analysis first step, "
"2D grayscale optimization beta 0, projection optimization beta schedule, "
"MFS conic filter fabrication constraint, 3D verification SOI, "
"design length sweep 5 to 10um, optimization pipeline MEEP adjoint, "
"역설계 5단계 워크플로우, MPB 분석, 이진화, MFS, 3D 검증"
),

(
"design_length_sweep",
"Sweep over design region lengths (5-10um) to find minimum length achieving "
"target FOM. Design height fixed at 13um (= input_width 12um + 1um margin). "
"Run full optimization (Stages 2-4) for each length, compare final FOMs. "
"Select shortest length with FOM > 0.90 to minimize device footprint. "
"Plot FOM vs length comparison. "
"Design length sweep: 5-10um, minimize footprint, FOM > 0.90 target.",
"""\
import os
import json
import numpy as np
import matplotlib.pyplot as plt

# Design region: height FIXED, length SWEPT
design_region_height  = 13.0   # um (fixed = input_width + 1)
design_region_lengths = [5.0, 6.0, 7.0, 8.0, 9.0, 10.0]  # um

sweep_results = {}

for design_length in design_region_lengths:
    print(f"Running length={design_length:.0f}um")
    result_dir = f"results/length_{design_length:.0f}um"
    os.makedirs(result_dir, exist_ok=True)

    # final_fom, final_bin = run_optimization(design_length, result_dir)
    # sweep_results[design_length] = {"fom": final_fom, "binarization": final_bin}


def plot_sweep_comparison(sweep_results: dict, output_path: str) -> float:
    # Plot FOM vs design length and return optimal length.
    lengths = sorted(sweep_results.keys())
    foms    = [sweep_results[l]["fom"] for l in lengths]
    bins    = [sweep_results[l]["binarization"] for l in lengths]

    fig, ax1 = plt.subplots(figsize=(10, 6))
    color1 = 'tab:blue'
    ax1.set_xlabel('Design Length (um)')
    ax1.set_ylabel('Final FOM (TE1 Transmission)', color=color1)
    ax1.plot(lengths, foms, 'o-', color=color1, linewidth=2, markersize=8)
    ax1.axhline(y=0.90, color='green', linestyle='--', alpha=0.7,
                label='Target FOM = 0.90')
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.set_ylim([0, 1])

    ax2 = ax1.twinx()
    color2 = 'tab:red'
    ax2.set_ylabel('Binarization', color=color2)
    ax2.plot(lengths, bins, 's--', color=color2, linewidth=1.5, markersize=6)
    ax2.tick_params(axis='y', labelcolor=color2)
    ax2.set_ylim([0, 1])

    ax1.legend(loc='lower right')
    plt.title('Design Length Sweep: FOM vs Length')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

    # Select shortest length achieving target
    optimal = next((l for l in lengths if sweep_results[l]["fom"] > 0.90), lengths[-1])
    print(f"Optimal: {optimal:.0f} um (FOM={sweep_results[optimal]['fom']:.3f})")
    return optimal
""",
"design length sweep MEEP adjoint, sweep design region length, "
"minimum footprint optimization, design length 5 to 10um, "
"compare FOM vs length plot, optimal design length selection, "
"mode converter length sweep, design length comparison, "
"설계 길이 스윕, footprint 최소화, 최적 길이 선택"
),

]  # end PATTERNS


def insert_patterns():
    conn = sqlite3.connect(DB_PATH)
    existing = {r[0] for r in conn.execute("SELECT pattern_name FROM patterns").fetchall()}
    inserted = 0
    skipped  = 0
    for name, desc, code, use_case in PATTERNS:
        if name in existing:
            print(f"[SKIP]   {name}")
            skipped += 1
            continue
        conn.execute(
            "INSERT INTO patterns (pattern_name, description, code_snippet, use_case, author_repo) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, desc, code, use_case, AUTHOR)
        )
        print(f"[INSERT] {name}")
        inserted += 1
    conn.commit()
    conn.close()
    print(f"\nInserted: {inserted}  Skipped: {skipped}  New total: ~{108 + inserted}")

if __name__ == "__main__":
    insert_patterns()
