#!/usr/bin/env python3
"""
Pattern: optimization_5stage_workflow
5-stage inverse design workflow for SOI photonic devices. Stage 1: MPB mode analysis - verify TE1 not cutoff in 1um, get
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "optimization_5stage_workflow"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
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

    for length in [5.0, 6.0, 7.0, 8.0, 9.0, 10.0]:  # um
        result_dir = f"results/length_{length:.0f}um"
        os.makedirs(result_dir, exist_ok=True)
        # run_optimization(design_length=length, output_dir=result_dir)

    # Select shortest length with FOM > 0.90, then run Stage 5 for that one only
    # ─────────────────────────────────────────────────────────

    # figure 자동 저장
    _outputs = []
    if plt.get_fignums():
        _out = savefig_safe(_PATTERN)
        if _out:
            _outputs.append("output.png")

    _elapsed = round(_time.time() - _t0, 2)
    save_result(_PATTERN, outputs=_outputs, elapsed=_elapsed)
    if mp.am_master():
        print(f"[OK] {_PATTERN} ({_elapsed}s) outputs={_outputs}")

except Exception as _e:
    _elapsed = round(_time.time() - _t0, 2)
    save_result(_PATTERN, error=_e, elapsed=_elapsed)
    import traceback
    traceback.print_exc()
    sys.exit(1)
