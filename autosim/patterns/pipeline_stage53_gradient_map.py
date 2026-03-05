#!/usr/bin/env python3
"""
Pattern: pipeline_stage53_gradient_map
[Stage 5-3: Gradient 계산] Gradient map 플롯 + 수렴 로깅.
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "pipeline_stage53_gradient_map"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # ── opt([x0]) 실행 결과 ───────────────────────────────────────────────────
    fom, grad = opt([x0])
    # grad: list, grad[0]이 첫 번째 design_region의 gradient

    grad_arr = grad[0]   # shape: (Nx*Ny,)
    grad_2d  = grad_arr.reshape(Nx, Ny)

    if mp.am_master():
        print(f"[Stage 5-3] FOM={fom[0]:.6f}  |grad|={np.linalg.norm(grad_arr):.4e}")
        print(f"            grad max={grad_arr.max():.4e}  min={grad_arr.min():.4e}")

        # gradient NaN/Inf 체크
        if np.any(np.isnan(grad_arr)) or np.any(np.isinf(grad_arr)):
            print("[Stage 5-3] ⚠️ gradient에 NaN/Inf 감지! beta 낮추거나 x0 점검")

        output_dir = Path("./output")
        output_dir.mkdir(exist_ok=True)

        # Gradient Map 플롯
        fig, ax = plt.subplots(figsize=(8, 6))
        vmax = np.abs(grad_2d).max()
        im = ax.imshow(
            grad_2d.T, cmap="RdBu_r", origin="lower",
            vmin=-vmax, vmax=vmax,
            extent=[-design_len/2, design_len/2, -design_wid/2, design_wid/2]
        )
        plt.colorbar(im, ax=ax, label="dJ/dε (Gradient)")
        ax.set_title("Adjoint Gradient Map — Red: Add Si, Blue: Remove Si")
        ax.set_xlabel("x (μm)"); ax.set_ylabel("y (μm)")
        plt.tight_layout()
        plt.savefig(output_dir / "gradient_map.png", dpi=150, bbox_inches="tight")
        plt.close()
        print("[Stage 5-3] Saved: output/gradient_map.png")

    mp.all_wait()

    # ── 수렴 히스토리 기록 ────────────────────────────────────────────────────
    # iteration 루프 안에서 사용
    fom_history      = []
    grad_norm_history = []

    def record_history(fom_val, grad_val):
        if mp.am_master():
            fom_history.append(float(fom_val))
            grad_norm_history.append(float(np.linalg.norm(grad_val)))
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
