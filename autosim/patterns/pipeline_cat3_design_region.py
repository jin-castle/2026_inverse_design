#!/usr/bin/env python3
"""
Pattern: pipeline_cat3_design_region
[Category 3: 디자인 영역 설정] MaterialGrid + DesignRegion 정의.
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "pipeline_cat3_design_region"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # ── 디자인 영역 크기 ──────────────────────────────────────────────────────
    design_region_size   = mp.Vector3(design_len, design_wid)
    design_region_center = mp.Vector3(0, 0, 0)

    # ── MaterialGrid 해상도 (시뮬레이션 resolution과 맞춤) ─────────────────────
    Nx = int(round(design_len * resolution))   # e.g. 3.0 * 50 = 150
    Ny = int(round(design_wid * resolution))   # e.g. 2.0 * 50 = 100
    print(f"[DesignRegion] Nx={Nx}, Ny={Ny}, total params={Nx*Ny}")

    # ── MaterialGrid 정의 ─────────────────────────────────────────────────────
    design_variables = mp.MaterialGrid(
        mp.Vector3(Nx, Ny),
        mp.air,          # u=0 -> air (ε=1)
        silicon,         # u=1 -> Si (ε=12.11)
        grid_type="U_MEAN",
        do_averaging=True,   # 서브픽셀 평균화 (수렴 안정성 향상)
    )

    # ── DesignRegion 등록 ─────────────────────────────────────────────────────
    design_region = mpa.DesignRegion(
        design_variables,
        volume=mp.Volume(
            center=design_region_center,
            size=design_region_size,
        ),
    )

    # ── Geometry에 디자인 영역 Block 추가 (geometry 리스트에 append) ───────────
    design_block = mp.Block(
        center=design_region_center,
        size=design_region_size,
        material=design_variables,
    )
    geometry.append(design_block)   # geometry = [wg_in, wg_out, design_block]

    # ── 초기값 ────────────────────────────────────────────────────────────────
    x0 = np.full(Nx * Ny, 0.5)   # 균일 초기화 (표준)
    # x0 = np.random.rand(Nx * Ny) * 0.1 + 0.45  # 약한 랜덤 노이즈 버전
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
