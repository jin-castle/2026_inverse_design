#!/usr/bin/env python3
"""
Pattern: plot_convergence_4panel
4-panel convergence monitoring plot for adjoint optimization. Panel 1: FOM vs iteration. Panel 2: binarization metric vs
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "plot_convergence_4panel"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def plot_convergence(history: dict, output_dir: Path, title: str = "Optimization"):
        """Generate 4-panel convergence plot."""
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        iters = list(range(1, len(history["fom"]) + 1))

        # FOM vs iteration
        ax = axes[0, 0]
        ax.plot(iters, history["fom"], 'b-', linewidth=2)
        ax.axhline(y=history["best_fom"], color='g', linestyle='--', alpha=0.7,
                   label=f'Best: {history["best_fom"]:.4f}')
        ax.set_xlabel('Iteration')
        ax.set_ylabel('FOM')
        ax.set_title('Figure of Merit (FOM)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_ylim([0, 1])

        # Binarization vs iteration
        ax = axes[0, 1]
        ax.plot(iters, history["binarization"], 'r-', linewidth=2)
        ax.set_xlabel('Iteration')
        ax.set_ylabel('Binarization')
        ax.set_title('Binarization Metric')
        ax.grid(True, alpha=0.3)
        ax.set_ylim([0, 1])

        # Gradient norm vs iteration (log scale)
        ax = axes[1, 0]
        if history.get("gradient_norm"):
            ax.semilogy(iters, history["gradient_norm"], 'g-', linewidth=2)
        ax.set_xlabel('Iteration')
        ax.set_ylabel('Gradient Norm (log)')
        ax.set_title('Gradient Norm')
        ax.grid(True, alpha=0.3)

        # Beta vs iteration
        ax = axes[1, 1]
        ax.plot(iters, history["beta"], 'm-', linewidth=2)
        ax.set_xlabel('Iteration')
        ax.set_ylabel('Beta')
        ax.set_title('Beta Schedule')
        ax.grid(True, alpha=0.3)

        fig.suptitle(title, fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig(output_dir / 'convergence.png', dpi=150, bbox_inches='tight')
        plt.close()
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
