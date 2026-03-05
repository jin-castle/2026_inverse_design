#!/usr/bin/env python3
"""
Pattern: geometry_cylinder_ellipsoid
Geometric structures: Cylinder, Ellipsoid, intersection/difference, material assignment
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "geometry_cylinder_ellipsoid"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def main():

        c = mp.Cylinder(radius=3, material=mp.Medium(index=3.5))
        e = mp.Ellipsoid(size=mp.Vector3(1, 2, mp.inf))

        src_cmpt = mp.Hz
        sources = mp.Source(src=mp.GaussianSource(1, fwidth=0.1), component=src_cmpt, center=mp.Vector3())

        if src_cmpt == mp.Ez:
            symmetries = [mp.Mirror(mp.X), mp.Mirror(mp.Y)]

        if src_cmpt == mp.Hz:
            symmetries = [mp.Mirror(mp.X, -1), mp.Mirror(mp.Y, -1)]

        sim = mp.Simulation(cell_size=mp.Vector3(10, 10),
                            geometry=[c, e],
                            boundary_layers=[mp.PML(1.0)],
                            sources=[sources],
                            symmetries=symmetries,
                            resolution=100)

        def print_stuff(sim_obj):
            v = mp.Vector3(4.13, 3.75, 0)
            p = sim.get_field_point(src_cmpt, v)
            print("t, Ez: {} {}+{}i".format(sim.round_time(), p.real, p.imag))

        sim.run(mp.at_beginning(mp.output_epsilon),
                mp.at_every(0.25, print_stuff),
                mp.at_end(print_stuff),
                mp.at_end(mp.output_efield_z),
                until=23)

        print("stopped at meep time = {}".format(sim.round_time()))

    if __name__ == '__main__':
        main()
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
