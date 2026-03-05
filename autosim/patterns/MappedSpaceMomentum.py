#!/usr/bin/env python3
"""
Pattern: MappedSpaceMomentum
msopt source Momentum: design space transformation to TJP after Adam in mapped space. bt1=0.9
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "MappedSpaceMomentum"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    class MappedSpaceMomentum:
        """msopt Opt_MS2.py Momentum 함수를 클래스로 재현.

        msopt 원본과의 핵심 차이:
        - Adam momentum을 **mapped (물리) 공간**에서 적용
        - TJP 전에 gradient를 스무딩 → β 전환 시 안정성 확보
        - design 공간에서는 단순 α × gradient step만 수행

        msopt 원본 flow:
            raw_gradient → Born_validity → Momentum(Adam) → TJP → α×gradient step

        파라미터 (msopt 원본):
        - beta1 = 0.9 (N_grad=9, bt1=N_grad/10)
        - beta2 = 0.99 ((1-bt1)^2 = 0.01 → 1-0.01=0.99)
        - 1st moment bias correction: 없음
        - 2nd moment bias correction: bt1^(numevl+1) 사용 (비표준)

        Usage:
            momentum = MappedSpaceMomentum(mapped_size)
            # 매 iteration:
            g_m = momentum.apply(grad_mapped)  # mapped 공간에서 Adam
            grad_design = TJP(mapping, 0)(design, beta, g_m)  # design 공간으로
            design = clip(design + lr * grad_design, 0, 1)  # 단순 step
        """

        def __init__(self, size: int, beta1: float = 0.9):
            """Initialize MappedSpaceMomentum.

            Args:
                size: Mapped design vector 크기 (nx * ny)
                beta1: 1st moment EMA 계수 (msopt 기본값 0.9)
            """
            self.beta1 = beta1
            self.m = np.zeros(size)       # 1st moment (grad_adj in msopt)
            self.v = np.zeros(size)       # 2nd moment (RMSprop in msopt)
            self.t = 0                    # numevl in msopt

        def apply(self, grad: np.ndarray) -> np.ndarray:
            """Mapped 공간에서 Adam momentum 적용.

            msopt Momentum() 함수와 동일한 계산:
                grad_adj = bt1 * dF_old + (1-bt1) * dF_cur
                RMSprop = (1-(1-bt1)^2) * dF_old2 + (1-bt1)^2 * dF_cur^2
                Bias_corr = RMSprop / (1 - bt1^(numevl+1))
                grad_prop = grad_adj / (sqrt(Bias_corr) + 1e-8)

            Args:
                grad: Mapped 공간 gradient (adjoint에서 직접 나온 gradient)

            Returns:
                g_m: Momentum 적용된 gradient (TJP에 넣을 값)
            """
            bt1 = self.beta1
            bt2 = (1 - bt1) ** 2  # msopt: 0.01 (beta2 = 1 - bt2 = 0.99)

            # 1st moment (no bias correction — msopt 원본)
            self.m = bt1 * self.m + (1 - bt1) * grad

            # 2nd moment (beta2 = 0.99)
            self.v = (1 - bt2) * self.v + bt2 * (grad ** 2)

            # Bias correction (msopt 비표준: bt1^(t+1) 사용)
            self.t += 1
            bias_corr = self.v / (1 - bt1 ** self.t + 1e-12)

            # Normalized gradient
            g_m = self.m / (np.sqrt(bias_corr) + 1e-8)

            return g_m

        def reset(self):
            """Momentum 상태 초기화."""
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
