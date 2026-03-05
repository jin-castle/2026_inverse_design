#!/usr/bin/env python3
"""
Pattern: apply_tanh_projection
Apply tanh projection to binarize grayscale design variables toward 0/1 (Si/SiO2). Formula: (tanh(beta*eta) + tanh(beta*
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "apply_tanh_projection"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def apply_tanh_projection(
        weights: np.ndarray,
        beta: float,
        eta: float = 0.5,
    ) -> np.ndarray:
        """Apply tanh projection for binarization.

        Args:
            weights: Design weights
            beta: Projection strength (higher = more binary)
            eta: Threshold (0.5 for intrinsic, 0.75 for eroded, 0.25 for dilated)
        """
        if beta <= 0:
            return weights.copy() if isinstance(weights, np.ndarray) else weights

        # MEEP's tanh projection formula
        tanh_beta_eta = npa.tanh(beta * eta)
        tanh_beta_one_minus_eta = npa.tanh(beta * (1.0 - eta))
        denom = tanh_beta_eta + tanh_beta_one_minus_eta

        return (tanh_beta_eta + npa.tanh(beta * (weights - eta))) / denom
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
