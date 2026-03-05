#!/usr/bin/env python3
"""
Pattern: array_metadata
Simulation metadata: get_array_metadata, verify coordinate array and field array shape
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "array_metadata"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    import unittest

    class TestArrayMetadata(unittest.TestCase):

        def test_array_metadata(self):
            resolution = 25

            n = 3.4
            w = 1
            r = 1
            pad = 4
            dpml = 2

            sxy = 2*(r+w+pad+dpml)
            cell_size = mp.Vector3(sxy,sxy)

            nonpml_vol = mp.Volume(mp.Vector3(), size=mp.Vector3(sxy-2*dpml,sxy-2*dpml))

            geometry = [mp.Cylinder(radius=r+w, material=mp.Medium(index=n)),
                        mp.Cylinder(radius=r)]

            fcen = 0.118
            df = 0.08

            symmetries = [mp.Mirror(mp.X,phase=-1),
                          mp.Mirror(mp.Y,phase=+1)]

            pml_layers = [mp.PML(dpml)]

            # CW source
            src = [mp.Source(mp.ContinuousSource(fcen,fwidth=df), mp.Ez, mp.Vector3(r+0.1)),
                   mp.Source(mp.ContinuousSource(fcen,fwidth=df), mp.Ez, mp.Vector3(-(r+0.1)), amplitude=-1)]

            sim = mp.Simulation(cell_size=cell_size,
                                geometry=geometry,
                                sources=src,
                                resolution=resolution,
                                force_complex_fields=True,
                                symmetries=symmetries,
                                boundary_layers=pml_layers)

            sim.init_sim()
            sim.solve_cw(1e-6, 1000, 10)

            def electric_energy(r, ez, eps):
                return np.real(eps * np.conj(ez)*ez)

            def vec_func(r):
                return r.x**2 + 2*r.y**2

            electric_energy_total = sim.integrate_field_function([mp.Ez,mp.Dielectric],electric_energy,nonpml_vol)
            electric_energy_max = sim.max_abs_field_function([mp.Ez,mp.Dielectric],electric_energy,nonpml_vol)
            vec_func_total = sim.integrate_field_function([],vec_func,nonpml_vol)
            cw_modal_volume = (electric_energy_total / electric_energy_max) * vec_func_total

            sim.reset_meep()

            # pulsed source
            src = [mp.Source(mp.GaussianSource(fcen,fwidth=df), mp.Ez, mp.Vector3(r+0.1)),
                   mp.Source(mp.GaussianSource(fcen,fwidth=df), mp.Ez, mp.Vector3(-(r+0.1)), amplitude=-1)]

            sim = mp.Simulation(cell_size=cell_size,
                                geometry=geometry,
                                k_point=mp.Vector3(),
                                sources=src,
                                resolution=resolution,
                                symmetries=symmetries,
                                boundary_layers=pml_layers)

            dft_obj = sim.add_dft_fields([mp.Ez], fcen, 0, 1, where=nonpml_vol)
            sim.run(until_after_sources=100)

            Ez = sim.get_dft_array(dft_obj, mp.Ez, 0)
            (X,Y,Z,W) = sim.get_array_metadata(dft_cell=dft_obj)
            Eps = sim.get_array(vol=nonpml_vol, component=mp.Dielectric)
            EpsE2 = np.real(Eps*np.conj(Ez)*Ez)
            xm, ym = np.meshgrid(X, Y)
            vec_func_sum = np.sum(W*(xm**2 + 2*ym**2))
            pulse_modal_volume = np.sum(W*EpsE2)/np.max(EpsE2) * vec_func_sum

            self.assertAlmostEqual(cw_modal_volume/pulse_modal_volume, 1.00, places=2)

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
