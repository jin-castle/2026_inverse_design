#!/usr/bin/env python3
"""
Pattern: source_monitor_size_substrate
Source and Monitor must include the full waveguide cross-section including SiO2 substrate. Too-small source/monitor clip
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "source_monitor_size_substrate"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
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
