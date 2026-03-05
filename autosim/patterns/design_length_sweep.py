#!/usr/bin/env python3
"""
Pattern: design_length_sweep
Sweep over design region lengths (5-10um) to find minimum length achieving target FOM. Design height fixed at 13um (= in
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "design_length_sweep"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # Design region: height FIXED, length SWEPT
    design_region_height  = 13.0   # um (fixed = input_width + 1)
    design_region_lengths = [5.0, 6.0, 7.0, 8.0, 9.0, 10.0]  # um

    sweep_results = {}

    for design_length in design_region_lengths:
        print(f"Running length={design_length:.0f}um")
        result_dir = f"results/length_{design_length:.0f}um"
        os.makedirs(result_dir, exist_ok=True)

        # final_fom, final_bin = run_optimization(design_length, result_dir)
        # sweep_results[design_length] = {"fom": final_fom, "binarization": final_bin}

    def plot_sweep_comparison(sweep_results: dict, output_path: str) -> float:
        # Plot FOM vs design length and return optimal length.
        lengths = sorted(sweep_results.keys())
        foms    = [sweep_results[l]["fom"] for l in lengths]
        bins    = [sweep_results[l]["binarization"] for l in lengths]

        fig, ax1 = plt.subplots(figsize=(10, 6))
        color1 = 'tab:blue'
        ax1.set_xlabel('Design Length (um)')
        ax1.set_ylabel('Final FOM (TE1 Transmission)', color=color1)
        ax1.plot(lengths, foms, 'o-', color=color1, linewidth=2, markersize=8)
        ax1.axhline(y=0.90, color='green', linestyle='--', alpha=0.7,
                    label='Target FOM = 0.90')
        ax1.tick_params(axis='y', labelcolor=color1)
        ax1.set_ylim([0, 1])

        ax2 = ax1.twinx()
        color2 = 'tab:red'
        ax2.set_ylabel('Binarization', color=color2)
        ax2.plot(lengths, bins, 's--', color=color2, linewidth=1.5, markersize=6)
        ax2.tick_params(axis='y', labelcolor=color2)
        ax2.set_ylim([0, 1])

        ax1.legend(loc='lower right')
        plt.title('Design Length Sweep: FOM vs Length')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()

        # Select shortest length achieving target
        optimal = next((l for l in lengths if sweep_results[l]["fom"] > 0.90), lengths[-1])
        print(f"Optimal: {optimal:.0f} um (FOM={sweep_results[optimal]['fom']:.3f})")
        return optimal
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
