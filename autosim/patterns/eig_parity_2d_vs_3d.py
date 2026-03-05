#!/usr/bin/env python3
"""
Pattern: eig_parity_2d_vs_3d
eig_parity rules for TE/TM mode selection in 2D vs 3D MEEP. 2D (xy plane, z=infinite): TE has Ey,Hx,Hz components -> eig
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "eig_parity_2d_vs_3d"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
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
