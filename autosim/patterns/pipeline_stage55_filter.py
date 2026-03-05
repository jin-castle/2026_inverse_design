#!/usr/bin/env python3
"""
Pattern: pipeline_stage55_filter
[Stage 5-5: Filter] Conic filter + fabrication constraint 적용.
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "pipeline_stage55_filter"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    from meep.adjoint import utils as mpa_utils

    # ── Conic Filter 설정 ─────────────────────────────────────────────────────
    # minimum feature size: 100 nm = 0.1 μm
    min_feature_um = 0.1
    design_grid_um = 1.0 / resolution    # 1/50 = 0.02 μm/pixel
    r_pixels = min_feature_um / design_grid_um / 2   # ≈ 2.5 pixels

    def apply_conic_filter(x, Nx, Ny, r):
        # Conic filter for minimum length scale (meep.adjoint.utils 사용)
        x_2d = x.reshape(Nx, Ny)
        x_filtered_2d = mpa_utils.conic_filter(
            x_2d,
            radius=r,
            Lx=design_len,   # μm
            Ly=design_wid,   # μm
            resolution=resolution,
        )
        return x_filtered_2d.flatten()

    def apply_gaussian_filter(x, Nx, Ny, sigma):
        # Gaussian filter (대안)
        from scipy.ndimage import gaussian_filter
        x_2d = x.reshape(Nx, Ny)
        x_filtered_2d = gaussian_filter(x_2d, sigma=sigma)
        return np.clip(x_filtered_2d.flatten(), 0, 1)

    # ── Filter + Projection 파이프라인 ────────────────────────────────────────
    def forward_pass(x, beta, eta=0.5):
        # Filter -> Projection 순서 적용 후 opt에 전달
        # Step 1: Conic filter (fabrication constraint)
        x_filt = apply_conic_filter(x, Nx, Ny, r_pixels)
        # Step 2: Tanh projection (binarization)
        x_proj = tanh_projection(x_filt, beta, eta)
        return x_proj

    # ── 최종 구조 binary 비율 확인 ────────────────────────────────────────────
    def check_binary_ratio(x_final, threshold=0.5):
        ratio = np.mean((x_final > threshold) | (x_final < 1 - threshold))
        if mp.am_master():
            binary_ratio = np.mean(np.abs(x_final - 0.5) > 0.4)
            print(f"[Stage 5-5] Binary ratio: {binary_ratio:.1%}  (≥90% = good)")
            if binary_ratio < 0.9:
                print("            ⚠️ 구조가 아직 회색 영역 많음 — beta 더 높이거나 iteration 추가")
        return ratio

    # ── 최종 구조 플롯 ────────────────────────────────────────────────────────
    def plot_final_structure(x_final, output_dir, iteration):
        if mp.am_master():
            x_2d = x_final.reshape(Nx, Ny)
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.imshow(
                x_2d.T, cmap="binary", origin="lower", vmin=0, vmax=1,
                extent=[-design_len/2, design_len/2, -design_wid/2, design_wid/2]
            )
            ax.set_title(f"Final Structure (iter={iteration})")
            ax.set_xlabel("x (μm)"); ax.set_ylabel("y (μm)")
            plt.tight_layout()
            path = Path(output_dir) / f"design_iter{iteration:03d}.png"
            plt.savefig(path, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"[Stage 5-5] Saved: {path}")
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
