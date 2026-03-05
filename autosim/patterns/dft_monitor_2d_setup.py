#!/usr/bin/env python3
"""
Pattern: dft_monitor_2d_setup
Set up 2D DFT field monitors for full XY plane and cross-section profiles. XY plane monitor: all 6 E/H components for fi
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "dft_monitor_2d_setup"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # ── Full XY plane DFT monitor (all field components) ─────────────────────
    # Register BEFORE sim.run()
    def setup_dft_monitors_2d(sim, sx, sy, DPML, FREQUENCY,
                               source_x, output_monitor_x,
                               source_size_y):
        """Setup DFT monitors for 2D simulation.
    
        Returns dict of DFT objects for later array extraction.
        """
        # Full XY plane: all E/H components for field visualization
        dft_xy = sim.add_dft_fields(
            [mp.Ex, mp.Ey, mp.Ez, mp.Hx, mp.Hy, mp.Hz],
            FREQUENCY, 0, 1,          # center_freq, df, nfreq=1
            center=mp.Vector3(0, 0, 0),
            size=mp.Vector3(sx - 2*DPML, sy - 2*DPML, 0)
        )

        # Input cross-section: mode profile at source
        dft_input = sim.add_dft_fields(
            [mp.Ez, mp.Hx, mp.Hy],   # TE dominant components
            FREQUENCY, 0, 1,
            center=mp.Vector3(source_x, 0, 0),
            size=mp.Vector3(0, source_size_y, 0)  # YZ line
        )

        # Output cross-section: mode profile at monitor
        dft_output = sim.add_dft_fields(
            [mp.Ez, mp.Hx, mp.Hy],
            FREQUENCY, 0, 1,
            center=mp.Vector3(output_monitor_x, 0, 0),
            size=mp.Vector3(0, source_size_y, 0)
        )

        return {"xy": dft_xy, "input": dft_input, "output": dft_output}

    # ── Extract arrays after sim.run() ───────────────────────────────────────
    # dft_mons = setup_dft_monitors_2d(sim, ...)
    # sim.run(until_after_sources=...)
    # Ez_xy = sim.get_dft_array(dft_mons["xy"],    mp.Ez, 0)
    # Ez_in = sim.get_dft_array(dft_mons["input"], mp.Ez, 0)
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
