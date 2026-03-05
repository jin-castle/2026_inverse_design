#!/usr/bin/env python3
"""
Pattern: get_beta_schedule_4phase
4-phase beta schedule: iter 1-20 maintain beta=2.0 → iter 21-50 linear 2→32 → iter 51-70 linear 32→64 → iter 71+ beta=12
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "get_beta_schedule_4phase"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def get_beta_schedule(n_iters: int) -> np.ndarray:
        """
        Multi-phase beta schedule for gradual binarization.

        Phase 1 (iter 1-20):  beta 2 (hold) - initial exploration
        Phase 2 (iter 21-50): beta 2→32 (gradual increase)
        Phase 3 (iter 51-70): beta 32→64 (moderate increase)
        Phase 4 (iter 71+):   beta 128 (hold for final binarization)
        """
        phase1_end = min(20, n_iters)
        phase2_end = min(50, n_iters)
        phase3_end = min(70, n_iters)

        beta_schedule = np.zeros(n_iters)
        if phase1_end > 0:
            beta_schedule[:phase1_end] = 2.0
        if phase2_end > phase1_end:
            beta_schedule[phase1_end:phase2_end] = np.linspace(2, 32, phase2_end - phase1_end)
        if phase3_end > phase2_end:
            beta_schedule[phase2_end:phase3_end] = np.linspace(32, 64, phase3_end - phase2_end)
        if n_iters > phase3_end:
            beta_schedule[phase3_end:] = 128.0

        return beta_schedule
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
