#!/usr/bin/env python3
"""
Pattern: apply_conic_filter
Apply conic (cone-shaped) spatial filter to design variables for minimum feature size (MFS) control. filter_radius = MFS
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "apply_conic_filter"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def apply_conic_filter(
        weights: np.ndarray,
        nx: int,
        ny: int,
        filter_radius_um: float,
        design_resolution: int = None,
        design_length: float = None,
        design_height: float = None,
    ) -> np.ndarray:
        """Apply conic filter for minimum feature size enforcement.

        Uses MEEP's built-in conic_filter function.

        Args:
            weights: 1D array of design weights
            nx: Number of pixels in x direction
            ny: Number of pixels in y direction
            filter_radius_um: Filter radius in micrometers
            design_resolution: Resolution in px/um (default: DESIGN_RESOLUTION)
            design_length: Design length in um (default: DESIGN_LENGTH)
            design_height: Design height in um (default: DESIGN_HEIGHT)
        """
        # Use defaults if not provided (backwards compatibility)
        if design_resolution is None:
            design_resolution = DESIGN_RESOLUTION
        if design_length is None:
            design_length = DESIGN_LENGTH
        if design_height is None:
            design_height = DESIGN_HEIGHT

        weights_2d = weights.reshape((nx, ny))

        # Use MEEP's conic filter
        filtered = mpa.conic_filter(
            weights_2d,
            filter_radius_um,
            design_length,
            design_height,
            design_resolution
        )

        return filtered.flatten()
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
