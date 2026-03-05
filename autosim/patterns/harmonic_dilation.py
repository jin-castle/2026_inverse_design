#!/usr/bin/env python3
"""
Pattern: harmonic_dilation
Hammond et al. 2021 Eq.9: D(ρ)=1-E(1-ρ), Si region expansion
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "harmonic_dilation"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def harmonic_dilation(
        rho: np.ndarray,
        etch_nm: float,
        resolution: int = DESIGN_RESOLUTION,
        alpha: float = 1e-3,
    ) -> np.ndarray:
        """
        Hammond et al. 2021 Eq. 9 - Harmonic Dilation Filter

        D(ρ) = 1 − E(1−ρ)
             = 1 − (1/(1−ρ+α) ∗ w)^(-1) − α

        Si 영역이 확장됩니다 (과증착 시뮬레이션).

        Args:
            rho: Density array (any shape, 0~1)
            etch_nm: Dilation amount in nm (양수 = Si 확장)
            resolution: 픽셀/μm (default: 60 for 3D)
            alpha: Numerical stability (default: 1e-3)

        Returns:
            dilated: Dilated density array (same shape)
        """
        return 1.0 - harmonic_erosion(1.0 - rho, etch_nm, resolution, alpha)
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
