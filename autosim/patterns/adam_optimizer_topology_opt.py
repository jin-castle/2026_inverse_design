#!/usr/bin/env python3
"""
Pattern: adam_optimizer_topology_opt
Adam optimizer for MEEP adjoint topology optimization with gradient ASCENT (maximize FOM). Key difference from standard 
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "adam_optimizer_topology_opt"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    class AdamOptimizer:
        # Adam optimizer for topology optimization.
        # Uses gradient ASCENT (+ update) to MAXIMIZE FOM.
        # Call reset() when changing beta to avoid stale moments.
        def __init__(self, learning_rate=0.01, beta1=0.9, beta2=0.999, epsilon=1e-8):
            self.lr      = learning_rate
            self.beta1   = beta1
            self.beta2   = beta2
            self.epsilon = epsilon
            self.m = None   # First moment
            self.v = None   # Second moment
            self.t = 0      # Time step

        def update(self, params: np.ndarray, grads: np.ndarray) -> np.ndarray:
            # Gradient ASCENT update - params in [0,1], grads from mpa.OptimizationProblem
            if self.m is None:
                self.m = np.zeros_like(params)
                self.v = np.zeros_like(params)
            self.t += 1

            self.m = self.beta1 * self.m + (1 - self.beta1) * grads
            self.v = self.beta2 * self.v + (1 - self.beta2) * (grads ** 2)
            m_hat  = self.m / (1 - self.beta1 ** self.t)
            v_hat  = self.v / (1 - self.beta2 ** self.t)

            # ASCENT: + not - (maximize FOM)
            params_new = params + self.lr * m_hat / (np.sqrt(v_hat) + self.epsilon)
            return np.clip(params_new, 0.0, 1.0)

        def reset(self):
            # Reset moments - call when changing beta!
            self.m = None
            self.v = None
            self.t = 0

    # Learning rate guide:
    # Grayscale (beta=0):  lr = 0.01 ~ 0.05
    # Low beta (1-8):      lr = 0.01 ~ 0.02
    # High beta (16-64):   lr = 0.005 ~ 0.01
    # Very high (128+):    lr = 0.001 ~ 0.005
    # -> Reduce lr as beta increases for stability

    # Usage in optimization loop:
    # optimizer = AdamOptimizer(learning_rate=0.01)
    # design = np.random.uniform(0.4, 0.6, n_pixels)
    # for i in range(n_iter):
    #     fom, grad = opt([design])
    #     design = optimizer.update(design, grad[0])
    # # When increasing beta:
    # # optimizer.reset()  <- IMPORTANT
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
