#!/usr/bin/env python3
"""
Pattern: pipeline_cat4_sources_monitors
[Category 4: 시뮬레이션 설정] EigenModeSource + EigenmodeCoefficient 모니터.
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "pipeline_cat4_sources_monitors"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # ── 소스/모니터 x 위치 ────────────────────────────────────────────────────
    src_x = -(design_len / 2 + wg_length * 0.7)  # 디자인 영역 왼쪽 바깥
    mon_x =   design_len / 2 + wg_length * 0.7   # 디자인 영역 오른쪽 바깥

    # ── 소스 크기 (도파로 폭보다 충분히 크게) ────────────────────────────────
    src_size_y = wg_width * 3.0    # 2D: y 방향만
    # src_size_z = wg_thick + sub_thick + 1.0  # 3D: z 방향 포함

    # ── EigenModeSource ────────────────────────────────────────────────────────
    sources = [
        mp.EigenModeSource(
            src=mp.GaussianSource(frequency=fcen, fwidth=fwidth),
            center=mp.Vector3(src_x, 0, 0),
            size=mp.Vector3(0, src_size_y, 0),   # 2D: z=0
            eig_band=1,          # ⚠️ 반드시 1부터 (0 금지!)
            eig_parity=parity_2d,
            eig_match_freq=True,
        )
    ]

    # ── Simulation 객체 ────────────────────────────────────────────────────────
    sim = mp.Simulation(
        resolution=resolution,
        cell_size=cell_2d,
        boundary_layers=boundary_layers,
        geometry=geometry,
        sources=sources,
        default_material=oxide,
    )

    # ── EigenmodeCoefficient 모니터 (mpa 모듈) ─────────────────────────────────
    # TE0 투과 모니터 (기본)
    te0_monitor = mpa.EigenmodeCoefficient(
        sim,
        mp.Volume(center=mp.Vector3(mon_x, 0, 0),
                  size=mp.Vector3(0, src_size_y, 0)),
        mode=1,          # ⚠️ eig_band와 마찬가지로 1부터
        forward=True,    # 포워드 방향 전파
        eig_parity=parity_2d,
    )

    # (선택) TE1 모니터 — mode demux 등에서 사용
    te1_monitor = mpa.EigenmodeCoefficient(
        sim,
        mp.Volume(center=mp.Vector3(mon_x, 0, 0),
                  size=mp.Vector3(0, src_size_y, 0)),
        mode=2,
        forward=True,
        eig_parity=parity_2d,
    )
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
