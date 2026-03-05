#!/usr/bin/env python3
"""
Pattern: get_adaptive_eta
Adaptive eta according to beta: ±2% at low beta, ±3% at high beta (approximately ±7~10nm tolerance)
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "get_adaptive_eta"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def get_adaptive_eta(
        beta: float,
        beta_min: float = 2.0,
        beta_max: float = 128.0,
        eta_max: float = 0.03,
    ):
        """Get adaptive eta values based on current beta.

        At low beta, use smaller eta range to avoid sudden transitions.
        At high beta, use full eta range for proper erosion/dilation.

        Updated 2026-01-06: Reduced eta_max to ±3% (from ±5%) to prevent FOM collapse.
        ±3% corresponds to approximately ±7-10nm fabrication tolerance.

        Args:
            beta: Current projection strength
            beta_min: Minimum beta (start of schedule)
            beta_max: Maximum beta (end of schedule)
            eta_max: Maximum eta range (0.03 = ±3%, 0.05 = ±5%)

        Returns:
            Tuple of (eta_dilated, eta_intrinsic, eta_eroded)
            - beta=2: eta_range=0.02 → (0.48, 0.50, 0.52)
            - beta=64: eta_range=0.03 → (0.47, 0.50, 0.53)
        """
        t = min(1.0, max(0.0, (beta - beta_min) / (beta_max - beta_min)))
        eta_range = 0.02 + (eta_max - 0.02) * t  # 0.02 → eta_max (±2% → ±3%)

        eta_eroded = 0.5 + eta_range
        eta_dilated = 0.5 - eta_range
        eta_intrinsic = 0.5

        return eta_dilated, eta_intrinsic, eta_eroded
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
