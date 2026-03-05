#!/usr/bin/env python3
"""
Pattern: adjoint_jax_integration
JAX + MEEP adjoint: Integration of JAX autograd and MEEP adjoint, JIT compilation
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "adjoint_jax_integration"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    import unittest

    import jax
    import jax.numpy as jnp

    import parameterized
    from utils import ApproxComparisonTestCase

    # The calculation of finite-difference gradients
    # requires that JAX be operated with double precision
    jax.config.update("jax_enable_x64", True)

    # The step size for the finite-difference
    # gradient calculation
    _FD_STEP = 1e-4

    # The tolerance for the adjoint and finite-difference
    # gradient comparison
    _TOL = 0.1 if mp.is_single_precision() else 0.025

    # We expect 3 design region monitor pointers
    # (one for each field component)
    _NUM_DES_REG_MON = 3

    mp.verbosity(0)

    def build_straight_wg_simulation(
        wg_width=0.5,
        wg_padding=1.0,
        wg_length=1.0,
        pml_width=1.0,
        source_to_pml=0.5,
        source_to_monitor=0.1,
        frequencies=[1 / 1.55],
        gaussian_rel_width=0.2,
        sim_resolution=20,
        design_region_resolution=20,
    ):
        """Builds a simulation of a straight waveguide with a design region segment."""
        design_region_shape = (1.0, wg_width)

        # Simulation domain size
        sx = 2 * pml_width + 2 * wg_length + design_region_shape[0]
        sy = (
            2 * pml_width
            + 2 * wg_padding
            + max(
                wg_width,
                design_region_shape[1],
            )
        )

        # Mean / center frequency
        fmean = onp.mean(frequencies)

        si = mp.Medium(index=3.4)
        sio2 = mp.Medium(index=1.44)

        sources = [
            mp.EigenModeSource(
                mp.GaussianSource(frequency=fmean, fwidth=fmean * gaussian_rel_width),
                eig_band=1,
                direction=mp.NO_DIRECTION,
                eig_kpoint=mp.Vector3(1, 0, 0),
                size=mp.Vector3(0, wg_width + 2 * wg_padding, 0),
                center=[-sx / 2 + pml_width + source_to_pml, 0, 0],
            ),
            mp.EigenModeSource(
                mp.GaussianSource(frequency=fmean, fwidth=fmean * gaussian_rel_width),
                eig_band=1,
                direction=mp.NO_DIRECTION,
                eig_kpoint=mp.Vector3(-1, 0, 0),
                size=mp.Vector3(0, wg_width + 2 * wg_padding, 0),
                center=[sx / 2 - pml_width - source_to_pml, 0, 0],
            ),
        ]
        nx, ny = int(design_region_shape[0] * design_region_resolution), int(
            design_region_shape[1] * design_region_resolution
        )
        mat_grid = mp.MaterialGrid(
            mp.Vector3(nx, ny),
            sio2,
            si,
            grid_type="U_DEFAULT",
        )

        design_regions = [
            mpa.DesignRegion(
                mat_grid,
                volume=mp.Volume(
                    center=mp.Vector3(),
                    size=mp.Vector3(
                        design_region_shape[0],
                        design_region_shape[1],
                        0,
                    ),
                ),
            )
        ]

        geometry = [
            mp.Block(
                center=mp.Vector3(
                    x=-design_region_shape[0] / 2 - wg_length / 2 - pml_width / 2
                ),
                material=si,
                size=mp.Vector3(wg_length + pml_width, wg_width, 0),
            ),  # left wg
            mp.Block(
                center=mp.Vector3(
                    x=+design_region_shape[0] / 2 + wg_length / 2 + pml_width / 2
                ),
                material=si,
                size=mp.Vector3(wg_length + pml_width, wg_width, 0),
            ),  # right wg
            mp.Block(
                center=design_regions[0].center,
                size=design_regions[0].size,
                material=mat_grid,
            ),  # design region
        ]

        simulation = mp.Simulation(
            cell_size=mp.Vector3(sx, sy),
            boundary_layers=[mp.PML(pml_width)],
            geometry=geometry,
            sources=sources,
            resolution=sim_resolution,
        )

        monitor_centers = [
            mp.Vector3(-sx / 2 + pml_width + source_to_pml + source_to_monitor),
            mp.Vector3(sx / 2 - pml_width - source_to_pml - source_to_monitor),
        ]
        monitor_size = mp.Vector3(y=wg_width + 2 * wg_padding)

        monitors = [
            mpa.EigenmodeCoefficient(
                simulation,
                mp.Volume(center=center, size=monitor_size),
                mode=1,
                forward=forward,
            )
            for center in monitor_centers
            for forward in [True, False]
        ]
        return simulation, sources, monitors, design_regions, frequencies

    class UtilsTest(unittest.TestCase):
        def setUp(self):
            super().setUp()
            (
                self.simulation,
                self.sources,
                self.monitors,
                self.design_regions,
                self.frequencies,
            ) = build_straight_wg_simulation()

        def test_mode_monitor_helpers(self):
            mpa.utils.register_monitors(self.monitors, self.frequencies)
            self.simulation.run(until=100)
            monitor_values = mpa.utils.gather_monitor_values(self.monitors)
            self.assertEqual(monitor_values.dtype, onp.complex128)
            self.assertEqual(
                monitor_values.shape, (len(self.monitors), len(self.frequencies))
            )

        def test_dist_dft_pointers(self):
            fwd_design_region_monitors = mpa.utils.install_design_region_monitors(
                self.simulation,
                self.design_regions,
                self.frequencies,
            )
            self.assertEqual(len(fwd_design_region_monitors[0]), _NUM_DES_REG_MON)
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
