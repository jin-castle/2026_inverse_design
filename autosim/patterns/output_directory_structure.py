#!/usr/bin/env python3
"""
Pattern: output_directory_structure
Standard output directory structure for MEEP inverse design projects. Root: results_stage1_grayscale/{timestamp_dir}/. S
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "output_directory_structure"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    from datetime import datetime

    def create_output_dirs(project_name: str, design_length: float,
                           base_dir: Path = Path("results_stage1")) -> dict:
        """Create standard output directory structure for inverse design.
    
        Returns dict of Path objects for each subdirectory.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = base_dir / f"L{design_length:.1f}um_{timestamp}"

        dirs = {
            "root":             run_dir,
            "design_iters":     run_dir / "design_iterations",
            "validation":       run_dir / "validation",
            "fields":           run_dir / "validation" / "fields",
            "mode_decomp":      run_dir / "validation" / "mode_decomposition",
            "mode_profiles":    run_dir / "validation" / "mode_profiles",
        }

        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)

        return dirs

    # Standard file naming convention:
    # dirs["root"]        / "initial_layout.png"
    # dirs["root"]        / "final_structure.png"
    # dirs["root"]        / "convergence.png"
    # dirs["root"]        / "history.json"
    # dirs["root"]        / "history.npy"
    # dirs["root"]        / "results.txt"
    # dirs["root"]        / "config.json"
    # dirs["root"]        / "best_design.npy"
    # dirs["root"]        / "final_design.npy"
    # dirs["design_iters"]/ f"design_iter{i:03d}.png"
    # dirs["validation"]  / "field_propagation.mp4"
    # dirs["validation"]  / "mode_purity.png"
    # dirs["validation"]  / "dft_fields_all.png"     # 6-panel (2D) or 9-panel (3D)
    # dirs["fields"]      / "field_Ey.png"           # individual component
    # dirs["mode_decomp"] / "mode_decomposition.json"
    # dirs["mode_profiles"]/ "dft_input_mode_profile.png"

    # 3D DFT fields_all: 9-panel (Ex,Ey,Ez / Hx,Hy,Hz / Px,Py,Pz)
    # 2D DFT fields_all: 6-panel (Re(Ez),Re(Hx),Re(Hy) / |Px|,|Py|,|Pz|)
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
