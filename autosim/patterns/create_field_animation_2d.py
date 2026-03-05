#!/usr/bin/env python3
"""
Pattern: create_field_animation_2d
2D FDTD field propagation animation: mp.Animate2D + to_mp4(), Ez component (TE polarization, ODD_Z parity)
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "create_field_animation_2d"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def create_field_animation(sim, layout: dict, output_dir: Path):
        """Create field propagation animation using mp.Animate2D."""
        # Use MEEP defaults for clear structure visibility
        anim = mp.Animate2D(
            sim,
            fields=mp.Ez,
            realtime=False,
            normalize=True,
            output_plane=mp.Volume(
                center=mp.Vector3(),
                size=mp.Vector3(layout["sx"], layout["sy"], 0),
            ),
        )

        sim.run(
            mp.at_every(max(1.0, 0.5 / FREQUENCY), anim),
            until_after_sources=mp.stop_when_fields_decayed(
                50, mp.Ez, mp.Vector3(OUTPUT_MONITOR_X, 0, 0), 1e-3
            ),
        )

        # Save as MP4
        anim.to_mp4(15, str(output_dir / "field_propagation.mp4"))
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
