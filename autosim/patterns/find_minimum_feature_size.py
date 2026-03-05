#!/usr/bin/env python3
"""
Pattern: find_minimum_feature_size
Minimum feature size based on distance_transform_edt: calculate separately for Si region and SiO2 (hole) region, then re
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "find_minimum_feature_size"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def find_minimum_feature_size(design: np.ndarray, pixel_size_nm: float) -> float:
        """Distance transform을 사용한 최소 feature size 계산."""
        from scipy.ndimage import distance_transform_edt

        binary = (design > 0.5).astype(int)

        # Si 영역의 최소 크기
        dist_si = distance_transform_edt(binary)
        min_si = np.min(dist_si[binary == 1]) * 2 * pixel_size_nm if np.any(binary) else 0

        # SiO2 (hole) 영역의 최소 크기
        dist_sio2 = distance_transform_edt(1 - binary)
        min_sio2 = np.min(dist_sio2[binary == 0]) * 2 * pixel_size_nm if np.any(1-binary) else 0

        return min(min_si, min_sio2) if min_si > 0 and min_sio2 > 0 else max(min_si, min_sio2)
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
