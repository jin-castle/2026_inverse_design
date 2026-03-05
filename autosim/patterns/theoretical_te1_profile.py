#!/usr/bin/env python3
"""
Pattern: theoretical_te1_profile
Theoretical TE1 mode profile: sine distribution inside waveguide, antisymmetric (first-order mode), peak=1 normalized
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "theoretical_te1_profile"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def theoretical_te0_profile(y: np.ndarray, width: float) -> np.ndarray:
        """
        Theoretical TE0 mode profile (symmetric, fundamental mode).

        TE0 mode has cosine distribution inside waveguide core.
        Args:
            y: Y coordinates (centered at 0)
            width: Waveguide width in same units as y
        Returns:
            Normalized mode profile (peak = 1.0)
        """
        profile = np.zeros_like(y)
        inside = np.abs(y) <= width / 2
        profile[inside] = np.cos(np.pi * y[inside] / width)
        if np.max(np.abs(profile)) > 0:
            profile = np.abs(profile) / np.max(np.abs(profile))
        return profile

    def theoretical_te1_profile(y: np.ndarray, width: float) -> np.ndarray:
        """
        Theoretical TE1 mode profile (antisymmetric, first order mode).

        TE1 mode has sine distribution inside waveguide core.
        Args:
            y: Y coordinates (centered at 0)
            width: Waveguide width in same units as y
        Returns:
            Normalized mode profile (peak = 1.0)
        """
        profile = np.zeros_like(y)
        inside = np.abs(y) <= width / 2
        profile[inside] = np.sin(2 * np.pi * y[inside] / width)
        if np.max(np.abs(profile)) > 0:
            profile = np.abs(profile) / np.max(np.abs(profile))
        return profile
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
