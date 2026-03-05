#!/usr/bin/env python3
"""
Pattern: mode_coefficients_test
Mode coefficient verification: add_flux, get_eigenmode_coefficients, alpha coefficient extraction pattern
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "mode_coefficients_test"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    import unittest

    class TestModeCoeffs(unittest.TestCase):

        def run_mode_coeffs(self, mode_num, kpoint_func, nf=1, resolution=15):

            w = 1   # width of waveguide
            L = 10  # length of waveguide

            Si = mp.Medium(epsilon=12.0)

            dair = 3.0
            dpml = 3.0

            sx = dpml + L + dpml
            sy = dpml + dair + w + dair + dpml
            cell_size = mp.Vector3(sx, sy, 0)

            prism_x = sx + 1
            prism_y = w / 2
            vertices = [mp.Vector3(-prism_x, prism_y),
                        mp.Vector3(prism_x, prism_y),
                        mp.Vector3(prism_x, -prism_y),
                        mp.Vector3(-prism_x, -prism_y)]

            geometry = [mp.Prism(vertices, height=mp.inf, material=Si)]

            boundary_layers = [mp.PML(dpml)]

            # mode frequency
            fcen = 0.20  # > 0.5/sqrt(11) to have at least 2 modes
            df   = 0.5*fcen

            source=mp.EigenModeSource(src=mp.GaussianSource(fcen, fwidth=df),
                                      eig_band=mode_num,
                                      size=mp.Vector3(0,sy-2*dpml,0),
                                      center=mp.Vector3(-0.5*sx+dpml,0,0),
                                      eig_match_freq=True,
                                      eig_resolution=2*resolution)

            sim = mp.Simulation(resolution=resolution,
                                cell_size=cell_size,
                                boundary_layers=boundary_layers,
                                geometry=geometry,
                                sources=[source],
                                symmetries=[mp.Mirror(mp.Y, phase=1 if mode_num % 2 == 1 else -1)])

            xm = 0.5*sx - dpml  # x-coordinate of monitor
            mflux = sim.add_mode_monitor(fcen, df, nf, mp.ModeRegion(center=mp.Vector3(xm,0), size=mp.Vector3(0,sy-2*dpml)))
            mode_flux = sim.add_flux(fcen, df, nf, mp.FluxRegion(center=mp.Vector3(xm,0), size=mp.Vector3(0,sy-2*dpml)))

            # sim.run(until_after_sources=mp.stop_when_fields_decayed(50, mp.Ez, mp.Vector3(-0.5*sx+dpml,0), 1e-10))
            sim.run(until_after_sources=100)

            ##################################################
            # If the number of analysis frequencies is >1, we
            # are testing the unit-power normalization
            # of the eigenmode source: we observe the total
            # power flux through the mode_flux monitor (which
            # equals the total power emitted by the source as
            # there is no scattering in this ideal waveguide)
            # and check that it agrees with the prediction
            # of the eig_power() class method in EigenmodeSource.
            ##################################################
            if nf>1:
                power_observed=mp.get_fluxes(mode_flux)
                freqs=mp.get_flux_freqs(mode_flux)
                power_expected=[source.eig_power(f) for f in freqs]
                return freqs, power_expected, power_observed

            modes_to_check = [1, 2]  # indices of modes for which to compute expansion coefficients
            res = sim.get_eigenmode_coefficients(mflux, modes_to_check, kpoint_func=kpoint_func)

            self.assertTrue(res.kpoints[0].close(mp.Vector3(0.604301, 0, 0)))
            self.assertTrue(res.kpoints[1].close(mp.Vector3(0.494353, 0, 0), tol=1e-2))
            self.assertTrue(res.kdom[0].close(mp.Vector3(0.604301, 0, 0)))
            self.assertTrue(res.kdom[1].close(mp.Vector3(0.494353, 0, 0), tol=1e-2))
            self.assertAlmostEqual(res.cscale[0],0.50000977,places=5)
            self.assertAlmostEqual(res.cscale[1],0.50096888,places=5)
            mode_power = mp.get_fluxes(mode_flux)[0]

            TestPassed = True
            TOLERANCE = 5.0e-3
            c0 = res.alpha[mode_num - 1, 0, 0] # coefficient of forward-traveling wave for mode #mode_num
            for nm in range(1, len(modes_to_check)+1):
                if nm != mode_num:
                    cfrel = np.abs(res.alpha[nm - 1, 0, 0]) / np.abs(c0)
                    cbrel = np.abs(res.alpha[nm - 1, 0, 1]) / np.abs(c0)
                    if cfrel > TOLERANCE or cbrel > TOLERANCE:
                        TestPassed = False

            self.sim = sim

            # test 1: coefficient of excited mode >> coeffs of all other modes
            self.assertTrue(TestPassed, msg="cfrel: {}, cbrel: {}".format(cfrel, cbrel))
            # test 2: |mode coeff|^2 = power
            self.assertAlmostEqual(mode_power / abs(c0**2), 1.0, places=1)

            return res

        def test_modes(self):
            self.run_mode_coeffs(1, None)
            res = self.run_mode_coeffs(2, None)

            # Test mp.get_eigenmode and EigenmodeData
            vol = mp.Volume(center=mp.Vector3(5), size=mp.Vector3(y=7))
            emdata = self.sim.get_eigenmode(0.2, mp.X, vol, 2, mp.Vector3())
            self.assertEqual(emdata.freq, 0.2)
            self.assertEqual(emdata.band_num, 2)
            self.assertTrue(emdata.kdom.close(res.kdom[1]))

            eval_point = mp.Vector3(0.7, -0.2, 0.3)
            ex_at_eval_point = emdata.amplitude(eval_point, mp.Ex)
            hz_at_eval_point
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
