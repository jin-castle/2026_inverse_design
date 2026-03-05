#!/usr/bin/env python3
"""
Pattern: harmonic_erosion
Hammond et al. 2021 Eq.8: E(ρ)=(1/(ρ+α)∗w)^(-1)−α, using scipy uniform_filter
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "harmonic_erosion"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def harmonic_erosion(
        rho: np.ndarray,
        etch_nm: float,
        resolution: int = DESIGN_RESOLUTION,
        alpha: float = 1e-3,
    ) -> np.ndarray:
        """
        Hammond et al. 2021 Eq. 8 - Harmonic Erosion Filter

        E(ρ) = (1/(ρ+α) ∗ w)^(-1) − α

        기존 grey_erosion/binary_erosion 대비 장점:
        - 정확한 etch_nm 제어 (±20nm 등)
        - Differentiable (autograd 호환 가능)
        - 연속적인 결과 (binary가 아닌 soft erosion)

        Args:
            rho: Density array (any shape, 0~1)
            etch_nm: Erosion amount in nm (양수 = Si 수축)
            resolution: 픽셀/μm (default: 60 for 3D)
            alpha: Numerical stability (default: 1e-3)

        Returns:
            eroded: Eroded density array (same shape)
        """
        from scipy.ndimage import uniform_filter

        # Filter radius in pixels
        # 1 μm = 1000 nm, resolution = px/μm
        # r_px = etch_nm / 1000 * resolution
        r_px = etch_nm / 1000.0 * resolution
        size = max(3, int(2 * r_px + 1))

        # Harmonic mean filter: (1/(ρ+α) ∗ w)
        # 각 픽셀에서 주변 영역의 harmonic mean 계산
        inv_rho = 1.0 / (rho + alpha)
        filtered = uniform_filter(inv_rho, size=size, mode='constant', cval=1.0/alpha)

        # E(ρ) = filtered^(-1) - α
        eroded = 1.0 / filtered - alpha

        return np.clip(eroded, 0.0, 1.0)
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
