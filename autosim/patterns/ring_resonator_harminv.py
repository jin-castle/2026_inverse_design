#!/usr/bin/env python3
"""
Pattern: ring_resonator_harminv
Ring resonator Harminv: extract resonant frequency/Q. after_sources + Harminv, check decay
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "ring_resonator_harminv"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # Calculating 2d ring-resonator modes, from the Meep tutorial.

    def main():
        n = 3.4                 # index of waveguide
        w = 1                   # width of waveguide
        r = 1                   # inner radius of ring
        pad = 4                 # padding between waveguide and edge of PML
        dpml = 2                # thickness of PML
        sxy = 2*(r+w+pad+dpml)  # cell size

        # Create a ring waveguide by two overlapping cylinders - later objects
        # take precedence over earlier objects, so we put the outer cylinder first.
        # and the inner (air) cylinder second.

        c1 = mp.Cylinder(radius=r+w, material=mp.Medium(index=n))
        c2 = mp.Cylinder(radius=r)

        # If we don't want to excite a specific mode symmetry, we can just
        # put a single point source at some arbitrary place, pointing in some
        # arbitrary direction.  We will only look for Ez-polarized modes.

        fcen = 0.15             # pulse center frequency
        df = 0.1                # pulse width (in frequency)

        src = mp.Source(mp.GaussianSource(fcen, fwidth=df), mp.Ez, mp.Vector3(r+0.1))

        sim = mp.Simulation(cell_size=mp.Vector3(sxy, sxy),
                            geometry=[c1, c2],
                            sources=[src],
                            resolution=10,
                            symmetries=[mp.Mirror(mp.Y)],
                            boundary_layers=[mp.PML(dpml)])

        sim.run(mp.at_beginning(mp.output_epsilon),
                mp.after_sources(mp.Harminv(mp.Ez, mp.Vector3(r+0.1), fcen, df)),
                until_after_sources=300)

        # Output fields for one period at the end.  (If we output
        # at a single time, we might accidentally catch the Ez field when it is
        # almost zero and get a distorted view.)
        sim.run(mp.at_every(1/fcen/20, mp.output_efield_z), until=1/fcen)

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
