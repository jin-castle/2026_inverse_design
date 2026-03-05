#!/usr/bin/env python3
"""
Pattern: WarmRestarter
msopt WarmRestart: Escape local minima by LR×5 (or ×20) when no improvement occurs for 3 iterations
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "WarmRestarter"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    class WarmRestarter:
        """msopt Warm Restart 메커니즘.

        3회 이상 FOM 개선 없으면 Learning Rate를 증가시켜 local minima 탈출.

        msopt 원본 (Opt_MS2.py:286-305):
        - no_improvement_count == 3 → LR *= 5 (or 20)
        - momentum 초기화
        - local best 저장
        """

        def __init__(
            self,
            improvement_threshold: float = 0.01,
            max_count: int = 3,
            lr_scale_high: float = 5.0,
            lr_scale_low: float = 20.0,
            lr_threshold: float = 0.0001,
            max_lr: float = 1.0,
        ):
            """Initialize WarmRestarter.

            Args:
                improvement_threshold: 개선으로 인정할 최소 비율 (default 1%)
                max_count: WR 발동까지 허용할 무개선 횟수 (default 3)
                lr_scale_high: LR > threshold일 때 증가 배율 (default 5x)
                lr_scale_low: LR <= threshold일 때 증가 배율 (default 20x)
                lr_threshold: 배율 결정 기준 (default 0.0001)
                max_lr: LR 상한 (default 1.0, 이 이상으로 증가하지 않음)
            """
            self.improvement_threshold = improvement_threshold
            self.max_count = max_count
            self.lr_scale_high = lr_scale_high
            self.lr_scale_low = lr_scale_low
            self.lr_threshold = lr_threshold
            self.max_lr = max_lr

            # State
            self.best_fom = 0.0
            self.no_improvement_count = 0
            self.wr_count = 0  # 총 WR 발동 횟수
            self.history = []  # WR 발동 기록

        def check(
            self,
            current_fom: float,
            current_lr: float,
            iteration: int = 0,
        ) -> Tuple[float, bool]:
            """WR 조건 확인 및 LR 조정.

            Args:
                current_fom: 현재 FOM
                current_lr: 현재 Learning Rate
                iteration: 현재 iteration (로깅용)

            Returns:
                (new_lr, warm_restart_triggered)
            """
            # FOM 개선 체크 (상대적 개선율 기준)
            improvement_ratio = (current_fom - self.best_fom) / (self.best_fom + 1e-8)

            if current_fom > self.best_fom:
                if improvement_ratio > self.improvement_threshold:
                    # 유의미한 개선
                    self.best_fom = current_fom
                    self.no_improvement_count = 0
                    return current_lr, False
                else:
                    # 작은 개선 (< 1%) - 카운트만 줄임
                    self.best_fom = current_fom
                    self.no_improvement_count = max(0, self.no_improvement_count - 1)
                    return current_lr, False

            # 개선 없음
            self.no_improvement_count += 1

            if self.no_improvement_count >= self.max_count:
                # Warm Restart 발동
                if current_lr > self.lr_threshold:
                    new_lr = current_lr * self.lr_scale_high
                else:
                    new_lr = current_lr * self.lr_scale_low

                # LR 상한 적용 (폭주 방지)
                new_lr = min(new_lr, self.max_lr)

                self.no_improvement_count = 0
                self.wr_count += 1
                self.history.append({
                    "iteration": iteration,
                    "old_lr": current_lr,
                    "new_lr": new_lr,
                    "fom": current_fom,
                })

                return new_lr, True

            return current_lr, False

        def reset(self):
            """State 초기화."""
            self.best_fom = 0.0
            self.no_improvement_count = 0
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
