#!/usr/bin/env python3
"""
Pattern: stop_when_fields_decayed
Automatically terminate MEEP simulation when fields have sufficiently decayed. mp.stop_when_fields_decayed(dt, c, pt, de
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "stop_when_fields_decayed"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # Python port of meep/examples/ring.ctl
    # Calculating 2d ring-resonator modes, from the Meep tutorial.

    import unittest

    class TestRing(unittest.TestCase):

        @classmethod
        def setUpClass(cls):
            cls.temp_dir = mp.make_output_directory()

        @classmethod
        def tearDownClass(cls):
            mp.delete_directory(cls.temp_dir)

        def init(self):
            n = 3.4
            w = 1
            r = 1
            pad = 4
            dpml = 2
            sxy = 2 * (r + w + pad + dpml)

            dielectric = mp.Medium(epsilon=n * n)
            air = mp.Medium()

            c1 = mp.Cylinder(r + w, material=dielectric)
            c2 = mp.Cylinder(r, material=air)

            fcen = 0.15
            df = 0.1

            src = mp.Source(mp.GaussianSource(fcen, fwidth=df), mp.Ez, mp.Vector3(r + 0.1))

            self.sim = mp.Simulation(cell_size=mp.Vector3(sxy, sxy),
                                     geometry=[c1, c2],
                                     sources=[src],
                                     resolution=10,
                                     symmetries=[mp.Mirror(mp.Y)],
                                     boundary_layers=[mp.PML(dpml)])

            self.sim.use_output_directory(self.temp_dir)
            self.h = mp.Harminv(mp.Ez, mp.Vector3(r + 0.1), fcen, df)

        def test_harminv(self):
            self.init()

            self.sim.run(
                mp.at_beginning(mp.output_epsilon),
                mp.after_sources(self.h),
                until_after_sources=300
            )

            m1 = self.h.modes[0]

            self.assertAlmostEqual(m1.freq, 0.118101315147, places=4)
            self.assertAlmostEqual(m1.decay, -0.000731513241623, places=4)
            self.assertAlmostEqual(abs(m1.amp), 0.00341267634436, places=4)
            self.assertAlmostEqual(m1.amp.real, -0.00304951667301, places=4)
            self.assertAlmostEqual(m1.amp.imag, -0.00153192946717, places=3)

            v = mp.Vector3(1, 1)
            fp = self.sim.get_field_point(mp.Ez, v)
            ep = self.sim.get_epsilon_point(v)

            self.assertAlmostEqual(ep, 11.559999999999999)
            self.assertAlmostEqual(fp, -0.08185972142450348)

    if __name__ == '__main__':
        unittest.main()
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
