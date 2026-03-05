#!/usr/bin/env python3
"""
Pattern: save_density_plot
Design density plot: gray_r colormap (0=SiO2/white, 1=Si/black), with FOM/binarization annotation
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "save_density_plot"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def save_density_plot(flat: np.ndarray, nx: int, ny: int,
                          design_length: float, out_path: Path,
                          title: str, fom: float | None = None,
                          binarization: float | None = None,
                          filter_radius_um: float | None = None) -> None:
        """Save design density plot with metrics annotation."""
        density = flat.reshape((nx, ny)).T
        extent = [0, design_length, -DESIGN_HEIGHT / 2, DESIGN_HEIGHT / 2]

        aspect_ratio = DESIGN_HEIGHT / design_length
        fig_width = 4
        fig_height = fig_width * aspect_ratio + 1
        plt.figure(figsize=(fig_width, fig_height))

        # 0=white(SiO2), 1=black(Si) -> gray_r
        plt.imshow(density, origin="lower", cmap="gray_r", vmin=0, vmax=1,
                   extent=extent, aspect="equal")
        plt.colorbar(label="Density (0=SiO2/white, 1=Si/black)")
        plt.xlabel("x (µm)")
        plt.ylabel("y (µm)")

        # Title with metrics
        full_title = title
        if fom is not None or binarization is not None:
            info_parts = []
            if fom is not None:
                info_parts.append(f"FOM={fom:.4f}")
            if binarization is not None:
                info_parts.append(f"Bin={binarization:.3f}")
            full_title = f"{title}\n{', '.join(info_parts)}"
        plt.title(full_title)
        plt.tight_layout()
        plt.savefig(out_path, dpi=200)
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
