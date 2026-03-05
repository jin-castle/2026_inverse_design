#!/usr/bin/env python3
"""
Pattern: third_harmonic_generation
Third harmonic generation: chi3 nonlinearity, 1ω→3ω conversion, nonlinear susceptibility
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "third_harmonic_generation"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    import unittest

    class Test3rdHarm1d(unittest.TestCase):

        def setUp(self):
            self.sz = 100
            fcen = 1 / 3.0
            df = fcen / 20.0
            self.amp = 1.0
            self.k = 1e-2
            self.dpml = 1.0
            dimensions = 1
            cell = mp.Vector3(0, 0, self.sz)

            default_material = mp.Medium(index=1, chi3=self.k)

            pml_layers = mp.PML(self.dpml)

            sources = mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ex,
                                center=mp.Vector3(0, 0, (-0.5 * self.sz) + self.dpml), amplitude=self.amp)

            nfreq = 400
            fmin = fcen / 2.0
            fmax = fcen * 4

            self.sim = mp.Simulation(cell_size=cell,
                                     geometry=[],
                                     sources=[sources],
                                     boundary_layers=[pml_layers],
                                     default_material=default_material,
                                     resolution=20,
                                     dimensions=dimensions)

            fr = mp.FluxRegion(mp.Vector3(0, 0, (0.5 * self.sz) - self.dpml - 0.5))
            self.trans = self.sim.add_flux(0.5 * (fmin + fmax), fmax - fmin, nfreq, fr)
            self.trans1 = self.sim.add_flux(fcen, 0, 1, fr)
            self.trans3 = self.sim.add_flux(3 * fcen, 0, 1, fr)

        def test_3rd_harm_1d(self):

            expected_harmonics = [0.01, 1.0, 221.89548712071553, 1.752960413399477]

            self.sim.run(
                until_after_sources=mp.stop_when_fields_decayed(
                    50, mp.Ex, mp.Vector3(0, 0, (0.5 * self.sz) - self.dpml - 0.5), 1e-6
                )
            )

            harmonics = [self.k, self.amp, mp.get_fluxes(self.trans1)[0], mp.get_fluxes(self.trans3)[0]]

            np.testing.assert_allclose(expected_harmonics, harmonics)

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
