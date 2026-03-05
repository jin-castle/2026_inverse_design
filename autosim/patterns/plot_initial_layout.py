#!/usr/bin/env python3
"""
Pattern: plot_initial_layout
Initial layout visualization: Save source/monitor/design region locations as annotated plot
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "plot_initial_layout"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def plot_initial_layout(sim, layout: dict, output_dir: Path):
        """Save initial layout with source/monitor annotations."""
        fig, ax = plt.subplots(figsize=(12, 6))
        sim.plot2D(ax=ax)

        # Source position
        ax.axvline(x=layout["source_x"], color='red', linestyle='--', linewidth=2, label='Source')

        # Output monitor position
        ax.axvline(x=layout["output_monitor_x"], color='blue', linestyle='--', linewidth=2, label='Output Monitor')

        # Design region
        rect = patches.Rectangle(
            (layout["design_start"], -DESIGN_HEIGHT / 2),
            layout["design_length"],
            DESIGN_HEIGHT,
            fill=False, edgecolor='green', linewidth=3, linestyle='--',
            label='Design Region'
        )
        ax.add_patch(rect)

        ax.legend(loc='upper right')
        ax.set_title(f'Initial Layout (L={layout["design_length"]:.1f} µm)')
        ax.set_xlabel('x (µm)')
        ax.set_ylabel('y (µm)')
        plt.tight_layout()
        plt.savefig(output_dir / 'initial_layout.png', dpi=150, bbox_inches='tight')
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
