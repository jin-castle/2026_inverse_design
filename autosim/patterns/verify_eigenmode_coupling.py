#!/usr/bin/env python3
"""
Pattern: verify_eigenmode_coupling
Verify eigenmode source coupling using sim.get_eigenmode(). Computes neff = k.x / frequency for each band to confirm cor
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "verify_eigenmode_coupling"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def verify_eigenmode_coupling(sim, source_x: float, source_size: mp.Vector3,
                                   frequency: float, num_bands: int = 5,
                                   parity=mp.ODD_Y):
        # Check eigenmode neff at source position.
        # Call after sim.init_sim() to verify band numbers before running.
        print(f"Eigenmode verification at x={source_x:.2f}")
        print(f"Source size y={source_size.y:.2f} um")
        print("-" * 40)

        for band in range(1, num_bands + 1):
            try:
                em = sim.get_eigenmode(
                    frequency,
                    mp.X,
                    mp.Volume(
                        center=mp.Vector3(source_x, 0, 0),
                        size=source_size
                    ),
                    band_num=band,
                    parity=parity,
                )
                neff = em.k.x / frequency
                print(f"  Band {band}: neff = {neff:.4f}")
            except Exception as e:
                print(f"  Band {band}: cutoff ({e})")

    # Expected for 12um SOI waveguide @ 1550nm:
    # Band 1: neff ~ 2.847  <- TE0 (eig_band=1 for source)
    # Band 2: neff ~ 2.710  <- TE1
    # Band 3: neff ~ 2.561  <- TE2
    # ... many modes in 12um multimode waveguide

    # Expected for 1um output waveguide:
    # Band 1: neff ~ 2.45   <- TE0
    # Band 2: neff ~ 1.98   <- TE1  (our target, check > 1.44 = not cutoff)
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
