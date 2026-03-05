#!/usr/bin/env python3
"""
Pattern: pipeline_cat2_geometry_layout
[Category 2: 지오메트리 구성] 입출력 도파로 + 레이아웃 플롯.
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "pipeline_cat2_geometry_layout"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    matplotlib.use("Agg")   # 헤드리스 서버용 (GUI 없을 때 필수)

    # ── 입출력 도파로 기본 geometry ────────────────────────────────────────────
    wg_width   = 0.5         # μm 입력 도파로 폭
    wg_length  = 2.0         # μm 입출력 도파로 길이 (디자인 영역 양쪽)
    design_len = 3.0         # μm 디자인 영역 길이
    design_wid = 2.0         # μm 디자인 영역 폭

    # 입력 도파로 (왼쪽)
    wg_in = mp.Block(
        size=mp.Vector3(wg_length, wg_width, mp.inf),
        center=mp.Vector3(-(design_len / 2 + wg_length / 2), 0, 0),
        material=silicon
    )
    # 출력 도파로 (오른쪽)
    wg_out = mp.Block(
        size=mp.Vector3(wg_length, wg_width, mp.inf),
        center=mp.Vector3(design_len / 2 + wg_length / 2, 0, 0),
        material=silicon
    )

    geometry = [wg_in, wg_out]
    # 주의: 디자인 영역 Block은 Cat.3에서 추가

    # ── 레이아웃 플롯 (시뮬레이션 실행 전 구조 확인) ─────────────────────────
    sim_for_plot = mp.Simulation(
        resolution=resolution,
        cell_size=cell_2d,
        boundary_layers=boundary_layers,
        geometry=geometry,
        default_material=oxide,    # 배경 재료
        sources=[]
    )
    sim_for_plot.init_sim()

    if mp.am_master():
        output_dir = Path("./output")
        output_dir.mkdir(exist_ok=True)
        fig, ax = plt.subplots(figsize=(10, 6))
        sim_for_plot.plot2D(ax=ax)
        ax.set_title("Initial Layout — Check before running simulation")
        plt.savefig(output_dir / "initial_layout.png", dpi=150, bbox_inches="tight")
        plt.close()
        print("[Layout] Saved: output/initial_layout.png")

    sim_for_plot.reset_meep()
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
