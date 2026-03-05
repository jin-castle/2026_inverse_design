#!/usr/bin/env python3
"""
Pattern: user_defined_material
Custom materials: epsilon_func, spatially-dependent refractive index, MaterialGrid
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "user_defined_material"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    import unittest

    # Material function that recreates the ellipsoid-in-cylinder configuration of
    # examples/cyl-ellipsoid.py
    def my_material_func(p):
        R1X = 0.5
        R1Y = 1.0
        R2 = 3.0

        x = p.x
        y = p.y

        # test for point inside inner ellipsoid
        if (x**2 / (R1X**2) + y**2 / (R1Y**2)) < 1.0:
            nn = 1.0
        elif (x**2 / (R2**2) + y**2 / (R2**2)) < 1.0:
            nn = 3.5
        else:
            nn = 1.0

        return mp.Medium(epsilon=nn**2)

    def my_epsilon_func(p):
        R1X = 0.5
        R1Y = 1.0
        R2 = 3.0

        x = p.x
        y = p.y

        if (x**2 / (R1X**2) + y**2 / (R1Y**2)) < 1.0:
            return 1.0
        elif (x**2 / (R2**2) + y**2 / (R2**2)) < 1.0:
            return 3.5
        return 1.0

    class TestUserMaterials(unittest.TestCase):

        def setUp(self):
            self.resolution = 10
            self.cell = mp.Vector3(10, 10)
            self.symmetries = [mp.Mirror(mp.X), mp.Mirror(mp.Y)]
            self.boundary_layers = [mp.PML(1.0)]
            self.sources = [mp.Source(src=mp.GaussianSource(0.2, fwidth=0.1),
                                      component=mp.Ez, center=mp.Vector3())]

        def test_user_material_func(self):
            sim = mp.Simulation(cell_size=self.cell,
                                resolution=self.resolution,
                                symmetries=self.symmetries,
                                boundary_layers=self.boundary_layers,
                                sources=self.sources,
                                material_function=my_material_func)

            sim.run(until=200)
            fp = sim.get_field_point(mp.Ez, mp.Vector3(x=1))

            self.assertAlmostEqual(fp, 4.816403627871773e-4 + 0j)

        def test_epsilon_func(self):
            sim = mp.Simulation(cell_size=self.cell,
                                resolution=self.resolution,
                                symmetries=self.symmetries,
                                boundary_layers=self.boundary_layers,
                                sources=self.sources,
                                epsilon_func=my_epsilon_func)

            sim.run(until=100)
            fp = sim.get_field_point(mp.Ez, mp.Vector3(x=1))

            self.assertAlmostEqual(fp, -7.895783750440999e-4 + 0j)

        def test_geometric_obj_with_user_material(self):
            geometry = [mp.Cylinder(5, material=my_material_func)]

            sim = mp.Simulation(cell_size=self.cell,
                                resolution=self.resolution,
                                symmetries=self.symmetries,
                                geometry=geometry,
                                boundary_layers=self.boundary_layers,
                                sources=self.sources)
            sim.run(until=200)
            fp = sim.get_field_point(mp.Ez, mp.Vector3(x=1))

            self.assertAlmostEqual(fp, 4.816403627871773e-4 + 0j)

        def test_geometric_obj_with_epsilon_func(self):
            geometry = [mp.Cylinder(5, epsilon_func=my_epsilon_func)]

            sim = mp.Simulation(cell_size=self.cell,
                                resolution=self.resolution,
                                symmetries=self.symmetries,
                                geometry=geometry,
                                boundary_layers=self.boundary_layers,
                                sources=self.sources)
            sim.run(until=100)
            fp = sim.get_field_point(mp.Ez, mp.Vector3(x=1))

            self.assertAlmostEqual(fp, -7.895783750440999e-4 + 0j)

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
