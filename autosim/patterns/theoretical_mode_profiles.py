#!/usr/bin/env python3
"""
Pattern: theoretical_mode_profiles
Theoretical TE0/TE1 mode profile functions and overlap integral calculation. TE0: symmetric cosine profile inside wavegu
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "theoretical_mode_profiles"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def theoretical_te0_profile(y: np.ndarray, width: float) -> np.ndarray:
        """Theoretical TE0 mode profile: symmetric cosine inside waveguide core.
    
        Args:
            y: Y coordinates (centered at 0), same units as width
            width: Waveguide width in µm
        Returns:
            Normalized profile (peak = 1.0)
        """
        profile = np.zeros_like(y)
        inside = np.abs(y) <= width / 2
        profile[inside] = np.cos(np.pi * y[inside] / width)
        if np.max(np.abs(profile)) > 0:
            profile = np.abs(profile) / np.max(np.abs(profile))
        return profile

    def theoretical_te1_profile(y: np.ndarray, width: float) -> np.ndarray:
        """Theoretical TE1 mode profile: antisymmetric sine inside waveguide core.
    
        Args:
            y: Y coordinates (centered at 0), same units as width
            width: Waveguide width in µm
        Returns:
            Normalized profile (peak = 1.0)
        """
        profile = np.zeros_like(y)
        inside = np.abs(y) <= width / 2
        profile[inside] = np.sin(2 * np.pi * y[inside] / width)
        if np.max(np.abs(profile)) > 0:
            profile = np.abs(profile) / np.max(np.abs(profile))
        return profile

    def compute_overlap(E_sim: np.ndarray, E_ref: np.ndarray,
                        y: np.ndarray) -> float:
        """Normalized overlap integral between simulated and reference mode.
    
        Formula: |∫ E_sim * E_ref* dy|² / (∫|E_sim|²dy · ∫|E_ref|²dy)
    
        Returns:
            Overlap value in [0, 1]
        """
        numerator   = np.abs(np.trapezoid(E_sim * np.conj(E_ref), y)) ** 2
        denominator = (np.trapezoid(np.abs(E_sim) ** 2, y) *
                       np.trapezoid(np.abs(E_ref) ** 2, y))
        if denominator > 1e-20:
            return float(numerator / denominator)
        return 0.0

    # Usage example:
    # y = np.linspace(-2, 2, 200)
    # te0 = theoretical_te0_profile(y, width=0.5)   # 500nm waveguide
    # te1 = theoretical_te1_profile(y, width=4.0)   # 4µm output waveguide
    # overlap = compute_overlap(simulated_Ey_profile, te1, y)
    # print(f"TE1 overlap: {overlap:.3f}")  # target > 0.9
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
