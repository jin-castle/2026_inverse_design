#!/usr/bin/env python3
"""
Pattern: dft_field_monitor_3d
Set up and extract DFT field monitor in 3D MEEP simulation for SOI slab waveguide. Records Ey field at a fixed YZ cross-
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "dft_field_monitor_3d"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # DFT field monitors for time-averaged mode profile
    # Ey component for TE-like mode in SOI slab
    dft_input = sim.add_dft_fields(
        [mp.Ey],
        FREQUENCY, 0, 1,  # center_freq, df, nfreq
        center=mp.Vector3(input_monitor_x, 0, 0),
        size=mp.Vector3(0, monitor_size_y, monitor_size_z)  # YZ plane
    )

    dft_output = sim.add_dft_fields(
        [mp.Ey],
        FREQUENCY, 0, 1,
        center=mp.Vector3(output_monitor_x, 0, 0),
        size=mp.Vector3(0, monitor_size_y, monitor_size_z)
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
