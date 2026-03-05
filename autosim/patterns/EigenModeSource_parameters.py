#!/usr/bin/env python3
"""
Pattern: EigenModeSource_parameters
EigenModeSource key parameter explanation and mode decomposition
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "EigenModeSource_parameters"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # EigenModeSource 주요 파라미터
    sources = [mp.EigenModeSource(
        src=mp.GaussianSource(frequency=1/1.55, fwidth=0.2),
        center=mp.Vector3(-L/2+dpml, 0),   # 소스 위치
        size=mp.Vector3(0, Sy, 0),          # 단면 크기 (Y방향)
        eig_band=1,                          # 모드 번호 (1=fundamental)
        direction=mp.X,                      # 전파 방향
        eig_parity=mp.EVEN_Y + mp.ODD_Z,   # 2D TE: ODD_Z, TM: EVEN_Z
        eig_kpoint=mp.Vector3(1, 0, 0),    # k-point 방향 힌트
        eig_match_freq=True,                 # True: 주파수 매칭
    )]

    # Mode decomposition (출력 전력 계산)
    mode_mon = sim.add_mode_monitor(
        fcen, df, nfreq,
        mp.ModeRegion(center=mp.Vector3(+L/2-dpml, 0),
                      size=mp.Vector3(0, Sy, 0))
    )
    sim.run(until_after_sources=mp.stop_when_fields_decayed(50, mp.Ez,
            mp.Vector3(L/2-dpml, 0), 1e-9))

    # 전송률 계산
    res = sim.get_eigenmode_coefficients(mode_mon, [1],
          eig_parity=mp.EVEN_Y + mp.ODD_Z)
    coeffs = res.alpha  # shape: (num_modes, num_freqs, 2)  [0]=forward, [1]=backward
    T = abs(coeffs[0, :, 0])**2  # forward power transmission
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
