#!/usr/bin/env python3
"""
Pattern: pipeline_cat1_2d_vs_3d_setup
[Category 1: 시뮬레이션 환경 설정] 2D vs 3D 시뮬레이션 설정 차이.
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "pipeline_cat1_2d_vs_3d_setup"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # ── 2D 설정 ───────────────────────────────────────────────────────────────
    wg_width   = 0.5         # μm
    design_len = 3.0         # μm (디자인 영역 길이)
    design_wid = 2.0         # μm (디자인 영역 폭)

    # 2D Cell
    sxy_x = design_len + 4.0 + 2 * dpml   # 디자인 + 입출력 도파로 + PML
    sxy_y = design_wid + 2.0 + 2 * dpml   # 디자인 + 여유 + PML
    cell_2d = mp.Vector3(sxy_x, sxy_y, 0)

    # eig_parity for 2D TE
    parity_2d = mp.ODD_Z + mp.EVEN_Y

    # ── 3D 설정 ───────────────────────────────────────────────────────────────
    # 기판 포함 z 크기
    air_gap = 1.0
    sz = wg_thick + sub_thick + dpml + air_gap   # ≈ 2.72 μm
    cell_3d = mp.Vector3(sxy_x, sxy_y, sz)

    # 3D SiO2 기판 (z 아래쪽)
    # z_center_sub = -wg_thick/2 - sub_thick/2  (Si slab 아래)
    z_center_sub = -(wg_thick / 2 + sub_thick / 2)
    substrate_3d = mp.Block(
        size=mp.Vector3(mp.inf, mp.inf, sub_thick),
        center=mp.Vector3(0, 0, z_center_sub),
        material=oxide
    )

    # eig_parity for 3D TE
    parity_3d = mp.ODD_Z   # TE mode
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
