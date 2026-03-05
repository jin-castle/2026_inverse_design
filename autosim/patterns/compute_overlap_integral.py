#!/usr/bin/env python3
"""
Pattern: compute_overlap_integral
Normalized overlap integral: |∫E_sim·E_ref* dy|² / (∫|E_sim|²dy·∫|E_ref|²dy), return value 0~1
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "compute_overlap_integral"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def compute_overlap(E_sim: np.ndarray, E_ref: np.ndarray, y: np.ndarray) -> float:
        """
        Compute normalized overlap integral between simulation and reference mode.

        Overlap = |∫ E_sim * E_ref* dy|² / (∫|E_sim|² dy * ∫|E_ref|² dy)

        Args:
            E_sim: Simulated field profile (complex or real)
            E_ref: Reference mode profile (real)
            y: Y coordinates for integration
        Returns:
            Overlap value between 0 and 1
        """
        numerator = np.abs(np.trapezoid(E_sim * np.conj(E_ref), y)) ** 2
        denominator = np.trapezoid(np.abs(E_sim) ** 2, y) * np.trapezoid(np.abs(E_ref) ** 2, y)
        if denominator > 1e-20:
            return float(numerator / denominator)
        return 0.0
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
