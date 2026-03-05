#!/usr/bin/env python3
"""
Pattern: sio2_substrate_pml_geometry
CRITICAL: SiO2 substrate geometry must extend to PML using mp.inf in x-direction. If SiO2 ends before PML, a SiO2/air in
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "sio2_substrate_pml_geometry"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
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
