#!/usr/bin/env python3
"""
Pattern: pipeline_cat6_output_results
[Category 6: 결과물 출력] 수렴 플롯 + 결과 저장 + 최종 검증 시뮬레이션.
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "pipeline_cat6_output_results"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    import time

    # ── 수렴 히스토리 저장 ────────────────────────────────────────────────────
    def save_history(fom_history, grad_norm_history, beta_history, output_dir):
        if mp.am_master():
            history = {
                "fom":       fom_history,
                "grad_norm": grad_norm_history,
                "beta":      beta_history,
                "n_iter":    len(fom_history),
                "best_fom":  max(fom_history) if fom_history else 0,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(Path(output_dir) / "history.json", "w") as f:
                json.dump(history, f, indent=2)
            print(f"[Cat.6] Saved: {output_dir}/history.json")

    # ── 수렴 플롯 ─────────────────────────────────────────────────────────────
    def plot_convergence(fom_history, beta_history, output_dir):
        if mp.am_master():
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

            ax1.plot(fom_history, "b-o", markersize=3, label="FOM")
            ax1.set_ylabel("FOM (Transmission)")
            ax1.set_ylim(0, 1.05)
            ax1.legend(); ax1.grid(True, alpha=0.3)
            ax1.set_title("Convergence")

            ax2.semilogy(beta_history, "r-s", markersize=3, label="Beta")
            ax2.set_ylabel("Beta (log scale)")
            ax2.set_xlabel("Iteration")
            ax2.legend(); ax2.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(Path(output_dir) / "convergence.png", dpi=150, bbox_inches="tight")
            plt.close()
            print(f"[Cat.6] Saved: {output_dir}/convergence.png")

    # ── results.txt summary ───────────────────────────────────────────────────
    def save_results_summary(fom_history, x_final, output_dir, resolution, n_iter):
        if mp.am_master():
            binary_ratio = np.mean(np.abs(x_final - 0.5) > 0.4)
            lines = [
                "=== Inverse Design Results Summary ===",
                f"Final FOM:     {fom_history[-1]:.6f}",
                f"Best FOM:      {max(fom_history):.6f}",
                f"Binary ratio:  {binary_ratio:.1%}",
                f"Iterations:    {n_iter}",
                f"Resolution:    {resolution} px/μm",
                f"Design params: {len(x_final)} ({Nx}×{Ny})",
                f"Timestamp:     {time.strftime('%Y-%m-%d %H:%M:%S')}",
            ]
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
