#!/usr/bin/env python3
"""
Pattern: BacktrackingLineSearch
Armijo condition-based backtracking: maximum 6 iterations, upscaling (×10) upon failure
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "BacktrackingLineSearch"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    class BacktrackingLineSearch:
        """Armijo condition based backtracking line search.

        msopt/Opt_MS2.py Inner_iter 로직 포팅.

        Armijo condition: f_new >= f_old + c * alpha * grad_sufficient
        - 만족하지 않으면 alpha *= 0.1 로 감소
        - 최대 bt_tol회까지 시도
        - 그래도 실패하면 upscaling (alpha *= 10) 시도
        """

        def __init__(
            self,
            bt_tol: int = 6,           # 최대 backtracking 횟수
            alpha_scale: float = 0.1,  # LR 감소 비율
            armijo_c: float = 1.0,     # Armijo 상수 (normalized by n_pixels)
        ):
            self.bt_tol = bt_tol
            self.initial_alpha_scale = alpha_scale
            self.armijo_c = armijo_c
            self.bt_max_count = 0      # Full backtracking 발생 횟수

        def compute_armijo_condition(
            self,
            f_old: float,
            alpha: float,
            grad_sufficient: float,
            n_pixels: int
        ) -> float:
            """Compute Armijo sufficient decrease condition.

            Armijo_cond = f_old + (armijo_c / n_pixels) * alpha * grad_sufficient

            FOM이 이 값보다 크거나 같아야 "충분한 개선"으로 인정.
            """
            return f_old + (self.armijo_c / n_pixels) * alpha * grad_sufficient

        def compute_grad_sufficient(
            self,
            design: np.ndarray,
            gradient: np.ndarray
        ) -> float:
            """Compute gradient sufficiency measure.

            Gray 영역 (0 < design < 1)에서의 gradient 크기 합.
            Binary 영역에서는 gradient가 영향을 미치지 않으므로 제외.
            """
            design_flat = design.flatten()
            grad_flat = gradient.flatten()

            # Gray 영역 마스크 (0.01 < design < 0.99)
            gray_mask = (design_flat > 0.01) & (design_flat < 0.99)

            return float(np.sum(np.abs(grad_flat[gray_mask])))

        def search(
            self,
            f_old: float,
            f_new: float,
            alpha: float,
            design: np.ndarray,
            gradient: np.ndarray,
            forward_func,  # callable(design) -> fom
            update_func,   # callable(design, gradient, alpha) -> new_design
            grad_sufficient: float = None,
        ) -> BacktrackingResult:
            """Perform backtracking line search.

            Args:
                f_old: Previous FOM
                f_new: Current FOM after update
                alpha: Current learning rate
                design: Current design vector (before update)
                gradient: Current gradient
                forward_func: Function to compute FOM given design
                update_func: Function to update design given alpha
                grad_sufficient: Pre-computed gradient sufficiency (optional)

            Returns:
                BacktrackingResult with best alpha and FOM
            """
            n_pixels = len(design.flatten())

            if grad_sufficient is None:
                grad_sufficient = self.compute_grad_sufficient(design, gradient)

            armijo = self.compute_armijo_condition(f_old, alpha, grad_sufficient, n_pixels)

            # No backtracking needed
            if f_new >= armijo:
                return BacktrackingResult(
                    success=True,
                    alpha=alpha,
                    fom=f_new,
                    num_evals=0,
                    upscaled=False,
                )

            # Backtracking loop
            fom_history = [f_new]
            alpha_history = [alpha]
            alpha_scale = self.initial_alpha_scale
            upscaled = False

            for bt_cnt in range(1, self.bt_tol):
                alpha *= alpha_scale
                new_design = update_func(design, gradient, alpha)
                f_bt = forward_func(new_design)

                fom_history.append(f_bt)
                alpha_history.append(alpha)

                armijo = self.compute_armijo_condition(f_old, alpha, grad_sufficient, n_pixels)

                if f_bt >= armijo:
                    # Success
                    return BacktrackingResult(
                        success=True,
                        alpha=alpha,
                        fom=f_bt,
                        num_evals=bt_cnt,
                        upscaled=upscaled,
                        best_idx=bt_cnt,
                    )

                # Check if FOM is improving (current vs previous)
                if bt_cnt >= 2 and fom_history[-1] <= fom_history[-2]:
                    # FOM not improving, check if we should try upscaling
                    if alpha_scale < 1.0 and not upscaled:
                        # Reset and try upscaling
                        alpha = alpha_history[0]  # Reset to original alpha
                        alpha_scale = 1.0 / self.initial_alpha_scale  # 10x upscale
                        upscaled = True
                        continue
                    else:
                        # Upscaling also failed or already tried, return best found
                        best_idx = int(np.argmax(fom_history))
                        return BacktrackingResult(
                            success=False,
                            alpha=alpha_history[best_idx],
                            fom=fom_history[best_idx],
                            num_evals=bt_cnt,
                            upscaled=upscaled,
                            best_idx=best_idx,
                        )

            # Full backtracking reached
            self.bt_max_count += 1
            best_idx = int(np.argmax(fom_history))
            return BacktrackingResult(
                success=False,
                alpha=alpha_history[best_idx],
                fom=fom_history[best_idx],
                num_evals=self.bt_tol,
                upscaled=upscaled,
                best_idx=best_idx,
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
