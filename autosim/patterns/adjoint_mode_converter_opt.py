#!/usr/bin/env python3
"""
Pattern: adjoint_mode_converter_opt
Complete adjoint optimization for TE0-to-TE1 mode converter. Design region between tapered waveguides, EigenmodeCoeffici
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "adjoint_mode_converter_opt"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    """Topology optimization of a waveguide mode converter.

    The worst-case optimization is based on minimizing the maximum of {R, 1-T} where
    R (reflectance) is $|S_{11}|^2$ for mode 1 and T (transmittance) is $|S_{21}|^2$
    for mode 2 across six different wavelengths. The optimization uses the
    Conservative Convex Separable Approximation (CCSA) algorithm from NLopt.

    The minimum linewidth constraint is adapted from A.M. Hammond et al.,
    Optics Express, Vol. 29, pp. 23916-23938, (2021). doi.org/10.1364/OE.431188
    """

    from typing import List, NamedTuple, Tuple

    import nlopt

    RESOLUTION_UM = 50
    WAVELENGTH_MIN_UM = 1.26
    WAVELENGTH_MAX_UM = 1.30
    WAVEGUIDE_UM = mp.Vector3(3.0, 0.4, 0)
    PADDING_UM = 0.6
    PML_UM = 1.0
    DESIGN_WAVELENGTHS_UM = (1.265, 1.270, 1.275, 1.285, 1.290, 1.295)
    DESIGN_REGION_UM = mp.Vector3(1.6, 1.6, mp.inf)
    DESIGN_REGION_RESOLUTION_UM = int(2 * RESOLUTION_UM)
    NX_DESIGN_GRID = int(DESIGN_REGION_UM.x * DESIGN_REGION_RESOLUTION_UM) + 1
    NY_DESIGN_GRID = int(DESIGN_REGION_UM.y * DESIGN_REGION_RESOLUTION_UM) + 1
    MIN_LENGTH_UM = 0.15
    SIGMOID_THRESHOLD_INTRINSIC = 0.5
    SIGMOID_THRESHOLD_EROSION = 0.75
    SIGMOID_THRESHOLD_DILATION = 1 - SIGMOID_THRESHOLD_EROSION
    MODE_SYMMETRY = mp.ODD_Z
    SILICON = mp.Medium(index=3.5)
    SILICON_DIOXIDE = mp.Medium(index=1.5)

    cell_um = mp.Vector3(
        PML_UM + WAVEGUIDE_UM.x + DESIGN_REGION_UM.x + WAVEGUIDE_UM.x + PML_UM,
        PML_UM + PADDING_UM + DESIGN_REGION_UM.y + PADDING_UM + PML_UM,
        0,
    )
    filter_radius_um = mpa.get_conic_radius_from_eta_e(
        MIN_LENGTH_UM, SIGMOID_THRESHOLD_EROSION
    )
    frequency_min = 1 / WAVELENGTH_MAX_UM
    frequency_max = 1 / WAVELENGTH_MIN_UM
    frequency_center = 0.5 * (frequency_min + frequency_max)
    frequency_width = frequency_max - frequency_min
    pml_layers = [mp.PML(thickness=PML_UM)]
    frequencies = [1 / wavelength_um for wavelength_um in DESIGN_WAVELENGTHS_UM]
    num_wavelengths = len(DESIGN_WAVELENGTHS_UM)
    src_pt = mp.Vector3(-0.5 * cell_um.x + PML_UM, 0, 0)
    refl_pt = mp.Vector3(-0.5 * cell_um.x + PML_UM + 0.5 * WAVEGUIDE_UM.x)
    tran_pt = mp.Vector3(0.5 * cell_um.x - PML_UM - 0.5 * WAVEGUIDE_UM.x)
    stop_cond = mp.stop_when_fields_decayed(50, mp.Ez, refl_pt, 1e-6)

    def str_from_list(list_: List[float]) -> str:
        return "[" + ", ".join(f"{val:.4f}" for val in list_) + "]"

    def border_masks() -> Tuple[np.ndarray, np.ndarray]:
        """Return border masks for the design region.

        The masks are used to prevent violations on constraints on the
        minimum feature size at the boundaries of the design region.

        Returns:
          A 2-tuple of 2D arrays for border masks for Si and SiO2.
        """
        x_grid = np.linspace(
            -DESIGN_REGION_UM.x / 2,
            DESIGN_REGION_UM.x / 2,
            NX_DESIGN_GRID,
        )
        y_grid = np.linspace(
            -DESIGN_REGION_UM.y / 2,
            DESIGN_REGION_UM.y / 2,
            NY_DESIGN_GRID,
        )
        xy_grid_x, xy_grid_y = np.meshgrid(
            x_grid,
            y_grid,
            sparse=True,
            indexing="ij",
        )

        left_waveguide_port = (xy_grid_x <= -DESIGN_REGION_UM.x / 2 + filter_radius_um) & (
            np.abs(xy_grid_y) <= WAVEGUIDE_UM.y / 2
        )
        right_waveguide_port = (xy_grid_x >= DESIGN_REGION_UM.x / 2 - filter_radius_um) & (
            np.abs(xy_grid_y) <= WAVEGUIDE_UM.y / 2
        )
        silicon_mask = left_waveguide_port | right_waveguide_port

        border_mask = (
            (xy_grid_x <= -DESIGN_REGION_UM.x / 2 + filter_radius_um)
            | (xy_grid_x >= DESIGN_REGION_UM.x / 2 - filter_radius_um)
            | (xy_grid_y <= -DESIGN_REGION_UM.y / 2 + filter_radius_um)
            | (xy_grid_y >= DESIGN_REGION_UM.y / 2 - filter_radius_um)
        )
        silicon_dioxide_mask = border_mask.copy()
        silicon_dioxide_mask[silicon_mask] = False

        return silicon_mask, silicon_dioxide_mask

    def filter_and_project(
        weights: np.ndarray, sigmoid_threshold: float, sigmoid_bias: float
    ) -> np.ndarray:
        """A differentiable function to filter and project the design weights.

        Args:
          weights: design weights as a flattened (1D) array.
          sigmoid_threshold: erosion/dilation parameter for the projection.
          sigmoid_bias: bias parameter for the projection. 0 is no projection.

        Returns:
          The mapped design weights as a 1D array.
        """
        silicon_mask, silicon_dioxide_mask = border_masks()

        weights_masked = npa.where(
            silicon_mask.flatten(),
            1,
            npa.where(
                silicon_dioxide_mask.flatten(),
                0,
                weights,
            ),
        )

        weights_filtered = mpa.conic_filter(
            weights_masked,
            filter_radius_um,
            DESIGN_REGION_UM.x,
            DESIGN_REGION_UM.y,
            DESIGN_REGION_RESOLUTION_UM,
        )

        if sigmoid_bias == 0:
            return weights_filtered.flatten()
        else:
            weights_projected = mpa.tanh_projection(
                weights_filtered,
                sigmoid_bias,
                sigmoid_threshold,
            )
            return weights_projected.flatten()

    def obj_func(epigraph_and_weights: np.ndarray, grad: np.ndarray) -> float:
        """Objective function for the epigraph formulation.

        Args:
          epigraph_and_weights: 1D array containing epigraph variable (first
            element) and design weights (remaining elements).
          grad: the gradient as a flattened (1D) array, modified in place.

        Returns:
          The scalar epigraph variable.
        """
        epigraph = epigraph_and_weights[0]

        if grad.size > 0:
            grad[0] = 1
            grad[1:] = 0

        return epigraph
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
