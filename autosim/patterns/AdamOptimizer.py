#!/usr/bin/env python3
"""
Pattern: AdamOptimizer
bounds support Adam optimizer: dynamic LR, 0~1 clipping by default, override_lr support
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "AdamOptimizer"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    class AdamOptimizer:
        """Adam optimizer with bounds support and dynamic learning rate."""

        def __init__(
            self,
            size: int,
            learning_rate: float = 0.02,
            beta1: float = 0.9,
            beta2: float = 0.999,
            eps: float = 1e-8,
        ):
            self.lr = learning_rate
            self.beta1 = beta1
            self.beta2 = beta2
            self.eps = eps
            self.m = np.zeros(size)
            self.v = np.zeros(size)
            self.t = 0

        def set_learning_rate(self, lr: float):
            """동적 learning rate 설정."""
            self.lr = lr

        def update(
            self,
            params: np.ndarray,
            grad: np.ndarray,
            lower_bounds: np.ndarray = None,
            upper_bounds: np.ndarray = None,
            override_lr: float = None,
        ) -> np.ndarray:
            """Update parameters using Adam optimizer.

            Args:
                params: Current parameters
                grad: Gradient
                lower_bounds: Lower bounds for clipping
                upper_bounds: Upper bounds for clipping
                override_lr: Optional learning rate override (for backtracking)
            """
            lr = override_lr if override_lr is not None else self.lr

            self.t += 1
            self.m = self.beta1 * self.m + (1 - self.beta1) * grad
            self.v = self.beta2 * self.v + (1 - self.beta2) * (grad ** 2)
            m_hat = self.m / (1 - self.beta1 ** self.t)
            v_hat = self.v / (1 - self.beta2 ** self.t)
            params = params + lr * m_hat / (np.sqrt(v_hat) + self.eps)

            if lower_bounds is not None and upper_bounds is not None:
                params = np.clip(params, lower_bounds, upper_bounds)
            else:
                params = np.clip(params, 0.0, 1.0)

            return params

        def reset(self):
            """Reset optimizer state (momentum)."""
            self.m = np.zeros_like(self.m)
            self.v = np.zeros_like(self.v)
            self.t = 0
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
