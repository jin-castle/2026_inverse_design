#!/usr/bin/env python3
"""
Pattern: adjoint_multilayer_optimization
Multilayer thin film adjoint optimization: 1D multilayer, reflectance minimization, structural parameter gradient
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "adjoint_multilayer_optimization"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    """Shape optimization of a multilayer stack over a broad bandwidth.

    The 1D stack consists of alternating materials of index N_LAYER_1 and N_LAYER_2
    in the arrangement: N_LAYER_2, N_LAYER_1, N_LAYER_2, N_LAYER_1, ..., N_LAYER_2.

    The design parameters are the N layer thicknesses: [t_1, t_2, ..., t_N]. N must
    be odd.

    The design objective involves minimizing the largest integral of the DFT fields
    in the multilayer stack over two wavelengths (worst-case optimization).

    Tutorial Reference:
    https://meep.readthedocs.io/en/latest/Python_Tutorials/Adjoint_Solver/#shape-optimization-of-a-multilayer-stack
    """

    import copy
    from typing import Callable, List, Tuple

    import nlopt

    RESOLUTION_UM = 800
    AIR_UM = 1.0
    PML_UM = 1.0
    NUM_LAYERS = 9
    N_LAYER = (1.0, 1.3)
    LAYER_PERTURBATION_UM = 1.0 / RESOLUTION_UM
    DESIGN_WAVELENGTHS_UM = (0.95, 1.05)
    MAX_LAYER_UM = max(DESIGN_WAVELENGTHS_UM) / (4 * min(N_LAYER))
    DESIGN_REGION_RESOLUTION_UM = 10 * RESOLUTION_UM
    DESIGN_REGION_UM = mp.Vector3(0, 0, NUM_LAYERS * MAX_LAYER_UM)
    NZ_DESIGN_GRID = int(DESIGN_REGION_UM.z * DESIGN_REGION_RESOLUTION_UM) + 1
    NZ_SIM_GRID = int(DESIGN_REGION_UM.z * RESOLUTION_UM) + 1
    MAX_OPT_ITERATIONS = 30
    NUM_OPT_REPEAT = 10

    num_wavelengths = len(DESIGN_WAVELENGTHS_UM)
    frequencies = [1 / wavelength_um for wavelength_um in DESIGN_WAVELENGTHS_UM]

    def str_from_list(list_: List[float]) -> str:
        return "[" + ", ".join(f"{val:.4f}" for val in list_) + "]"

    def design_region_to_grid(nz: int) -> np.ndarray:
        """Returns the coordinates of the 1D grid for the design region.

        Args:
          nz: number of grid points.

        Returns:
          The 1D coordinates of the grid points.
        """
        z_grid = np.linspace(-0.5 * DESIGN_REGION_UM.z, 0.5 * DESIGN_REGION_UM.z, nz)

        return z_grid

    @primitive
    def levelset_and_smoothing(layer_thickness_um: np.ndarray) -> np.ndarray:
        """Returns the density weights for a multilayer stack as a levelset.

        Args:
          layer_thickness_um: thickness of each layer in the stack.

        Returns:
          The density weights as a flattened (1D) array.
        """
        air_padding_um = 0.5 * (DESIGN_REGION_UM.z - np.sum(layer_thickness_um))

        weights = np.zeros(NZ_DESIGN_GRID)

        # Air padding at left edge
        z_start = 0
        z_end = int(air_padding_um * DESIGN_REGION_RESOLUTION_UM)
        weights[z_start:z_end] = 0

        z_start = z_end
        for j in range(NUM_LAYERS):
            z_end = z_start + int(layer_thickness_um[j] * DESIGN_REGION_RESOLUTION_UM)
            weights[z_start:z_end] = 1 if (j % 2 == 0) else 0
            z_start = z_end

        # Air padding at right edge
        z_end = z_start + int(air_padding_um * DESIGN_REGION_RESOLUTION_UM)
        weights[z_start:z_end] = 0

        # Smooth the design weights by downsampling from the design grid
        # to the simulation grid using bilinear interpolation.
        z_sim_grid = design_region_to_grid(NZ_SIM_GRID)
        z_design_grid = design_region_to_grid(NZ_DESIGN_GRID)
        smoothed_weights = np.interp(z_sim_grid, z_design_grid, weights)

        return smoothed_weights.flatten()

    def levelset_and_smoothing_vjp(
        ans: np.ndarray, layer_thickness_um: np.ndarray
    ) -> Callable[[np.ndarray], np.ndarray]:
        """Returns a function for computing the vector-Jacobian product."""

        total_layer_thickness_um = np.sum(layer_thickness_um)
        air_padding_um = 0.5 * (DESIGN_REGION_UM.z - total_layer_thickness_um)

        jacobian = np.zeros((NZ_SIM_GRID, NUM_LAYERS))

        z_design_grid = design_region_to_grid(NZ_DESIGN_GRID)
        z_sim_grid = design_region_to_grid(NZ_SIM_GRID)

        for i in range(NUM_LAYERS):
            weights = np.zeros(NZ_DESIGN_GRID)

            # Air padding at left edge
            z_start = 0
            z_end = int(air_padding_um * DESIGN_REGION_RESOLUTION_UM)
            weights[z_start:z_end] = 0

            z_start = z_end
            for j in range(NUM_LAYERS):
                layer_um = layer_thickness_um[j]
                if j == i:
                    layer_um += LAYER_PERTURBATION_UM
                z_end = z_start + int(layer_um * DESIGN_REGION_RESOLUTION_UM)
                weights[z_start:z_end] = 1 if (j % 2 == 0) else 0
                z_start = z_end

            # Air padding at right edge
            z_end = z_start + int(air_padding_um * DESIGN_REGION_RESOLUTION_UM)
            weights[z_start:z_end] = 0

            # Smooth the design weights by downsampling from the design grid
            # to the simulation grid using bilinear interpolation.
            smoothed_weights = np.interp(z_sim_grid, z_design_grid, weights)

            jacobian[:, i] = (smoothed_weights - ans) / LAYER_PERTURBATION_UM

        return lambda g: np.tensordot(g, jacobian, axes=1)

    def multilayer_stack() -> mpa.OptimizationProblem:
        """Sets up the adjoint optimization of a multilayer stack.

        Returns:
          A `meep.adjoint.Optimization` callable object.
        """
        pml_layers = [mp.PML(thickness=PML_UM)]

        size_z_um = PML_UM + AIR_UM + DESIGN_REGION_UM.z + AIR_UM + PML_UM
        cell_size = mp.Vector3(0, 0, size_z_um)

        frequency_center = np.mean(frequencies)

        # Set source bandwidth to be larger than the range of design wavelengths.
        frequency_width = 1.2 * (np.max(frequencies) - np.min(frequencies))

        src_cmpt = mp.Ex
        src_pt = mp.Vector3(0, 0, -0.5 * size_z_um + PML_UM)
        sources = [
            mp.Source(
                mp.GaussianSource(frequency_center, fwidth=frequency_width),
                component=src_cmpt,
                center=src_pt,
            )
        ]

        mat_1 = mp.Medium(index=N_LAYER[0])
        mat_2 = mp.Medium(index=N_LAYER[1])

        matgrid = mp.MaterialGrid(
            mp.Vector3(0, 0, NZ_SIM_GRID),
            mat_1,
            mat_2,
            weights=np.ones(NZ_SIM_GRID),
            do_averaging=False,
        )

        matgrid_region = mpa.DesignRegion(
            matgrid,
            volume=mp.Volume(center=mp.Vector3(), size=DESIGN_REGION_UM),
        )
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
