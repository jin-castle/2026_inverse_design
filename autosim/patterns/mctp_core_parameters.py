#!/usr/bin/env python3
"""
Pattern: mctp_core_parameters
Core parameters for PROJ-002 MCTP: TE0 to TE1 mode conversion with 12um to 1um width taper on SOI 220nm platform. Input:
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "mctp_core_parameters"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
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
