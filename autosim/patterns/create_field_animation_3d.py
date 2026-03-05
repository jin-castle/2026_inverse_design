#!/usr/bin/env python3
"""
Pattern: create_field_animation_3d
3D FDTD field propagation animation: XY slice at slab center, Ey component (SOI slab TE-like mode)
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "create_field_animation_3d"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def create_field_animation_3d(sim, layout: dict, output_dir: Path):
        """Create field propagation animation for 3D (XY slice at slab center)."""
        anim = mp.Animate2D(
            sim,
            fields=mp.Ey,  # Ey for SOI slab TE-like mode
            realtime=False,
            normalize=True,
            output_plane=mp.Volume(
                center=mp.Vector3(0, 0, SLAB_THICKNESS / 2),
                size=mp.Vector3(layout["sx"], layout["sy"], 0)
            ),
        )

        sim.run(mp.at_every(0.5, anim), until=80)

        anim.to_mp4(10, str(output_dir / "field_propagation.mp4"))
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
