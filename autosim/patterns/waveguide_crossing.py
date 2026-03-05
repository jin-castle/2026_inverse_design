#!/usr/bin/env python3
"""
Pattern: waveguide_crossing
Waveguide crossing: X-junction transmittance, 4-port S-parameter, crossing loss measurement
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "waveguide_crossing"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    """waveguide_crossing.py - Using meep's adjoint solver, designs a waveguide
    crossing that maximizes transmission at a single frequency.

    Two approaches are demonstrated: (1) start with the nominal crossing shape and
    perform shape optimization via meep's smoothed projection feature; (2) run a
    full topology optimization starting from an initial grayscale. Evolve the design
    until β=∞.

    Importantly, this particular example highlights some of the ways one can use the
    novel smoothed projection function to perform both shape and topology
    optimization.
    """

    from typing import Callable, List, Optional, Tuple

    import nlopt

    mp.quiet()

    DEFAULT_MIN_LENGTH = 0.09
    DEFAULT_DESIGN_REGION_WIDTH = 3.0
    DEFAULT_DESIGN_REGION_HEIGHT = 3.0
    DEFAULT_WAVEGUIDE_WIDTH = 0.5
    DEFAULT_ETA = 0.5
    DEFAULT_ETA_E = 0.75
    DEFAULT_MAX_EVAL = 30

    def build_optimization_problem(
        resolution: float,
        beta: float,
        use_smoothed_projection: bool,
        min_length: float = DEFAULT_MIN_LENGTH,
        dx: float = DEFAULT_DESIGN_REGION_WIDTH,
        dy: float = DEFAULT_DESIGN_REGION_HEIGHT,
        waveguide_width: float = DEFAULT_WAVEGUIDE_WIDTH,
        eta: float = DEFAULT_ETA,
        eta_e: float = DEFAULT_ETA_E,
        damping_factor: float = 0.0,
    ) -> Tuple[mpa.OptimizationProblem, Callable]:
        """Build the waveguide-crossing optimization problem.

        The waveguide crossing is a cononical inverse design problem with both
        shape- and topology-optimization implementations. The idea is to find the
        optimal structure that maximizes transmission from one side to the other. It
        exhibits C4 symmetry, and generally resembles the following structure:

             |  |
             |  |
        -----    ------
        -----    ------
             |  |
             |  |

        Args:
            resolution: Simulation resolution in pixels/micron.
            beta: Tanh function projection strength parameter, ranging from [0,∞].
            use_smoothed_projection: Whether or not to use the smoothed projection.
            min_length: Minimum length scale in microns.
            dx: Design region width in microns.
            dy: Design region height in microns.
            waveguide_width: Waveguide width in microns.
            eta: Projection function threshold parameter.
            eta_e: Projection function eroded threshold parameter.
            damping_factor: The material grid damping scalar factor.

        Returns:
            The corresponding optimization problem object and the mapping function
            that applies the linear and nonlinear transformations.
        """
        # Map the design region resolution to the yee grid, which is twice the standard resolution.
        design_region_resolution = int(2 * resolution)

        # pml thickness
        dpml = 1.0

        filter_radius = mpa.get_conic_radius_from_eta_e(min_length, eta_e)

        sxy = dx + 1 + 2 * dpml

        silicon = mp.Medium(epsilon=12)
        cell_size = mp.Vector3(sxy, sxy, 0)
        boundary_layers = [mp.PML(thickness=dpml)]

        eig_parity = mp.EVEN_Y + mp.ODD_Z

        design_region_size = mp.Vector3(dx, dy)
        Nx = int(design_region_resolution * design_region_size.x) + 1
        Ny = int(design_region_resolution * design_region_size.y) + 1

        waveguide_geometry = [
            mp.Block(material=silicon, size=mp.Vector3(mp.inf, waveguide_width, mp.inf)),
            mp.Block(material=silicon, size=mp.Vector3(waveguide_width, mp.inf, mp.inf)),
        ]

        # Source centered in optical c-band
        fcen = 1 / 1.55
        df = 0.23 * fcen
        sources = [
            mp.EigenModeSource(
                src=mp.GaussianSource(fcen, fwidth=df),
                center=mp.Vector3(-0.5 * sxy + dpml + 0.1, 0),
                size=mp.Vector3(0, sxy - 2 * dpml),
                eig_band=1,
                eig_parity=eig_parity,
            )
        ]

        damping = damping_factor * fcen
        matgrid = mp.MaterialGrid(
            mp.Vector3(Nx, Ny),
            mp.air,
            silicon,
            weights=np.ones((Nx, Ny)),
            beta=0,  # disable meep's internal smoothing
            do_averaging=False,  # disable meep's internal mg smoothing
            damping=damping,
        )

        matgrid_region = mpa.DesignRegion(
            matgrid,
            volume=mp.Volume(
                center=mp.Vector3(),
                size=mp.Vector3(design_region_size.x, design_region_size.y, 0),
            ),
        )

        matgrid_geometry = [
            mp.Block(
                center=matgrid_region.center, size=matgrid_region.size, material=matgrid
            )
        ]

        geometry = waveguide_geometry + matgrid_geometry

        sim = mp.Simulation(
            resolution=resolution,
            cell_size=cell_size,
            boundary_layers=boundary_layers,
            sources=sources,
            geometry=geometry,
        )

        frequencies = [fcen]

        obj_list = [
            mpa.EigenmodeCoefficient(
                sim,
                mp.Volume(
                    center=mp.Vector3(-0.5 * sxy + dpml + 0.2),
                    size=mp.Vector3(0, sxy - 2 * dpml, 0),
                ),
                1,
                eig_parity=eig_parity,
            ),
            mpa.EigenmodeCoefficient(
                sim,
                mp.Volume(
                    center=mp.Vector3(0.5 * sxy - dpml - 0.2),
                    size=mp.Vector3(0, sxy - 2 * dpml, 0),
                ),
                1,
                eig_parity=eig_parity,
            ),
        ]

        def J(input, output):
            """Simple objective function to minimize loss."""
            return 1 - npa.power(npa.abs(output / input), 2)

        opt = mpa.OptimizationProblem(
            simulation=sim,
            maximum_run_time=500,
            objective_functions=J,
            objective_arguments=obj_list,
            design_regions=[matgrid_region],
            frequencies=frequencies,
        )

        def mapping(x: npa.ndarray):
            """Applies the smoothing and projection."""
            x = x.reshape(Nx, Ny)
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
