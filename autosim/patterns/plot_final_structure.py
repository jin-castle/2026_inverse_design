#!/usr/bin/env python3
"""
Pattern: plot_final_structure
Final design structure 2-panel: (1) grayscale density, (2) binarized (threshold=0.5)
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "plot_final_structure"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def plot_final_structure(design_vector: np.ndarray, nx: int, ny: int,
                             design_length: float, output_dir: Path):
        """Save final structure with grayscale and binarized views."""
        density = design_vector.reshape((nx, ny)).T
        binary = (density > 0.5).astype(float)
        extent = [0, design_length, -DESIGN_HEIGHT / 2, DESIGN_HEIGHT / 2]

        fig, axes = plt.subplots(1, 2, figsize=(12, 8))

        # Grayscale
        im0 = axes[0].imshow(density, origin='lower', cmap='gray_r', vmin=0, vmax=1,
                              extent=extent, aspect='equal')
        axes[0].set_title('Final Design (Grayscale)')
        axes[0].set_xlabel('x (µm)')
        axes[0].set_ylabel('y (µm)')
        plt.colorbar(im0, ax=axes[0], label='Density')

        # Binarized (threshold=0.5)
        im1 = axes[1].imshow(binary, origin='lower', cmap='gray_r', vmin=0, vmax=1,
                              extent=extent, aspect='equal')
        axes[1].set_title('Final Design (Binarized, threshold=0.5)')
        axes[1].set_xlabel('x (µm)')
        axes[1].set_ylabel('y (µm)')
        plt.colorbar(im1, ax=axes[1], label='Density')

        plt.tight_layout()
        plt.savefig(output_dir / 'final_structure.png', dpi=150, bbox_inches='tight')
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
