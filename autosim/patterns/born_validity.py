#!/usr/bin/env python3
"""
Pattern: born_validity
Born validity gradient filtering: retain top 50% magnitude + remove top 0.1% outliers
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "born_validity"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def born_validity(gradient: np.ndarray, top_k: float = 50.0) -> np.ndarray:
        """Apply Born validity filtering to gradient.

        msopt/Opt_MS2.py Born_validity 포팅.

        상위 top_k% gradient만 유지하고, outlier 제거.
        Born Approximation의 유효 범위를 유지하기 위해
        노이즈가 많은 작은 gradient를 제거하고 의미있는 gradient만 사용.

        Args:
            gradient: 1D gradient array
            top_k: Top percentage of gradient magnitudes to keep (default 50%)

        Returns:
            Filtered gradient with outliers removed and only top_k% retained
        """
        grad = gradient.copy().flatten()

        # Step 1: Remove extreme outliers (top 0.1%)
        outlier_th = np.percentile(np.abs(grad), 99.9)
        grad = np.where(np.abs(grad) > outlier_th, 0.0, grad)

        # Step 2: Keep only top top_k% gradients
        if top_k < 100:
            born_th = np.percentile(np.abs(grad), 100 - top_k)
            grad = np.where(np.abs(grad) >= born_th, grad, 0.0)

        return grad
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
