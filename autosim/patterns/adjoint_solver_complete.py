#!/usr/bin/env python3
"""
Pattern: adjoint_solver_complete
NanoComp MEEP adjoint solver full testing: OptimizationProblem, gradient verification
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "adjoint_solver_complete"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    try:
        pass
    except:
        import adjoint as mpa

    import unittest
    from enum import Enum
    from typing import List, Union, Tuple

    from utils import ApproxComparisonTestCase

    MonitorObject = Enum("MonitorObject", "EIGENMODE DFT LDOS")

    class TestAdjointSolver(ApproxComparisonTestCase):
        @classmethod
        def setUpClass(cls):
            cls.resolution = 30  # pixels/μm

            cls.silicon = mp.Medium(epsilon=12)
            cls.sapphire = mp.Medium(
                epsilon_diag=(10.225, 10.225, 9.95),
                epsilon_offdiag=(-0.825, -0.55 * np.sqrt(3 / 2), 0.55 * np.sqrt(3 / 2)),
            )

            cls.sxy = 5.0
            cls.cell_size = mp.Vector3(cls.sxy, cls.sxy, 0)

            cls.dpml = 1.0
            cls.pml_xy = [mp.PML(thickness=cls.dpml)]
            cls.pml_x = [mp.PML(thickness=cls.dpml, direction=mp.X)]

            cls.eig_parity = mp.EVEN_Y + mp.ODD_Z
            cls.src_cmpt = mp.Ez

            cls.design_region_size = mp.Vector3(1.5, 1.5)
            cls.design_region_resolution = int(2 * cls.resolution)
            cls.Nx = int(round(cls.design_region_size.x * cls.design_region_resolution)) + 1
            cls.Ny = int(round(cls.design_region_size.y * cls.design_region_resolution)) + 1

            # ensure reproducible results
            rng = np.random.RandomState(9861548)

            # random design region
            cls.p = 0.5 * rng.rand(cls.Nx * cls.Ny)

            # random perturbation for design region
            deps = 1e-5
            cls.dp = deps * rng.rand(cls.Nx * cls.Ny)

            cls.w = 1.0
            cls.waveguide_geometry = [
                mp.Block(
                    material=cls.silicon,
                    center=mp.Vector3(),
                    size=mp.Vector3(mp.inf, cls.w, mp.inf),
                )
            ]

            # source center frequency and bandwidth
            cls.fcen = 1 / 1.55
            cls.df = 0.05 * cls.fcen

            # monitor frequencies
            # two cases: (1) single and (2) multi frequency
            cls.mon_frqs = [
                [cls.fcen],
                [
                    cls.fcen - 0.09 * cls.df,
                    cls.fcen,
                    cls.fcen + 0.06 * cls.df,
                ],
            ]

            cls.mode_source = [
                mp.EigenModeSource(
                    src=mp.GaussianSource(cls.fcen, fwidth=cls.df),
                    center=mp.Vector3(-0.5 * cls.sxy + cls.dpml, 0),
                    size=mp.Vector3(0, cls.sxy - 2 * cls.dpml),
                    eig_parity=cls.eig_parity,
                )
            ]

            cls.pt_source = [
                mp.Source(
                    src=mp.GaussianSource(cls.fcen, fwidth=cls.df),
                    center=mp.Vector3(-0.5 * cls.sxy + cls.dpml, 0),
                    size=mp.Vector3(),
                    component=cls.src_cmpt,
                )
            ]

            cls.line_source = [
                mp.Source(
                    src=mp.GaussianSource(cls.fcen, fwidth=cls.df),
                    center=mp.Vector3(-0.85, 0),
                    size=mp.Vector3(0, cls.sxy - 2 * cls.dpml),
                    component=cls.src_cmpt,
                )
            ]

            cls.k_point = mp.Vector3(0.23, -0.38)

            # location of DFT monitors for reflected and transmitted fields
            cls.refl_pt = mp.Vector3(-0.5 * cls.sxy + cls.dpml + 0.5, 0)
            cls.tran_pt = mp.Vector3(0.5 * cls.sxy - cls.dpml, 0)

        def adjoint_solver(
            self,
            design_params: List[float] = None,
            mon_type: MonitorObject = None,
            frequencies: List[float] = None,
            mat2: mp.Medium = None,
            need_gradient: bool = True,
        ) -> Tuple[np.ndarray, np.ndarray]:
            matgrid = mp.MaterialGrid(
                mp.Vector3(self.Nx, self.Ny),
                mp.air,
                self.silicon if mat2 is None else mat2,
                weights=np.ones((self.Nx, self.Ny)),
            )

            matgrid_region = mpa.DesignRegion(
                matgrid,
                volume=mp.Volume(
                    center=mp.Vector3(),
                    size=mp.Vector3(
                        self.design_region_size.x, self.design_region_size.y, 0
                    ),
                ),
            )

            matgrid_geometry = [
                mp.Block(
                    center=matgrid_region.center, size=matgrid_region.size, material=matgrid
                )
            ]

            geometry = self.waveguide_geometry + matgrid_geometry

            sim = mp.Simulation(
                resolution=self.resolution,
                cell_size=self.cell_size,
                boundary_layers=self.pml_xy,
                sources=self.mode_source,
                geometry=geometry,
            )

            if not frequencies:
                frequencies = [self.fcen]

            if mon_type.name == "EIGENMODE":
                if len(frequencies) == 1:
                    if mat2 is None:
                        # the incident fields of the mode source in the
                        # straight waveguide are used as normalization
                        # of the reflectance (S11) measurement.
                        ref_sim = mp.Simulation(
                            resolution=self.resolution,
                            cell_size=self.cell_size,
                            boundary_layers=self.pml_xy,
                            sources=self.mode_source,
                            geometry=self.waveguide_geometry,
                        )
                        dft_mon = ref_sim.add_mode_monitor(
                            frequencies,
                            mp.ModeRegion(
                                center=self.refl_pt,
                                size=mp.Vector3(0, self.sxy - 2 * self.dpml, 0),
                            ),
                            yee_grid=True,
                        )
                        ref_sim.run(until_after_sources=20)
                        subtracted_dft_fields = ref_sim.get_flux_data(dft_mon)
                    else:
                        subtracted_dft_fields = None
    # ... (truncated)
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
