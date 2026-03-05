"""
Output Format Guide → Pattern DB 삽입 스크립트
출처: Jin's Inverse Design Output Format Guide (jin/output_format_guide)
모든 코드는 실제 PROJ-001/002에서 실행 검증된 코드
"""
import sqlite3

DB_PATH = '/app/db/knowledge.db'
AUTHOR  = 'jin/output_format_guide'

PATTERNS = [

# ─── 1. Initial Layout ───────────────────────────────────────────────────────
(
"plot_initial_layout",
"""Plot initial simulation layout: waveguide geometry with source (red dashed), \
output monitor (blue dashed), and design region (green dashed rectangle) annotations. \
Uses sim.plot2D() as base, overlays axvline markers and patches.Rectangle for design region. \
Essential first step to verify source/monitor/design positions before running optimization. \
초기 레이아웃 시각화: source/monitor/design region 위치 검증용.""",
"""\
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path

def plot_initial_layout(sim, layout: dict, output_dir: Path,
                        DESIGN_HEIGHT: float = 3.0):
    \"\"\"Save initial layout with source/monitor/design region annotations.\"\"\"
    fig, ax = plt.subplots(figsize=(12, 6))
    sim.plot2D(ax=ax)

    # Source position (red dashed vertical line)
    ax.axvline(x=layout["source_x"], color='red', linestyle='--',
               linewidth=2, label='Source')

    # Output monitor position (blue dashed)
    ax.axvline(x=layout["output_monitor_x"], color='blue', linestyle='--',
               linewidth=2, label='Output Monitor')

    # Design region rectangle (green dashed)
    rect = patches.Rectangle(
        (layout["design_start"], -DESIGN_HEIGHT / 2),
        layout["design_length"], DESIGN_HEIGHT,
        fill=False, edgecolor='green', linewidth=3,
        linestyle='--', label='Design Region'
    )
    ax.add_patch(rect)

    ax.legend(loc='upper right')
    ax.set_title(f'Initial Layout (L={layout["design_length"]:.1f} µm)')
    ax.set_xlabel('x (µm)')
    ax.set_ylabel('y (µm)')
    plt.tight_layout()
    plt.savefig(output_dir / 'initial_layout.png', dpi=150, bbox_inches='tight')
    plt.close()
""",
"plot initial layout MEEP, initial_layout.png, sim.plot2D annotation, "
"source monitor design region visualization, layout verification, "
"axvline source MEEP, patches Rectangle design region, "
"initial layout adjoint, 초기 레이아웃, source monitor 위치 확인, design region 시각화"
),

# ─── 2. Save Density Plot ────────────────────────────────────────────────────
(
"save_density_plot",
"""Save design density plot for adjoint optimization iterations. \
Reshapes flat design vector to 2D, plots with gray_r colormap (0=white/SiO2, 1=black/Si). \
Annotates FOM and binarization metric in title. Used for design_iter{N:03d}.png files \
to track optimization progress. Colormap convention: gray_r so Si (high density) appears dark. \
설계 밀도 플롯: gray_r 컬러맵 (0=SiO2/흰색, 1=Si/검정), FOM/binarization 표시.""",
"""\
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Optional

def save_density_plot(flat: np.ndarray, nx: int, ny: int,
                      design_length: float, out_path: Path, title: str,
                      DESIGN_HEIGHT: float = 3.0,
                      fom: Optional[float] = None,
                      binarization: Optional[float] = None) -> None:
    \"\"\"Save design density plot with FOM/binarization annotation.
    
    Colormap: gray_r → 0=white(SiO2), 1=black(Si)
    \"\"\"
    density = flat.reshape((nx, ny)).T
    extent = [0, design_length, -DESIGN_HEIGHT / 2, DESIGN_HEIGHT / 2]
    aspect_ratio = DESIGN_HEIGHT / design_length
    fig_width = 4
    fig_height = fig_width * aspect_ratio + 1

    plt.figure(figsize=(fig_width, fig_height))
    plt.imshow(density, origin="lower", cmap="gray_r", vmin=0, vmax=1,
               extent=extent, aspect="equal")
    plt.colorbar(label="Density (0=SiO2/white, 1=Si/black)")
    plt.xlabel("x (µm)")
    plt.ylabel("y (µm)")

    # Build title with metrics
    full_title = title
    if fom is not None or binarization is not None:
        info_parts = []
        if fom is not None:
            info_parts.append(f"FOM={fom:.4f}")
        if binarization is not None:
            info_parts.append(f"Bin={binarization:.3f}")
        full_title = f"{title}\\n{', '.join(info_parts)}"
    plt.title(full_title)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()

# Usage: save per iteration
# save_density_plot(design_vars, nx, ny, L,
#     output_dir / f"design_iter{iteration:03d}.png",
#     f"Iter {iteration}", fom=current_fom, binarization=bin_metric)
""",
"save density plot adjoint, design iteration plot, gray_r colormap Si SiO2, "
"design_iter png adjoint, density plot FOM annotation, reshape design vector 2D, "
"topology optimization density visualization, imshow design MEEP adjoint, "
"밀도 플롯, 설계 밀도 시각화, design iteration 저장, gray_r Si 검정 SiO2 흰색"
),

# ─── 3. Field Animation 2D ───────────────────────────────────────────────────
(
"create_field_animation_2d",
"""Create 2D field propagation animation (MP4) using mp.Animate2D. \
Records Ez field (TE polarization, ODD_Z parity) with normalize=True. \
Uses stop_when_fields_decayed for automatic termination. \
Saves as field_propagation.mp4 at 15 fps. Do NOT specify eps_parameters or \
field_parameters — MEEP defaults show structure more clearly. \
2D 필드 전파 애니메이션: Ez field, mp.Animate2D, stop_when_fields_decayed, MP4 저장.""",
"""\
import meep as mp
from pathlib import Path

def create_field_animation(sim, layout: dict, output_dir: Path,
                           FREQUENCY: float = 1/1.55):
    \"\"\"Create 2D field propagation animation using mp.Animate2D.
    
    Note: Do NOT set eps_parameters/field_parameters — MEEP defaults
    give clearer structure visualization.
    \"\"\"
    anim = mp.Animate2D(
        sim,
        fields=mp.Ez,          # Ez for 2D TE (ODD_Z parity)
        realtime=False,
        normalize=True,        # Auto-normalize for visibility
        output_plane=mp.Volume(
            center=mp.Vector3(),
            size=mp.Vector3(layout["sx"], layout["sy"], 0),
        ),
    )

    sim.run(
        mp.at_every(max(1.0, 0.5 / FREQUENCY), anim),
        until_after_sources=mp.stop_when_fields_decayed(
            50, mp.Ez,
            mp.Vector3(layout["output_monitor_x"], 0, 0),
            1e-3
        ),
    )

    # Save as MP4 (prefer over GIF: smaller, better compatibility)
    anim.to_mp4(15, str(output_dir / "field_propagation.mp4"))
""",
"field animation 2D MEEP, mp.Animate2D, Ez field animation, field_propagation.mp4, "
"animate2D to_mp4, stop_when_fields_decayed animation, TE field animation, "
"normalize Animate2D, 2D field propagation video, "
"2D 필드 애니메이션, field 전파 동영상, mp.Animate2D 사용법, Ez 필드 시각화"
),

# ─── 4. Field Animation 3D ───────────────────────────────────────────────────
(
"create_field_animation_3d",
"""Create 3D SOI slab field propagation animation (MP4). \
Records Ey field (dominant for SOI TE-like mode) on XY slice at slab center \
(z = SLAB_THICKNESS/2). Uses mp.Animate2D with output_plane specifying z position. \
3D SOI 슬랩 필드 애니메이션: Ey 필드, slab center XY 슬라이스, MP4 저장.""",
"""\
import meep as mp
from pathlib import Path

def create_field_animation_3d(sim, layout: dict, output_dir: Path,
                               SLAB_THICKNESS: float = 0.22):
    \"\"\"Create 3D field animation on XY slice at slab center.
    
    Use Ey for SOI TE-like mode (dominant component).
    output_plane z = SLAB_THICKNESS/2 captures slab center.
    \"\"\"
    anim = mp.Animate2D(
        sim,
        fields=mp.Ey,          # Ey dominant for SOI slab TE-like mode
        realtime=False,
        normalize=True,
        output_plane=mp.Volume(
            center=mp.Vector3(0, 0, SLAB_THICKNESS / 2),  # slab center
            size=mp.Vector3(layout["sx"], layout["sy"], 0)
        ),
    )

    sim.run(mp.at_every(0.5, anim), until=80)
    anim.to_mp4(10, str(output_dir / "field_propagation.mp4"))
""",
"3D field animation MEEP, mp.Animate2D 3D, Ey field SOI slab, XY slice animation, "
"slab center field animation, 3D field propagation video, Animate2D output_plane 3D, "
"SOI waveguide field animation, field_propagation.mp4 3D, "
"3D 필드 애니메이션, SOI slab Ey 필드, slab center 슬라이스"
),

# ─── 5. Theoretical Mode Profiles + Overlap ──────────────────────────────────
(
"theoretical_mode_profiles",
"""Theoretical TE0/TE1 mode profile functions and overlap integral calculation. \
TE0: symmetric cosine profile inside waveguide core. \
TE1: antisymmetric sine profile (2π/width). \
compute_overlap: normalized overlap integral \
|∫E_sim·E_ref* dy|² / (∫|E_sim|²dy · ∫|E_ref|²dy). \
Used to verify mode conversion quality in TE0→TE1 converter. \
이론적 TE0/TE1 프로파일: cos/sin 분포, overlap integral 계산.""",
"""\
import numpy as np

def theoretical_te0_profile(y: np.ndarray, width: float) -> np.ndarray:
    \"\"\"Theoretical TE0 mode profile: symmetric cosine inside waveguide core.
    
    Args:
        y: Y coordinates (centered at 0), same units as width
        width: Waveguide width in µm
    Returns:
        Normalized profile (peak = 1.0)
    \"\"\"
    profile = np.zeros_like(y)
    inside = np.abs(y) <= width / 2
    profile[inside] = np.cos(np.pi * y[inside] / width)
    if np.max(np.abs(profile)) > 0:
        profile = np.abs(profile) / np.max(np.abs(profile))
    return profile


def theoretical_te1_profile(y: np.ndarray, width: float) -> np.ndarray:
    \"\"\"Theoretical TE1 mode profile: antisymmetric sine inside waveguide core.
    
    Args:
        y: Y coordinates (centered at 0), same units as width
        width: Waveguide width in µm
    Returns:
        Normalized profile (peak = 1.0)
    \"\"\"
    profile = np.zeros_like(y)
    inside = np.abs(y) <= width / 2
    profile[inside] = np.sin(2 * np.pi * y[inside] / width)
    if np.max(np.abs(profile)) > 0:
        profile = np.abs(profile) / np.max(np.abs(profile))
    return profile


def compute_overlap(E_sim: np.ndarray, E_ref: np.ndarray,
                    y: np.ndarray) -> float:
    \"\"\"Normalized overlap integral between simulated and reference mode.
    
    Formula: |∫ E_sim * E_ref* dy|² / (∫|E_sim|²dy · ∫|E_ref|²dy)
    
    Returns:
        Overlap value in [0, 1]
    \"\"\"
    numerator   = np.abs(np.trapezoid(E_sim * np.conj(E_ref), y)) ** 2
    denominator = (np.trapezoid(np.abs(E_sim) ** 2, y) *
                   np.trapezoid(np.abs(E_ref) ** 2, y))
    if denominator > 1e-20:
        return float(numerator / denominator)
    return 0.0


# Usage example:
# y = np.linspace(-2, 2, 200)
# te0 = theoretical_te0_profile(y, width=0.5)   # 500nm waveguide
# te1 = theoretical_te1_profile(y, width=4.0)   # 4µm output waveguide
# overlap = compute_overlap(simulated_Ey_profile, te1, y)
# print(f"TE1 overlap: {overlap:.3f}")  # target > 0.9
""",
"theoretical TE0 TE1 mode profile, overlap integral MEEP, mode overlap calculation, "
"compute_overlap function, TE0 cosine profile, TE1 sine antisymmetric profile, "
"mode conversion verification, mode purity calculation, "
"np.trapezoid overlap integral, normalized overlap, "
"TE0 TE1 이론 프로파일, overlap integral 계산, 모드 중첩 적분, 모드 변환 검증"
),

# ─── 6. Final Structure Plot ──────────────────────────────────────────────────
(
"plot_final_structure",
"""Plot final optimized design: side-by-side grayscale and binarized views. \
Left panel: grayscale density (gray_r). Right panel: binarized (threshold=0.5). \
Both use same extent and aspect='equal' for geometric accuracy. \
Saves as final_structure.png. \
최종 구조 플롯: grayscale + binarized 2패널 비교, threshold=0.5.""",
"""\
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

def plot_final_structure(design_vector: np.ndarray, nx: int, ny: int,
                         design_length: float, output_dir: Path,
                         DESIGN_HEIGHT: float = 3.0):
    \"\"\"Save final structure with grayscale and binarized (threshold=0.5) views.\"\"\"
    density = design_vector.reshape((nx, ny)).T
    binary  = (density > 0.5).astype(float)  # Hard threshold
    extent  = [0, design_length, -DESIGN_HEIGHT / 2, DESIGN_HEIGHT / 2]

    fig, axes = plt.subplots(1, 2, figsize=(12, 8))

    # Left: grayscale
    im0 = axes[0].imshow(density, origin='lower', cmap='gray_r',
                          vmin=0, vmax=1, extent=extent, aspect='equal')
    axes[0].set_title('Final Design (Grayscale)')
    axes[0].set_xlabel('x (µm)')
    axes[0].set_ylabel('y (µm)')
    plt.colorbar(im0, ax=axes[0], label='Density')

    # Right: binarized
    im1 = axes[1].imshow(binary, origin='lower', cmap='gray_r',
                          vmin=0, vmax=1, extent=extent, aspect='equal')
    axes[1].set_title('Final Design (Binarized, threshold=0.5)')
    axes[1].set_xlabel('x (µm)')
    axes[1].set_ylabel('y (µm)')
    plt.colorbar(im1, ax=axes[1], label='Density')

    plt.tight_layout()
    plt.savefig(output_dir / 'final_structure.png', dpi=150, bbox_inches='tight')
    plt.close()
""",
"plot final structure adjoint, final_structure.png, binarized design plot, "
"grayscale vs binary design, threshold 0.5 binarization plot, "
"final optimized design visualization, gray_r final structure, "
"최종 구조 플롯, 이진화 설계 시각화, final design grayscale binarized"
),

# ─── 7. History JSON/NPY ─────────────────────────────────────────────────────
(
"history_json_format",
"""Standard history dictionary format for adjoint optimization logging. \
Tracks: fom list, gradient_norm list, beta schedule, binarization metric, \
best_fom value and best_iteration index. \
Saves as both history.json (human-readable) and history.npy (backward compat). \
adjoint 최적화 히스토리: fom/gradient/beta/binarization 추적, JSON+NPY 저장.""",
"""\
import json
import numpy as np
from pathlib import Path

# Initialize history dictionary
history = {
    'fom':            [],    # FOM value per iteration
    'gradient_norm':  [],    # Gradient norm per iteration
    'beta':           [],    # Beta value per iteration
    'binarization':   [],    # Binarization metric per iteration
    'best_fom':       0.0,   # Best FOM achieved so far
    'best_iteration': 0,     # Iteration index of best FOM
}

# Update after each iteration
def update_history(history, fom, grad_norm, beta, binarization, iteration):
    history['fom'].append(float(fom))
    history['gradient_norm'].append(float(grad_norm))
    history['beta'].append(float(beta))
    history['binarization'].append(float(binarization))
    if fom > history['best_fom']:
        history['best_fom'] = float(fom)
        history['best_iteration'] = iteration

# Save history to files
def save_history(history, output_dir: Path):
    # JSON (human readable, for analysis/plotting)
    with open(output_dir / "history.json", "w") as f:
        json.dump(history, f, indent=2)
    # NPY (backward compatibility with older scripts)
    np.save(output_dir / "history.npy", history)

# Load history (for resume or analysis)
def load_history(output_dir: Path) -> dict:
    json_path = output_dir / "history.json"
    if json_path.exists():
        with open(json_path) as f:
            return json.load(f)
    return None
""",
"history json adjoint optimization, history.json format MEEP, "
"optimization history tracking, fom history list, gradient norm history, "
"beta schedule history, save history json npy, load history resume adjoint, "
"adjoint 히스토리 저장, history.json 형식, optimization 기록"
),

# ─── 8. MPI-Compatible Logging ───────────────────────────────────────────────
(
"setup_logging_mpi",
"""Setup Python logging compatible with MPI parallel execution. \
Only master process (mp.am_master()) adds file/console handlers \
to prevent duplicate log entries from all MPI ranks. \
Non-master processes get NullHandler. \
Logs to both run.log file and stdout simultaneously. \
MPI 병렬 호환 로깅: am_master() 가드로 중복 출력 방지, run.log 파일 + stdout.""",
"""\
import logging
import sys
import meep as mp
from pathlib import Path

def setup_logging(output_dir: Path, stage_name: str) -> logging.Logger:
    \"\"\"Setup logging for MPI parallel simulation.
    
    Only master process writes to file/console.
    Non-master processes get NullHandler (silent).
    \"\"\"
    logger = logging.getLogger(stage_name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    if mp.am_master():
        # File handler → run.log
        fh = logging.FileHandler(output_dir / "run.log")
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(fh)

        # Console handler → stdout
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(ch)
    else:
        # Non-master MPI ranks: suppress all output
        logger.addHandler(logging.NullHandler())

    return logger

# Usage:
# logger = setup_logging(output_dir, "stage1")
# logger.info(f"Iteration {i}: FOM={fom:.4f}")
# → Only printed/saved once, not duplicated across MPI ranks
""",
"MPI logging MEEP, setup_logging MPI, am_master logging, "
"avoid duplicate MPI output, run.log MEEP, NullHandler non-master MPI, "
"MPI parallel logging, am_master guard logging, "
"MPI 로깅, 중복 출력 방지, am_master 가드, run.log 설정"
),

# ─── 9. Compute Binarization ─────────────────────────────────────────────────
(
"compute_binarization",
"""Binarization metric for adjoint optimization design variables. \
Formula: mean(|2x - 1|) where x ∈ [0,1]. \
Returns 0.0 for fully grayscale (x=0.5 everywhere), 1.0 for fully binary (all 0 or 1). \
Track over iterations to monitor binarization progress. Target > 0.95 for fabrication. \
이진화 지표: mean(|2x-1|), 0=완전 회색, 1=완전 이진, 목표 > 0.95.""",
"""\
import numpy as np

def compute_binarization(vec: np.ndarray) -> float:
    \"\"\"Binarization metric: mean of |2x - 1| over design variables.
    
    Returns:
        0.0 = fully grayscale (x=0.5 everywhere)
        1.0 = fully binary (all x=0 or x=1)
    Target: > 0.95 for fabrication-ready design.
    \"\"\"
    return float(np.mean(np.abs(2.0 * vec - 1.0)))

# Usage in optimization loop:
# bin_metric = compute_binarization(design_vars)
# history['binarization'].append(bin_metric)
# if bin_metric > 0.95:
#     logger.info("Design is sufficiently binarized for fabrication")
""",
"compute binarization adjoint, binarization metric MEEP, binary metric design, "
"mean abs 2x-1 binarization, fabrication binarization threshold, "
"binarization monitor optimization, design binarization 0 to 1, "
"이진화 지표, binarization 계산, 설계 이진화 확인"
),

# ─── 10. Minimum Feature Size ────────────────────────────────────────────────
(
"find_minimum_feature_size",
"""Calculate minimum feature size (MFS) of binarized design using distance transform. \
Computes minimum Si feature width and minimum SiO2 gap separately, returns smaller. \
Uses scipy.ndimage.distance_transform_edt on binary mask. \
pixel_size_nm = 1000 / (resolution * scale_factor). \
MFS 계산: distance transform, Si 최소 크기 + SiO2 최소 갭 비교, nm 단위 반환.""",
"""\
import numpy as np
from scipy.ndimage import distance_transform_edt

def find_minimum_feature_size(design: np.ndarray, pixel_size_nm: float) -> float:
    \"\"\"Calculate minimum feature size using distance transform.
    
    Args:
        design: 2D design array (values in [0,1])
        pixel_size_nm: Physical size of one pixel in nm
                       = 1000 / (resolution_per_um * um_per_pixel)
    Returns:
        Minimum feature size in nm (min of Si width and SiO2 gap)
    \"\"\"
    binary = (design > 0.5).astype(int)  # Binarize first

    # Si (solid) region minimum feature
    dist_si  = distance_transform_edt(binary)
    min_si   = (np.min(dist_si[binary == 1]) * 2 * pixel_size_nm
                if np.any(binary) else 0)

    # SiO2 (hole/gap) region minimum feature
    dist_sio2 = distance_transform_edt(1 - binary)
    min_sio2  = (np.min(dist_sio2[binary == 0]) * 2 * pixel_size_nm
                 if np.any(1 - binary) else 0)

    if min_si > 0 and min_sio2 > 0:
        return min(min_si, min_sio2)
    return max(min_si, min_sio2)

# Example:
# resolution = 50  # pixels per µm
# pixel_size_nm = 1000 / resolution  # = 20 nm per pixel
# mfs = find_minimum_feature_size(final_design_2d, pixel_size_nm)
# print(f"Minimum feature size: {mfs:.1f} nm")  # Target: > 100 nm
""",
"minimum feature size MEEP adjoint, MFS calculation, distance_transform_edt MFS, "
"fabrication constraint feature size, minimum Si width SiO2 gap, "
"find_minimum_feature_size, pixel size nm MFS, "
"최소 피처 크기, MFS 계산, distance transform 이진화, fabrication 제약 확인"
),

# ─── 11. Beta Schedule ───────────────────────────────────────────────────────
(
"get_beta_schedule",
"""Multi-phase beta schedule for gradual binarization in adjoint topology optimization. \
Phase 1 (iter 1-20): beta=2 (hold, initial exploration). \
Phase 2 (iter 21-50): beta 2→32 (gradual increase). \
Phase 3 (iter 51-70): beta 32→64. \
Phase 4 (iter 71+): beta=128 (hold for final binarization). \
Abrupt beta increase causes FOM collapse — use gradual schedule. \
Beta 스케줄: 점진적 증가로 FOM 붕괴 방지, 4단계 멀티페이즈.""",
"""\
import numpy as np

def get_beta_schedule(n_iters: int) -> np.ndarray:
    \"\"\"Multi-phase beta schedule for gradual binarization.
    
    Phase 1 (1-20):   beta = 2      (hold, initial exploration)
    Phase 2 (21-50):  beta 2 → 32  (gradual increase)
    Phase 3 (51-70):  beta 32 → 64 (moderate increase)
    Phase 4 (71+):    beta = 128   (hold for final binarization)
    
    WARNING: Abrupt beta increase → FOM collapse.
    Always use gradual schedule, not step jumps.
    \"\"\"
    phase1_end = min(20, n_iters)
    phase2_end = min(50, n_iters)
    phase3_end = min(70, n_iters)

    beta_schedule = np.zeros(n_iters)

    if phase1_end > 0:
        beta_schedule[:phase1_end] = 2.0

    if phase2_end > phase1_end:
        beta_schedule[phase1_end:phase2_end] = np.linspace(
            2, 32, phase2_end - phase1_end)

    if phase3_end > phase2_end:
        beta_schedule[phase2_end:phase3_end] = np.linspace(
            32, 64, phase3_end - phase2_end)

    if n_iters > phase3_end:
        beta_schedule[phase3_end:] = 128.0

    return beta_schedule

# Usage:
# beta_sched = get_beta_schedule(n_iterations)
# for i, beta in enumerate(beta_sched):
#     # Apply tanh projection with current beta
#     projected = mpa.tanh_projection(filtered, beta, eta=0.5)
""",
"beta schedule adjoint, multi-phase beta binarization, gradual beta increase, "
"beta collapse prevention, tanh projection beta, beta schedule numpy linspace, "
"binarization schedule adjoint optimization, FOM collapse beta fix, "
"beta 스케줄, 점진적 beta 증가, FOM 붕괴 방지, binarization 스케줄"
),

# ─── 12. Poynting Vector from DFT ────────────────────────────────────────────
(
"compute_poynting_vector",
"""Compute time-averaged Poynting vector from DFT field arrays. \
3D formula: Px = 0.5*Re(Ey·Hz* - Ez·Hy*), Py = 0.5*Re(Ez·Hx* - Ex·Hz*), \
Pz = 0.5*Re(Ex·Hy* - Ey·Hx*). \
2D TE formula: Px = 0.5*Re(Ez·Hy*), Py = -0.5*Re(Ez·Hx*). \
Used for visualizing power flow direction and computing flux. \
Poynting 벡터: DFT 필드에서 시간평균 전력 흐름 계산, 2D/3D 공식.""",
"""\
import numpy as np

# ── 3D Poynting vector from DFT complex field arrays ──────────────────────
def compute_poynting_3d(Ex, Ey, Ez, Hx, Hy, Hz):
    \"\"\"Time-averaged Poynting vector from 3D DFT fields.
    
    P = 0.5 * Re(E × H*)
    \"\"\"
    Px = 0.5 * np.real(Ey * np.conj(Hz) - Ez * np.conj(Hy))
    Py = 0.5 * np.real(Ez * np.conj(Hx) - Ex * np.conj(Hz))
    Pz = 0.5 * np.real(Ex * np.conj(Hy) - Ey * np.conj(Hx))
    return Px, Py, Pz


# ── 2D TE Poynting vector (Ez, Hx, Hy only) ──────────────────────────────
def compute_poynting_2d_te(Ez, Hx, Hy):
    \"\"\"Time-averaged Poynting vector for 2D TE polarization.
    
    TE: Ez dominant; Hx, Hy present; Ex=Ey=Hz=0
    \"\"\"
    Px =  0.5 * np.real(Ez * np.conj(Hy))
    Py = -0.5 * np.real(Ez * np.conj(Hx))
    Pz = np.zeros_like(Px)  # No z-propagation in 2D
    return Px, Py, Pz


# ── Usage with MEEP DFT arrays ────────────────────────────────────────────
# After sim.run():
# Ex = sim.get_dft_array(dft_mon, mp.Ex, 0)  # freq index 0
# Ey = sim.get_dft_array(dft_mon, mp.Ey, 0)
# ...
# Px, Py, Pz = compute_poynting_3d(Ex, Ey, Ez, Hx, Hy, Hz)
# # Plot |Px| to see power flow in x-direction
# plt.imshow(np.abs(Px), cmap='hot')
""",
"Poynting vector DFT MEEP, compute Poynting from DFT fields, "
"time-averaged power flow MEEP, E cross H conjugate, "
"Px Py Pz DFT fields, 2D TE Poynting vector, 3D Poynting MEEP, "
"power flow visualization adjoint, "
"Poynting 벡터 계산, DFT 필드 전력 흐름, 시간평균 전력"
),

# ─── 13. DFT Monitor 2D Setup ────────────────────────────────────────────────
(
"dft_monitor_2d_setup",
"""Set up 2D DFT field monitors for full XY plane and cross-section profiles. \
XY plane monitor: all 6 E/H components for field visualization. \
Input/output cross-section monitors: 1D profiles for mode analysis. \
nfreq=1 for single-frequency (efficient); increase for broadband. \
2D DFT 모니터 설정: XY 전체 평면 + 입출력 단면 모니터.""",
"""\
import meep as mp

# ── Full XY plane DFT monitor (all field components) ─────────────────────
# Register BEFORE sim.run()
def setup_dft_monitors_2d(sim, sx, sy, DPML, FREQUENCY,
                           source_x, output_monitor_x,
                           source_size_y):
    \"\"\"Setup DFT monitors for 2D simulation.
    
    Returns dict of DFT objects for later array extraction.
    \"\"\"
    # Full XY plane: all E/H components for field visualization
    dft_xy = sim.add_dft_fields(
        [mp.Ex, mp.Ey, mp.Ez, mp.Hx, mp.Hy, mp.Hz],
        FREQUENCY, 0, 1,          # center_freq, df, nfreq=1
        center=mp.Vector3(0, 0, 0),
        size=mp.Vector3(sx - 2*DPML, sy - 2*DPML, 0)
    )

    # Input cross-section: mode profile at source
    dft_input = sim.add_dft_fields(
        [mp.Ez, mp.Hx, mp.Hy],   # TE dominant components
        FREQUENCY, 0, 1,
        center=mp.Vector3(source_x, 0, 0),
        size=mp.Vector3(0, source_size_y, 0)  # YZ line
    )

    # Output cross-section: mode profile at monitor
    dft_output = sim.add_dft_fields(
        [mp.Ez, mp.Hx, mp.Hy],
        FREQUENCY, 0, 1,
        center=mp.Vector3(output_monitor_x, 0, 0),
        size=mp.Vector3(0, source_size_y, 0)
    )

    return {"xy": dft_xy, "input": dft_input, "output": dft_output}

# ── Extract arrays after sim.run() ───────────────────────────────────────
# dft_mons = setup_dft_monitors_2d(sim, ...)
# sim.run(until_after_sources=...)
# Ez_xy = sim.get_dft_array(dft_mons["xy"],    mp.Ez, 0)
# Ez_in = sim.get_dft_array(dft_mons["input"], mp.Ez, 0)
""",
"DFT monitor 2D MEEP, add_dft_fields 2D, XY plane DFT monitor, "
"DFT cross-section monitor, input output DFT monitor, "
"2D TE DFT fields setup, get_dft_array 2D, DFT all components, "
"2D DFT 모니터 설정, 단면 DFT 모니터, XY 평면 DFT"
),

# ─── 14. DFT Monitor 3D SOI ──────────────────────────────────────────────────
(
"dft_monitor_3d_soi_setup",
"""Set up 3D DFT field monitors for SOI slab simulation. \
XY plane monitor at slab center (z=SLAB_THICKNESS/2): all 6 components. \
YZ plane monitors at input/output x-positions: Ey, Ez, Hy, Hz for mode profile. \
slab_center = SLAB_THICKNESS/2 (substrate at z=0, slab top at z=SLAB_THICKNESS). \
3D SOI DFT 모니터: slab center XY 평면 + 입출력 YZ 단면.""",
"""\
import meep as mp

def setup_dft_monitors_3d(sim, cell_x, cell_y, DPML,
                           FREQUENCY, SLAB_THICKNESS,
                           input_monitor_x, output_monitor_x,
                           source_size_y, source_size_z):
    \"\"\"Setup DFT monitors for 3D SOI slab simulation.
    
    Coordinate convention:
    - Substrate: z < 0
    - Si slab: 0 <= z <= SLAB_THICKNESS (e.g., 0.22 µm)
    - slab_center: z = SLAB_THICKNESS / 2
    \"\"\"
    slab_center_z = SLAB_THICKNESS / 2  # = 0.11 µm for 220nm SOI

    # XY plane at slab center: all components for propagation view
    dft_xy = sim.add_dft_fields(
        [mp.Ex, mp.Ey, mp.Ez, mp.Hx, mp.Hy, mp.Hz],
        FREQUENCY, 0, 1,
        center=mp.Vector3(0, 0, slab_center_z),
        size=mp.Vector3(cell_x - 2*DPML, cell_y - 2*DPML, 0)
    )

    # YZ plane at input: Ey dominant for TE-like mode
    dft_input_yz = sim.add_dft_fields(
        [mp.Ey, mp.Ez, mp.Hy, mp.Hz],
        FREQUENCY, 0, 1,
        center=mp.Vector3(input_monitor_x, 0, slab_center_z),
        size=mp.Vector3(0, source_size_y, source_size_z)
    )

    # YZ plane at output: check TE1 mode profile
    dft_output_yz = sim.add_dft_fields(
        [mp.Ey, mp.Ez, mp.Hy, mp.Hz],
        FREQUENCY, 0, 1,
        center=mp.Vector3(output_monitor_x, 0, slab_center_z),
        size=mp.Vector3(0, source_size_y, source_size_z)
    )

    return {"xy": dft_xy, "input_yz": dft_input_yz, "output_yz": dft_output_yz}

# ── Extract Ey at output for mode profile ────────────────────────────────
# dft_mons = setup_dft_monitors_3d(sim, ...)
# sim.run(until=...)
# Ey_out = sim.get_dft_array(dft_mons["output_yz"], mp.Ey, 0)
# # Ey_out shape: (ny, nz) → take z-center slice for 1D profile
""",
"DFT monitor 3D MEEP SOI, add_dft_fields 3D, slab center DFT monitor, "
"YZ plane DFT monitor 3D, 3D DFT field setup SOI, XY plane 3D DFT, "
"input output DFT monitor 3D, SLAB_THICKNESS slab center z, "
"3D DFT 모니터, SOI slab DFT 설정, slab center z 좌표, YZ 단면 모니터"
),

# ─── 15. Output Directory Structure ──────────────────────────────────────────
(
"output_directory_structure",
"""Standard output directory structure for MEEP inverse design projects. \
Root: results_stage1_grayscale/{timestamp_dir}/. \
Subdirs: design_iterations/ (per-iter density plots), \
validation/ (field animation, mode profiles, DFT fields), \
validation/fields/ (individual field component PNGs), \
validation/mode_decomposition/ (JSON + bar chart). \
File naming: design_iter{N:03d}.png, field_propagation.mp4, history.json. \
역설계 출력 디렉토리 구조: stage1/validation/fields/ 계층, 파일 명명 규칙.""",
"""\
from pathlib import Path
from datetime import datetime

def create_output_dirs(project_name: str, design_length: float,
                       base_dir: Path = Path("results_stage1")) -> dict:
    \"\"\"Create standard output directory structure for inverse design.
    
    Returns dict of Path objects for each subdirectory.
    \"\"\"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base_dir / f"L{design_length:.1f}um_{timestamp}"

    dirs = {
        "root":             run_dir,
        "design_iters":     run_dir / "design_iterations",
        "validation":       run_dir / "validation",
        "fields":           run_dir / "validation" / "fields",
        "mode_decomp":      run_dir / "validation" / "mode_decomposition",
        "mode_profiles":    run_dir / "validation" / "mode_profiles",
    }

    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    return dirs

# Standard file naming convention:
# dirs["root"]        / "initial_layout.png"
# dirs["root"]        / "final_structure.png"
# dirs["root"]        / "convergence.png"
# dirs["root"]        / "history.json"
# dirs["root"]        / "history.npy"
# dirs["root"]        / "results.txt"
# dirs["root"]        / "config.json"
# dirs["root"]        / "best_design.npy"
# dirs["root"]        / "final_design.npy"
# dirs["design_iters"]/ f"design_iter{i:03d}.png"
# dirs["validation"]  / "field_propagation.mp4"
# dirs["validation"]  / "mode_purity.png"
# dirs["validation"]  / "dft_fields_all.png"     # 6-panel (2D) or 9-panel (3D)
# dirs["fields"]      / "field_Ey.png"           # individual component
# dirs["mode_decomp"] / "mode_decomposition.json"
# dirs["mode_profiles"]/ "dft_input_mode_profile.png"

# 3D DFT fields_all: 9-panel (Ex,Ey,Ez / Hx,Hy,Hz / Px,Py,Pz)
# 2D DFT fields_all: 6-panel (Re(Ez),Re(Hx),Re(Hy) / |Px|,|Py|,|Pz|)
""",
"output directory structure inverse design, results directory MEEP, "
"design_iterations directory, validation directory structure, "
"field_propagation mp4 location, history json output dir, "
"create output dirs MEEP adjoint, file naming convention design_iter, "
"출력 디렉토리 구조, 역설계 결과물 폴더, 파일 명명 규칙, 디렉토리 생성"
),

]  # end PATTERNS


def insert_patterns():
    conn = sqlite3.connect(DB_PATH)

    # Check which already exist
    existing = {r[0] for r in conn.execute("SELECT pattern_name FROM patterns").fetchall()}

    inserted = 0
    skipped  = 0

    for name, desc, code, use_case in PATTERNS:
        if name in existing:
            print(f"[SKIP] {name} (already exists)")
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

    total = conn.execute if False else None  # just formatting
    print(f"\nInserted: {inserted}, Skipped: {skipped}")
    print(f"New total: {101 + inserted}")


if __name__ == "__main__":
    insert_patterns()
