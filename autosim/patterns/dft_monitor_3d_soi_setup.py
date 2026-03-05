#!/usr/bin/env python3
"""
Pattern: dft_monitor_3d_soi_setup
Set up 3D DFT field monitors for SOI slab simulation. XY plane monitor at slab center (z=SLAB_THICKNESS/2): all 6 compon
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "dft_monitor_3d_soi_setup"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def setup_dft_monitors_3d(sim, cell_x, cell_y, DPML,
                               FREQUENCY, SLAB_THICKNESS,
                               input_monitor_x, output_monitor_x,
                               source_size_y, source_size_z):
        """Setup DFT monitors for 3D SOI slab simulation.
    
        Coordinate convention:
        - Substrate: z < 0
        - Si slab: 0 <= z <= SLAB_THICKNESS (e.g., 0.22 µm)
        - slab_center: z = SLAB_THICKNESS / 2
        """
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
