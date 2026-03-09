# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys, os
os.makedirs('/tmp/kb_results', exist_ok=True)

if '__file__' not in dir():
    __file__ = '/tmp/typeb_597.py'

_fig_count = [0]
_orig_show = plt.show
def _patched_show(*a, **kw):
    _n = _fig_count[0]
    plt.savefig('/tmp/kb_results/typeb_597_%02d.png' % _n, dpi=80, bbox_inches='tight')
    _fig_count[0] += 1
    plt.close('all')
plt.show = _patched_show

"""Topology optimization of a waveguide mode converter.

The worst-case optimization is based on minimizing the maximum of {R, 1-T} where
R (reflectance) is $|S_{11}|^2$ for mode 1 and T (transmittance) is $|S_{21}|^2$
for mode 2 across six different wavelengths. The optimization uses the
Conservative Convex Separable Approximation (CCSA) algorithm from NLopt.

The minimum linewidth constraint is adapted from A.M. Hammond et al.,
Optics Express, Vol. 29, pp. 23916-23938, (2021). doi.org/10.1364/OE.431188
"""

from typing import List, NamedTuple, Tuple

from autograd import numpy as npa, tensor_jacobian_product, grad
import matplotlib.pyplot as plt
import meep as mp
import meep.adjoint as mpa
import nlopt
import numpy as np


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


def epigraph_constraint(
    result: np.ndarray,
    epigraph_and_weights: np.ndarray,
    gradient: np.ndarray,
    sigmoid_threshold: float,
    sigmoid_bias: float,
    use_epsavg: bool,
) -> None:
    """Constraint function for the epigraph formulation.

    Args:
      result: evaluation of this constraint function, modified in place.
      epigraph_and_weights: 1D array containing the epigraph variable (first
        element) and design weights (remaining elements).
      gradient: the Jacobian matrix with dimensions (1 + NX_DESIGN_GRID *
        NY_DESIGN_GRID, 2 * num. wavelengths), modified in place.
      sigmoid_threshold: erosion/dilation parameter for projection.
      sigmoid_bias: bias parameter for projection.
      use_epsavg: whether to use subpixel smoothing.
    """
    epigraph = epigraph_and_weights[0]
    weights = epigraph_and_weights[1:]

    obj_val, grad = opt(
        [
            filter_and_project(
                weights, sigmoid_threshold, 0 if use_epsavg else sigmoid_bias
            )
        ]
    )

    reflectance = obj_val[0]
    transmittance = obj_val[1]
    obj_val_merged = np.concatenate((reflectance, transmittance))
    obj_val_merged_str = str_from_list(obj_val_merged)

    grad_reflectance = grad[0]
    grad_transmittance = grad[1]
    grad = np.zeros((NX_DESIGN_GRID * NY_DESIGN_GRID, 2 * num_wavelengths))
    grad[:, :num_wavelengths] = grad_reflectance
    grad[:, num_wavelengths:] = grad_transmittance

    # Backpropagate the gradients through the filter and project function.
    for k in range(2 * num_wavelengths):
        grad[:, k] = tensor_jacobian_product(filter_and_project, 0)(
            weights,
            sigmoid_threshold,
            sigmoid_bias,
            grad[:, k],
        )

    if gradient.size > 0:
        gradient[:, 0] = -1  # gradient w.r.t. epigraph variable
        gradient[:, 1:] = grad.T  # gradient w.r.t. each frequency objective

    result[:] = np.real(obj_val_merged) - epigraph

    objfunc_history.append(np.real(obj_val_merged))
    epivar_history.append(epigraph)

    print(
        f"iteration:, {cur_iter[0]:3d}, sigmoid_bias: {sigmoid_bias:2d}, "
        f"epigraph: {epigraph:.5f}, obj. func.: {obj_val_merged_str}, "
        f"epigraph constraint: {str_from_list(result)}"
    )

    cur_iter[0] = cur_iter[0] + 1
