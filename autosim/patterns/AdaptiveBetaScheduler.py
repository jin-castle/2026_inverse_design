#!/usr/bin/env python3
"""
Pattern: AdaptiveBetaScheduler
Recovery period-based adaptive beta scheduler: monitoring FOM recovery during recovery_iters after beta increase
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "AdaptiveBetaScheduler"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    class AdaptiveBetaScheduler:
        """
        Adaptive beta scheduler with recovery period.

        After each beta increase, allows `recovery_iters` iterations for FOM to recover.
        Only freezes beta if FOM fails to recover after the grace period.
        This prevents getting stuck in local minima while still protecting against
        catastrophic FOM drops.
        """

        def __init__(
            self,
            n_iters: int,
            recovery_iters: int = 5,
            recovery_threshold: float = 0.90,
        ):
            """
            Args:
                n_iters: Total number of iterations
                recovery_iters: Number of iterations to wait for FOM recovery after beta increase
                recovery_threshold: FOM must recover to this fraction of pre-increase FOM
            """
            self.n_iters = n_iters
            self.recovery_iters = recovery_iters
            self.recovery_threshold = recovery_threshold
            self.current_beta = 2.0
            self.fom_before_increase = 0.0
            self.best_fom_during_recovery = 0.0
            self.iters_since_increase = 0
            self.in_recovery = False
            self.frozen = False
            self.frozen_at_beta = 0.0

            # Pre-compute base schedule
            phase1_end = min(40, n_iters)
            phase2_end = min(80, n_iters)
            phase3_end = min(120, n_iters)

            self.beta_schedule = np.zeros(n_iters)
            if phase1_end > 0:
                self.beta_schedule[:phase1_end] = 2.0
            if phase2_end > phase1_end:
                self.beta_schedule[phase1_end:phase2_end] = np.linspace(2, 16, phase2_end - phase1_end)
            if phase3_end > phase2_end:
                self.beta_schedule[phase2_end:phase3_end] = np.linspace(16, 32, phase3_end - phase2_end)
            if n_iters > phase3_end:
                self.beta_schedule[phase3_end:] = 64.0

        def get_beta(self, iteration: int, current_fom: float) -> float:
            """Get beta for current iteration based on FOM history."""
            target_beta = self.beta_schedule[iteration - 1]  # iteration is 1-indexed

            # First iteration - just set initial values
            if iteration == 1:
                self.current_beta = target_beta
                self.fom_before_increase = current_fom
                return self.current_beta

            # Track best FOM during recovery period
            if self.in_recovery:
                self.best_fom_during_recovery = max(self.best_fom_during_recovery, current_fom)
                self.iters_since_increase += 1

                # Check if recovery period ended
                if self.iters_since_increase >= self.recovery_iters:
                    self.in_recovery = False
                    # Did we recover enough?
                    if self.best_fom_during_recovery < self.fom_before_increase * self.recovery_threshold:
                        # Failed to recover - freeze at current beta
                        self.frozen = True
                        self.frozen_at_beta = self.current_beta
                    else:
                        # Recovered successfully - can continue increasing
                        self.fom_before_increase = self.best_fom_during_recovery

            # If frozen, check if we should unfreeze
            if self.frozen:
                # Unfreeze if FOM exceeds the pre-freeze level
                if current_fom >= self.fom_before_increase * 0.98:
                    self.frozen = False
                    self.fom_before_increase = current_fom

            # Target beta wants to increase
            if target_beta > self.current_beta + 0.01:
                if self.frozen:
                    # Stay at frozen beta
                    return self.current_beta
                else:
                    # Allow increase and start recovery period
                    self.fom_before_increase = current_fom
                    self.current_beta = target_beta
                    self.in_recovery = True
                    self.iters_since_increase = 0
                    self.best_fom_during_recovery = current_fom
                    return self.current_beta

            return self.current_beta

        def get_status(self) -> str:
            """Get human-readable status string."""
            if self.frozen:
                return f"FROZEN@β={self.frozen_at_beta:.1f}"
            if self.in_recovery:
                return f"RECOVERING({self.iters_since_increase}/{self.recovery_iters})"
            return "NORMAL"
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
