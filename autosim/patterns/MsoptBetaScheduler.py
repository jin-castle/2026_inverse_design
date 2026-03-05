#!/usr/bin/env python3
"""
Pattern: MsoptBetaScheduler
msopt convergence detection beta scheduler: if bin>=0.8 then 150% increase else 200%. Includes re-roll.
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "MsoptBetaScheduler"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    class MsoptBetaScheduler:
        """msopt Opt_MS2.py 기반 Beta 스케줄러.

        특징:
        1. 수렴 감지 기반 Beta 증가 (고정 스케줄 대신)
        2. Binarization 수준에 따른 증가율 조절
        3. FOM 급락 시 Re-roll (작은 step으로 재시도)
        4. 조기 종료 조건 지원

        msopt 핵심 로직:
        - is_converged: FOM 변화율 < threshold
        - binarization >= 0.8: beta *= 1.5 (50% 증가)
        - binarization < 0.8: beta *= 2.0 (100% 증가)
        - FOM < best * 0.9: Re-roll (scale *= 0.1)
        """

        def __init__(
            self,
            beta_init: float = 2.0,
            beta_final: float = 128.0,
            convergence_window: int = 5,
            convergence_threshold: float = 5e-4,
            beta_scale_high_bin: float = 0.5,  # bin >= 0.8: 150% 증가
            beta_scale_low_bin: float = 1.0,   # bin < 0.8: 200% 증가
            fom_drop_threshold: float = 0.1,   # 10% drop → Re-roll
            max_reroll_count: int = 3,
            min_beta_for_exit: float = 48.0,
            target_binarization: float = 0.99,
            target_fom: float = 0.95,
        ):
            self.beta = beta_init
            self.beta_init = beta_init
            self.beta_final = beta_final
            self.convergence_window = convergence_window
            self.convergence_threshold = convergence_threshold
            self.beta_scale_high_bin = beta_scale_high_bin
            self.beta_scale_low_bin = beta_scale_low_bin
            self.fom_drop_threshold = fom_drop_threshold
            self.max_reroll_count = max_reroll_count
            self.min_beta_for_exit = min_beta_for_exit
            self.target_binarization = target_binarization
            self.target_fom = target_fom

            # 상태 변수
            self.best_fom = 0.0
            self.reroll_count = 0
            self.fom_history = []
            self.beta_history = []
            self.last_beta_increase_iter = 0
            self.phase1_complete = False

        def reset(self):
            """스케줄러 상태 초기화."""
            self.beta = self.beta_init
            self.best_fom = 0.0
            self.reroll_count = 0
            self.fom_history = []
            self.beta_history = []
            self.last_beta_increase_iter = 0
            self.phase1_complete = False

        def is_converged(self) -> bool:
            """FOM 수렴 여부 판단.

            최근 window 내 FOM 변화율이 threshold 미만이면 수렴으로 판단.
            """
            if len(self.fom_history) < self.convergence_window:
                return False

            recent = self.fom_history[-self.convergence_window:]
            mean_fom = np.mean(recent)

            if mean_fom < 1e-8:
                return False

            # 변화율 = std / mean
            variation = np.std(recent) / mean_fom
            return variation < self.convergence_threshold

        def should_exit_early(self, binarization: float, fom: float) -> bool:
            """조기 종료 조건 확인.

            조건:
            1. Beta >= min_beta_for_exit
            2. Binarization >= target_binarization
            3. FOM >= target_fom (선택적)
            """
            if self.beta < self.min_beta_for_exit:
                return False

            if binarization < self.target_binarization:
                return False

            if fom < self.target_fom:
                return False

            return True

        def update(
            self,
            iteration: int,
            fom: float,
            binarization: float,
            phase1_ratio: float = 0.25,
            max_iterations: int = 300,
        ) -> tuple:
            """Beta 업데이트 및 상태 관리.

            Args:
                iteration: 현재 iteration (1-indexed)
                fom: 현재 FOM
                binarization: 현재 binarization
                phase1_ratio: Phase 1 비율 (beta 고정 기간)
                max_iterations: 최대 iteration

            Returns:
                (new_beta, should_exit, status_msg)
            """
            self.fom_history.append(fom)
            self.best_fom = max(self.best_fom, fom)

            status_msg = ""

            # Phase 1: Beta 고정 (FOM 탐색)
            phase1_end = int(max_iterations * phase1_ratio)
            if iteration <= phase1_end:
                self.beta_history.append(self.beta)
                return self.beta, False, "Phase1: β fixed for FOM exploration"

            if not self.phase1_complete:
                self.phase1_complete = True
                status_msg = "Phase1 complete. Starting adaptive β schedule."

            # 조기 종료 확인
            if self.should_exit_early(binarization, fom):
                return self.beta, True, f"Early exit: bin={binarization:.3f}, FOM={fom:.4f}"

            # 수렴 감지
            if not self.is_converged():
                self.beta_history.append(self.beta)
                return self.beta, False, status_msg or "Waiting for convergence..."

            # FOM 급락 체크 (Re-roll)
            if fom < self.best_fom * (1 - self.fom_drop_threshold):
                self.reroll_count += 1
                if self.reroll_count <= self.max_reroll_count:
                    # Re-roll: 작은 증가로 재시도
                    scale = 0.1  # 10% 증가만
                    old_beta = self.beta
                    self.beta = min(self.beta * (1.0 + scale), self.beta_final)
                    self.fom_history = []  # Reset history
                    status_msg = f"Re-roll #{self.reroll_count}: β {old_beta:.1f}→{self.beta:.1f} (10% only)"
                    self.beta_history.append(self.beta)
                    return self.beta, False, status_msg
            else:
                self.reroll_count = 0  # Reset reroll counter

            # Beta 증가 (수렴 + FOM 안정)
            if binarization >= 0.8:
                scale = self.beta_scale_high_bin  # 50% 증가
            else:
                scale = self.beta_scale_low_bin   # 100% 증가

            old_beta = self.beta
            self.beta = min(self.beta * (1.0 + scale), self.beta_final)
            self.fom_history = []  # Reset for next convergence check
            self.last_beta_increase_iter = iteration

            status_msg = f"Converged! β {old_beta:.1f}→{self.beta:.1f} (scale={scale:.0%})"
            self.beta_history.append(self.beta)

            return self.beta, False, status_msg

        def get_state_dict(self) -> dict:
            """현재 상태를 딕셔너리로 반환 (저장용)."""
    # ... (truncated)
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
