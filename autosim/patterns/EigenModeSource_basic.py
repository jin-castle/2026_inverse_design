#!/usr/bin/env python3
"""
Pattern: EigenModeSource_basic
EigenModeSource: Basic example of creating a waveguide eigenmode source (wvg-src.py)
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "EigenModeSource_basic"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # Example file illustrating an eigenmode source, generating a waveguide mode
    # (requires recent MPB version to be installed before Meep is compiled)

    cell = mp.Vector3(16, 8)

    # an asymmetrical dielectric waveguide:
    geometry = [
        mp.Block(
            center=mp.Vector3(),
            size=mp.Vector3(mp.inf, 1, mp.inf),
            material=mp.Medium(epsilon=12),
        ),
        mp.Block(
            center=mp.Vector3(y=0.3),
            size=mp.Vector3(mp.inf, 0.1, mp.inf),
            material=mp.Medium(),
        ),
    ]

    # create a transparent source that excites a right-going waveguide mode
    sources = [
        mp.EigenModeSource(
            src=mp.ContinuousSource(0.15),
            size=mp.Vector3(y=6),
            center=mp.Vector3(x=-5),
            component=mp.Dielectric,
            eig_parity=mp.ODD_Z,
        )
    ]

    pml_layers = [mp.PML(1.0)]

    force_complex_fields = True  # so we can get time-average flux

    resolution = 10
    # ... (truncated)
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
