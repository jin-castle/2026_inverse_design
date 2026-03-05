#!/usr/bin/env python3
"""
Pattern: LinearBetaScheduler
Tidy3D-inspired linear beta schedule: β(t)=β_min+(β_max-β_min)×t/T. Simple and predictable.
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "LinearBetaScheduler"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    class LinearBetaScheduler:
        """Tidy3D-inspired linear beta continuation.

        β(t) = β_min + (β_max - β_min) × t / T

        No convergence detection, no re-roll, no adaptive logic.
        Trade-off: Simple & predictable vs. Less flexible

        Tidy3D 검증:
        - Mode converter: β=5→20 over 20 iterations, 96% transmission
        - Waveguide bend: β=5→20 over 25 iterations

        Phase26 targets:
        - β_min=5.0, β_max=20.0
        - T=50-100 iterations (vs Phase25's 150-200)
        - 2-3x faster convergence
        """

        def __init__(
            self,
            beta_min: float = 5.0,
            beta_max: float = 20.0,
            num_iterations: int = 50,
        ):
            """Initialize linear beta scheduler.

            Args:
                beta_min: Starting beta (default: 5.0, Tidy3D)
                beta_max: Final beta (default: 20.0, Tidy3D)
                num_iterations: Total iterations (default: 50)
            """
            self.beta_min = beta_min
            self.beta_max = beta_max
            self.num_iterations = num_iterations
            self.current_beta = beta_min

        def get_beta(self, iteration: int) -> float:
            """Compute beta for given iteration.

            Args:
                iteration: Current iteration (1-indexed)

            Returns:
                beta: Linearly interpolated value

            Examples:
                >>> scheduler = LinearBetaScheduler(5, 20, 50)
                >>> scheduler.get_beta(1)   # 5.0
                >>> scheduler.get_beta(25)  # 12.5
                >>> scheduler.get_beta(50)  # 20.0
            """
            if iteration <= 1:
                return self.beta_min
            if iteration >= self.num_iterations:
                return self.beta_max

            # Linear interpolation
            t = (iteration - 1) / (self.num_iterations - 1)
            return self.beta_min + (self.beta_max - self.beta_min) * t

        def update(
            self,
            iteration: int,
            fom: float,
            binarization: float,
            design_vector: np.ndarray,
        ) -> dict:
            """Update beta (no adaptive logic).

            Args:
                iteration: Current iteration
                fom: Current figure of merit (unused)
                binarization: Current binarization (unused)
                design_vector: Current design (unused)

            Returns:
                dict with keys:
                    - beta: Current beta value
                    - status: Status message
                    - restore_best: Always False (never restores)
                    - lr_reset: Always None (never resets LR)
                    - should_exit: Always False (no early exit)
                    - phase: "linear"
            """
            self.current_beta = self.get_beta(iteration)

            return {
                "beta": self.current_beta,
                "status": f"Linear schedule: β={self.current_beta:.2f}",
                "restore_best": False,  # Never restores
                "lr_reset": None,  # Never resets LR
                "should_exit": False,  # No early exit
                "phase": "linear",
            }

        def save_state(self, path):
            """Save scheduler state.

            Args:
                path: Path to save pickle file
            """
            import pickle

            state = {
                "beta_min": self.beta_min,
                "beta_max": self.beta_max,
                "num_iterations": self.num_iterations,
                "current_beta": self.current_beta,
            }
            with open(path, "wb") as f:
                pickle.dump(state, f)

        def load_state(self, path):
            """Load scheduler state.

            Args:
                path: Path to load pickle file
            """
            import pickle

            with open(path, "rb") as f:
                state = pickle.load(f)

            self.beta_min = state["beta_min"]
            self.beta_max = state["beta_max"]
            self.num_iterations = state["num_iterations"]
            self.current_beta = state.get("current_beta", self.beta_min)

        def __repr__(self) -> str:
            return (
                f"LinearBetaScheduler("
                f"β={self.beta_min}→{self.beta_max}, "
                f"T={self.num_iterations}, "
                f"current={self.current_beta:.2f})"
            )
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
