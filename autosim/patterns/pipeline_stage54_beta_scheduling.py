#!/usr/bin/env python3
"""
Pattern: pipeline_stage54_beta_scheduling
[Stage 5-4: Beta Scheduling] Tanh projection + beta continuation 스케줄.
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "pipeline_stage54_beta_scheduling"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    from meep.adjoint import utils as mpa_utils

    # ── Tanh projection 함수 ──────────────────────────────────────────────────
    def tanh_projection(x, beta, eta=0.5):
        # Heaviside tanh projection for binarization
        return (npa.tanh(beta * eta) + npa.tanh(beta * (x - eta))) /            (npa.tanh(beta * eta) + npa.tanh(beta * (1 - eta)))

    # ── Beta schedule ─────────────────────────────────────────────────────────
    beta_start  = 2.0
    beta_max    = 128.0
    beta_update_freq = 10   # 매 N iteration마다 beta 2배

    def get_beta(iteration):
        # iteration -> beta 값 반환
        doublings = iteration // beta_update_freq
        beta = beta_start * (2 ** doublings)
        return min(beta, beta_max)

    # ── 최적화 루프 내 beta 적용 예시 ─────────────────────────────────────────
    n_iter = 100
    x      = x0.copy()

    for i in range(n_iter):
        beta = get_beta(i)

        # Projected design variable (beta projection 적용 후)
        x_projected = tanh_projection(x, beta, eta=0.5)

        # opt에 현재 beta를 반영하여 실행
        # (opt의 design_region에 projection 함수를 등록한 경우)
        fom, grad = opt([x_projected])

        # gradient도 projection chain rule 적용
        # grad_projected = grad * d(tanh_proj)/dx
        chain = beta * (1 - npa.tanh(beta * (x - 0.5)) ** 2) /             (npa.tanh(beta * 0.5) + npa.tanh(beta * 0.5))
        grad_effective = grad[0] * chain

        if mp.am_master():
            print(f"[Stage 5-4] iter={i:03d}  beta={beta:.1f}  FOM={fom[0]:.6f}")

        # gradient descent step (scipy optimizer 사용 시 optimizer.tell(x, -fom, -grad) 형태)
        x = np.clip(x + 0.01 * grad_effective, 0, 1)   # 단순 gradient ascent 예시

    mp.all_wait()
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
