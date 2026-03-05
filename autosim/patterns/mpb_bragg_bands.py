#!/usr/bin/env python3
"""
Pattern: mpb_bragg_bands
MPB Bragg mirror band structure: ModeSolver, run_te, ky=0 band diagram
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "mpb_bragg_bands"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # Compute the bands at the X point for a quarter-wave stack Bragg
    # mirror (this is the point that defines the band gap edges).

    # the high and low indices:
    n_lo = 1.0
    n_hi = 3.0

    w_hi = n_lo / (n_hi + n_lo)  # a quarter_wave stack

    geometry_lattice = mp.Lattice(size=mp.Vector3(1))  # 1d cell
    default_material = mp.Medium(index=n_lo)
    geometry = mp.Cylinder(material=mp.Medium(index=n_hi), center=mp.Vector3(), axis=mp.Vector3(1),
                           radius=mp.inf, height=w_hi)

    kx = 0.5
    k_points = [mp.Vector3(kx)]

    resolution = 32
    num_bands = 8

    ms = mpb.ModeSolver(
        num_bands=num_bands,
        k_points=k_points,
        geometry_lattice=geometry_lattice,
        geometry=[geometry],
        resolution=resolution,
        default_material=default_material
    )

    def main():
        ms.run_tm(mpb.output_hfield_y)  # note that TM and TE bands are degenerate, so we only need TM

    if __name__ == '__main__':
        main()
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
