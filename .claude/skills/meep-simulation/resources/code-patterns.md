# Code Patterns from Photonics Research Groups

_자동 생성 (meep-kb DB)_

## NanoComp/meep: python/materials.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
# Materials Library
import numpy as np

import meep as mp

# default unit length is 1 μm
um_scale = 1.0

# conversion factor for eV to 1/μm [=1/hc]
eV_um_scale = um_scale / 1.23984193

# ------------------------------------------------------------------
# crystalline silicon (c-Si) from A. Deinega et al., J. Optical Society of America A, Vol. 28, No. 5, pp. 770-77 (2011)
# based on experimental data for intrinsic silicon at T=300K from M.A. Green and M. Keevers, Progress in Photovoltaics, Vol. 3, pp. 189-92 (1995)
# wavelength range: 0.4 - 1.0 μm

cSi_range = mp.FreqRange(min=um_scale, max=um_
```

## NanoComp/meep: python/chunk_balancer.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import abc
import copy
from typing import Optional, Tuple, Union

import numpy as np
from meep.timing_measurements import MeepTimingMeasurements

import meep as mp
from meep import binary_partition_utils as bpu


class AbstractChunkBalancer(abc.ABC):
    """Abstract chunk balancer for adaptive chunk layouts in Meep simulations.

    This class defines interfaces for a chunk balancer, which adjusts chunk
    layouts to optimal load balancing. It provides two main functionalities:
      1. Generating an initial chunk layout for the first iteration of an
         optimization run, using a strateg
```

## NanoComp/meep: python/timing_measurements.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
from typing import Dict, List, Optional

import numpy as np

import meep as mp

# Codes for different Meep time sinks, used by `mp.Simulation.time_spent_on()`.
# See
# https://meep.readthedocs.io/en/latest/Python_User_Interface/#simulation-time
# for more information.
TIMING_MEASUREMENT_IDS = {
    "connecting_chunks": mp.Connecting,
    "time_stepping": mp.Stepping,
    "boundaries_copying": mp.Boundaries,
    "mpi_all_to_all": mp.MpiAllTime,
    "mpi_one_to_one": mp.MpiOneTime,
    "field_output": mp.FieldOutput,
    "fourier_transform": mp.FourierTransforming,
    "mpb": mp.MPBTime,
    "ne
```

## NanoComp/meep: python/source.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,mode-source,official,waveguide`

MEEP official examples & tests

```python
import warnings
import functools

import numpy as np

from meep.geom import Vector3, check_nonnegative

import meep as mp


def check_positive(prop, val):
    if val > 0:
        return val
    else:
        raise ValueError(f"{prop} must be positive. Got {val}")


class Source:
    """
    The `Source` class is used to specify the current sources via the `Simulation.sources`
    attribute. Note that all sources in Meep are separable in time and space, i.e. of the
    form $\\mathbf{J}(\\mathbf{x},t) = \\mathbf{A}(\\mathbf{x}) \\cdot f(t)$ for some functions
    $\\mathbf{A}$ and $f$. Non-sepa
```

## NanoComp/meep: python/binary_partition_utils.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import warnings
from typing import Dict, Generator, List, Tuple

import numpy as onp

import meep as mp


def is_leaf_node(partition: mp.BinaryPartition) -> bool:
    """Returns True if the partition has no children.

    Args:
      partition: the BinaryPartition node

    Returns:
      A boolean indicating whether partition is a leaf node.
    """
    return partition.left is None and partition.right is None


def enumerate_leaf_nodes(
    partition: mp.BinaryPartition,
) -> Generator[mp.BinaryPartition, None, None]:
    """Enumerates all leaf nodes of a partition.

    Args:
      partitio
```

## NanoComp/meep: python/verbosity_mgr.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
class Verbosity:
    """
    A class to help make accessing and setting the global verbosity level a bit
    more pythonic. It manages one or more verbosity flags that are located in
    the C/C++ libraries used by Meep.

    The verbosity levels are:

    * 0: minimal output
    * 1: a little
    * 2: a lot
    * 3: debugging

    An instance of `Verbosity` is created when meep is imported, and is
    accessible as `meep.verbosity`. The `meep.mpb` package also has a verbosity
    flag in its C library, and it can also be managed via the `Verbosity` class
    after `meep.mpb` is imported.
```

## NanoComp/meep: python/mpb_data.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,mpb,official`

MEEP official examples & tests

```python
import math

import numpy as np

import meep as mp

from . import MPBArray, map_data


class MPBData:

    TWOPI = 6.2831853071795864769252867665590057683943388

    def __init__(
        self,
        lattice=None,
        kpoint=None,
        rectify=False,
        x=0,
        y=0,
        z=0,
        periods=0,
        resolution=0,
        phase_angle=0,
        pick_nearest=False,
        ve=None,
        verbose=False,
    ):

        self.lattice = lattice
        self.kpoint = kpoint
        self.rectify = rectify

        if periods:
            self.multiply_size = [periods, period
```

## NanoComp/meep: python/visualization.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,mode-source,official,topology-optimization`

MEEP official examples & tests

```python
from collections import namedtuple
import warnings
import copy

from time import sleep

import matplotlib.pyplot as plt
import numpy as np

import meep as mp
from meep.geom import Vector3, init_do_averaging
from meep.source import EigenModeSource, check_positive
from meep.simulation import Simulation, Volume

## Typing imports
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from typing import Callable, Union, Any, Tuple, List, Optional


# ------------------------------------------------------- #
# Visualization
# ------------------------------------------------------- #
```

## NanoComp/meep: python/geom.py
**Source:** `NanoComp/meep` | **Tags:** `adjoint,fdtd,meep,meep-adjoint,official`

MEEP official examples & tests

```python
"""
A collection of geometry- and material-related objects and helper routines.
"""

from __future__ import annotations

from collections import namedtuple
from copy import deepcopy
import functools
import math
from numbers import Number
import operator
from typing import List, NamedTuple, Optional, Tuple, Union
import warnings

import numpy as np
import meep as mp

FreqRange = namedtuple("FreqRange", ["min", "max"])


def check_nonnegative(prop, val):
    if val >= 0:
        return val
    else:
        raise ValueError(f"{prop} cannot be negative. Got {val}")


def init_do_averaging(mat_fun
```

## NanoComp/meep: python/solver.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,mpb,official,optimization`

MEEP official examples & tests

```python
import functools
import math
import numbers
import os
import re
import sys
import time

import h5py
import numpy as np
from meep.geom import init_do_averaging
from meep.simulation import get_num_args
from meep.verbosity_mgr import Verbosity

import meep as mp

from . import mode_solver, with_hermitian_epsilon

try:
    basestring
except NameError:
    basestring = str

U_MIN = 0
U_PROD = 1
U_MEAN = 2

verbosity = Verbosity(mp.cvar, "meep", 1)


class MPBArray(np.ndarray):
    def __new__(cls, input_array, lattice, kpoint=None, bloch_phase=False):
        # Input array is an already formed ndar
```

## NanoComp/meep: python/tests/test_ldos.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest
import numpy as np
import meep as mp


class TestLDOS(unittest.TestCase):
    @classmethod
    def setUp(cls):
        cls.resolution = 25  # pixels/μm
        cls.dpml = 0.5  # thickness of PML
        cls.dair = 1.0  # thickness of air padding
        cls.L = 6.0  # length of non-PML region
        cls.n = 2.4  # refractive index of surrounding medium
        cls.wvl = 1.0  # wavelength (in vacuum)

        cls.fcen = 1 / cls.wvl

        # termination criteria
        cls.tol = 1e-8

    def bulk_ldos_cyl(self):
        """Computes the LDOS of a point dipole in a homogeneous
```

## NanoComp/meep: python/tests/test_dft_energy.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,mode-source,official,waveguide`

MEEP official examples & tests

```python
import unittest

import meep as mp

# compute group velocity of a waveguide mode using two different methods
# (1) ratio of Poynting flux to energy density
# (2) via MPB from get-eigenmode-coefficients


class TestDftEnergy(unittest.TestCase):
    def test_dft_energy(self):
        resolution = 20
        cell = mp.Vector3(10, 5)
        geom = [
            mp.Block(size=mp.Vector3(mp.inf, 1, mp.inf), material=mp.Medium(epsilon=12))
        ]
        pml = [mp.PML(1)]
        fsrc = 0.15
        sources = [
            mp.EigenModeSource(
                src=mp.GaussianSource(frequency=fsrc,
```

## NanoComp/meep: python/tests/test_pml_cyl.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest
import parameterized
import numpy as np
import meep as mp


class TestPMLCylindrical(unittest.TestCase):
    @classmethod
    def setUp(cls):
        cls.resolution = 25  # pixels/um
        cls.s = 5.0
        cls.dpml_r = 1.0
        cls.dpml_z = 1.0
        cls.cell_size = mp.Vector3(
            cls.s + cls.dpml_r,
            0,
            cls.s + 2 * cls.dpml_z,
        )
        cls.fcen = 1.0

    @parameterized.parameterized.expand(
        [
            (0.0, 0.04, False),
            (-1.0, 0, False),
            (2.0, 0.14, False),
            (3.0, 0.17, True),
```

## NanoComp/meep: python/tests/test_source.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,mode-source,official`

MEEP official examples & tests

```python
import math
import os
import unittest

import numpy as np
from meep.geom import Cylinder, Vector3
from meep.source import ContinuousSource, EigenModeSource, GaussianSource, Source

import meep as mp

data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "data"))


class TestEigenModeSource(unittest.TestCase):
    def test_amp_func_change_sources(self):
        src = ContinuousSource(5.0)
        center = Vector3()
        size = Vector3(0, 1, 0)

        ampfunc = lambda X: 1.0
        amp_source = [
            Source(src, component=mp.Ez, center=center, size=size, amp_func=ampfu
```

## NanoComp/meep: python/tests/test_ring_cyl.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest

from utils import ApproxComparisonTestCase

import meep as mp


class TestRingCyl(ApproxComparisonTestCase):
    def setUp(self):
        n = 3.4
        w = 1
        self.r = 1
        pad = 4
        dpml = 2
        sr = self.r + w + pad + dpml
        dimensions = mp.CYLINDRICAL
        cell = mp.Vector3(sr, 0, 0)
        m = 3

        geometry = [
            mp.Block(
                center=mp.Vector3(self.r + (w / 2)),
                size=mp.Vector3(w, mp.inf, mp.inf),
                material=mp.Medium(index=n),
            )
        ]

        pml_layers = [mp.PML(
```

## NanoComp/meep: python/tests/test_visualization.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official,waveguide`

MEEP official examples & tests

```python
# visualization.py - Tests the visualization module. Checks 2D
# plotting of a waveguide with several sources, monitors, and
# boundary conditions. Checks for subdomain plots.
#
# Also tests the animation run function, mp4 output, jshtml output, and git output.
import os
import unittest
from subprocess import call

import matplotlib
import numpy as np

import meep as mp

# Make sure we have matplotlib installed

matplotlib.use("agg")  # Set backend for consistency and to pull pixels quickly
import io

from matplotlib import pyplot as plt


def hash_figure(fig):
    buf = io.BytesIO()
    fig.s
```

## NanoComp/meep: python/tests/test_cavity_farfield.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import os
import unittest

import h5py
from utils import ApproxComparisonTestCase

import meep as mp


class TestCavityFarfield(ApproxComparisonTestCase):

    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "data"))

    def run_test(self, nfreqs):
        eps = 13
        w = 1.2
        r = 0.36
        d = 1.4
        N = 3
        sy = 6
        pad = 2
        dpml = 1
        sx = 2 * (pad + dpml + N) + d - 1

        cell = mp.Vector3(sx, sy, 0)

        geometry = [
            mp.Block(
                center=mp.Vector3(),
                size=mp.Vector3(mp.inf, w,
```

## NanoComp/meep: python/tests/test_field_functions.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest

import meep as mp


def f(r, ex, hz, eps):
    return (r.x * r.norm() + ex) - (eps * hz)


def f2(r, ez1, ez2):
    return ez1.conjugate() * ez2


class TestFieldFunctions(unittest.TestCase):

    cs = [mp.Ex, mp.Hz, mp.Dielectric]
    vol = mp.Volume(size=mp.Vector3(1), center=mp.Vector3())

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = mp.make_output_directory()

    @classmethod
    def tearDownClass(cls):
        mp.delete_directory(cls.temp_dir)

    def init(self):
        resolution = 20

        cell = mp.Vector3(10, 10, 0)

        pml_layers = mp.P
```

## NanoComp/meep: python/tests/test_cyl_ellipsoid.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest

import meep as mp


def dummy_eps(vec):
    return 1.0


class TestCylEllipsoid(unittest.TestCase):

    ref_Ez = -8.29555720049629e-5
    ref_Hz = -4.5623185899766e-5

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = mp.make_output_directory()

    @classmethod
    def tearDownClass(cls):
        mp.delete_directory(cls.temp_dir)

    def init(self):

        c = mp.Cylinder(radius=3, material=mp.Medium(index=3.5))
        e = mp.Ellipsoid(size=mp.Vector3(1, 2, mp.inf))

        sources = mp.Source(
            src=mp.GaussianSource(1, fwidth=0.1),
```

## NanoComp/meep: python/tests/test_refl_angular.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import math
from typing import List, Tuple
import unittest

import numpy as np
import parameterized
from utils import ApproxComparisonTestCase

import meep as mp


class TestReflectanceAngular(ApproxComparisonTestCase):
    @classmethod
    def setUpClass(cls):
        cls.resolution = 200  # pixels/μm

        cls.n1 = 1.4  # refractive index of medium 1
        cls.n2 = 3.5  # refractive index of medium 2

        cls.t_pml = 1.0
        cls.length_z = 7.0
        cls.size_z = cls.length_z + 2 * cls.t_pml

        cls.wavelength_min = 0.4
        cls.wavelength_max = 0.8
        cls.frequenc
```

## NanoComp/meep: python/tests/test_material_dispersion.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest

import numpy as np

import meep as mp


class TestMaterialDispersion(unittest.TestCase):
    def test_material_dispersion_with_user_material(self):
        susceptibilities = [
            mp.LorentzianSusceptibility(frequency=1.1, gamma=1e-5, sigma=0.5),
            mp.LorentzianSusceptibility(frequency=0.5, gamma=0.1, sigma=2e-5),
        ]

        def mat_func(p):
            return mp.Medium(epsilon=2.25, E_susceptibilities=susceptibilities)

        fcen = 1.0
        df = 2.0

        sources = mp.Source(
            mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
```

## NanoComp/meep: python/tests/test_mpb.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,mpb,official,optimization`

MEEP official examples & tests

```python
import math
import os
import re
import sys
import time
import unittest

import h5py
import meep as mp
import numpy as np
from meep import mpb
from scipy.optimize import minimize_scalar, ridder
from utils import ApproxComparisonTestCase


@unittest.skipIf(
    os.getenv("MEEP_SKIP_LARGE_TESTS", False),
    "skipping large tests",
)
class TestModeSolver(ApproxComparisonTestCase):

    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "data"))
    examples_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "examples")
    )
    sys.path.insert(0, example
```

## NanoComp/meep: python/tests/test_adjoint_solver.py
**Source:** `NanoComp/meep` | **Tags:** `adjoint,fdtd,gradient,meep,meep-adjoint,mode-source,official,waveguide`

MEEP official examples & tests

```python
import meep as mp

try:
    import meep.adjoint as mpa
except:
    import adjoint as mpa
import os
import unittest
from enum import Enum
from typing import List, Union, Tuple
import numpy as np
from autograd import numpy as npa
from autograd import grad, tensor_jacobian_product
from utils import ApproxComparisonTestCase

MonitorObject = Enum("MonitorObject", "EIGENMODE DFT LDOS")


class TestAdjointSolver(ApproxComparisonTestCase):
    @classmethod
    def setUpClass(cls):
        cls.resolution = 30  # pixels/μm

        cls.silicon = mp.Medium(epsilon=12)
        cls.sapphire = mp.Medium(
```

## NanoComp/meep: python/tests/test_material_grid.py
**Source:** `NanoComp/meep` | **Tags:** `adjoint,fdtd,meep,meep-adjoint,mode-source,official`

MEEP official examples & tests

```python
import meep as mp

try:
    import meep.adjoint as mpa
except:
    import adjoint as mpa

import unittest

import numpy as np
from scipy.ndimage import gaussian_filter


def compute_transmittance(matgrid_symmetry=False):
    resolution = 25

    cell_size = mp.Vector3(6, 6, 0)

    boundary_layers = [mp.PML(thickness=1.0)]

    matgrid_size = mp.Vector3(2, 2, 0)
    matgrid_resolution = 2 * resolution

    Nx, Ny = int(matgrid_size.x * matgrid_resolution), int(
        matgrid_size.y * matgrid_resolution
    )

    # ensure reproducible results
    rng = np.random.RandomState(2069588)

    w =
```

## NanoComp/meep: python/tests/test_geom.py
**Source:** `NanoComp/meep` | **Tags:** `adjoint,fdtd,meep,official`

MEEP official examples & tests

```python
import math
import unittest
import warnings

import meep.geom as gm
import numpy as np

import meep as mp


def zeros():
    return gm.Vector3(0, 0, 0)


def ones():
    return gm.Vector3(1, 1, 1)


class TestGeom(unittest.TestCase):
    def test_geometric_object_duplicates_x(self):
        rad = 1
        s = mp.Sphere(rad)
        res = mp.geometric_object_duplicates(mp.Vector3(x=1), 1, 5, s)

        expected = [
            mp.Sphere(rad, center=mp.Vector3(x=5)),
            mp.Sphere(rad, center=mp.Vector3(x=4)),
            mp.Sphere(rad, center=mp.Vector3(x=3)),
            mp.Sphere(ra
```

## NanoComp/meep: python/tests/test_user_defined_material.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest

import meep as mp


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

    if (x**2 / (R1X**2) + y**2
```

## NanoComp/meep: python/tests/test_materials_library.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest

from meep.materials import Ag, Cr, Ge, InP, LiNbO3, Si, SiO2_aniso


class TestMaterialsLibrary(unittest.TestCase):
    def test_materials_library(self):
        self.assertAlmostEqual(InP.epsilon(1 / 3.3)[0][0], (3.1031) ** 2, places=2)

        self.assertAlmostEqual(Ge.epsilon(1 / 6.8)[0][0], (4.0091) ** 2, places=2)

        self.assertAlmostEqual(Si.epsilon(1 / 1.55)[0][0], (3.4777) ** 2, places=2)

        self.assertAlmostEqual(LiNbO3.epsilon(1 / 1.55)[0][0], (2.2111) ** 2, places=2)
        self.assertAlmostEqual(LiNbO3.epsilon(1 / 1.55)[1][1], (2.2111) ** 2, places=2)
```

## NanoComp/meep: python/tests/test_3rd_harm_1d.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest

from utils import ApproxComparisonTestCase

import meep as mp


class Test3rdHarm1d(ApproxComparisonTestCase):
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

        sources = mp.Source(
            mp.GaussianSource(fcen, fwidth=df),
            component=mp.Ex,
            center=mp.Vector3(0, 0, (-0.5
```

## NanoComp/meep: python/tests/test_chunk_layout.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import copy
import unittest

import meep as mp


def traverse_tree(bp=None, min_corner=None, max_corner=None):

    process_ids = []
    chunk_areas = []

    def _traverse_tree(bp=None, min_corner=None, max_corner=None):
        if (min_corner.x > max_corner.x) or (min_corner.y > max_corner.y):
            raise RuntimeError("min_corner/max_corner have been incorrectly defined.")

        ## reached a leaf
        if bp.left is None and bp.right is None:
            process_ids.append(bp.proc_id)
            chunk_area = (max_corner.x - min_corner.x) * (max_corner.y - min_corner.y)
```

## NanoComp/meep: python/tests/test_diffracted_planewave.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import cmath
import math
import unittest

import numpy as np

import meep as mp

# Computes the mode coefficient of the transmitted orders of
# a binary grating given an incident planewave and verifies
# that the results are the same when using either a band number
# or `DiffractedPlanewave` object in `get_eigenmode_coefficients`.


class TestDiffractedPlanewave(unittest.TestCase):
    @classmethod
    def setUp(cls):
        cls.resolution = 50  # pixels/um
        cls.dpml = 1.0  # PML thickness
        cls.dsub = 3.0  # substrate thickness
        cls.dpad = 3.0  # length of padding between
```

## NanoComp/meep: python/tests/test_holey_wvg_cavity.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest

from utils import ApproxComparisonTestCase

import meep as mp


class TestHoleyWvgCavity(ApproxComparisonTestCase):
    def setUp(self):
        eps = 13
        self.w = 1.2
        r = 0.36
        d = 1.4
        N = 3
        sy = 6
        pad = 2
        self.dpml = 1
        self.sx = (2 * (pad + self.dpml + N)) + d - 1
        self.fcen = 0.25
        self.df = 0.2
        self.nfreq = 500

        cell = mp.Vector3(self.sx, sy, 0)

        blk = mp.Block(
            size=mp.Vector3(mp.inf, self.w, mp.inf), material=mp.Medium(epsilon=eps)
        )

        geometry =
```

## NanoComp/meep: python/tests/test_eigfreq.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official,waveguide`

MEEP official examples & tests

```python
import unittest

import meep as mp


class TestEigfreq(unittest.TestCase):
    @unittest.skipIf(
        mp.is_single_precision(), "double-precision floating point specific test"
    )
    def test_eigfreq(self):
        w = 1.2  # width of waveguide
        r = 0.36  # radius of holes
        d = 1.4  # defect spacing (ordinary spacing = 1)
        N = 3  # number of holes on either side of defect
        sy = 6  # size of cell in y direction (perpendicular to wvg.)
        pad = 2  # padding between last hole and PML edge
        dpml = 1  # PML thickness
        sx = 2 * (pad + dpml + N) +
```

## NanoComp/meep: python/tests/test_gaussianbeam.py
**Source:** `NanoComp/meep` | **Tags:** `dft,fdtd,meep,official`

MEEP official examples & tests

```python
import math
import unittest

import numpy as np

import meep as mp


class TestGaussianBeamSource(unittest.TestCase):
    def gaussian_beam(self, rot_angle, beamfunc=mp.GaussianBeamSource):

        s = 14
        resolution = 25
        dpml = 2

        cell_size = mp.Vector3(s, s)
        boundary_layers = [mp.PML(thickness=dpml)]

        beam_x0 = mp.Vector3(0, 7.0)  # beam focus (relative to source center)
        beam_kdir = mp.Vector3(0, 1, 0).rotate(
            mp.Vector3(0, 0, 1), math.radians(rot_angle)
        )  # beam propagation direction
        beam_w0 = 0.8  # beam waist rad
```

## NanoComp/meep: python/tests/test_oblique_source.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,mode-source,official,waveguide`

MEEP official examples & tests

```python
import math
import unittest

import meep as mp


class TestEigenmodeSource(unittest.TestCase):
    def test_waveguide_flux(self):
        cell_size = mp.Vector3(10, 10)

        pml_layers = [mp.PML(thickness=2.0)]

        rot_angles = range(0, 60, 20)  # rotation angle of waveguide, CCW around z-axis

        fluxes = []
        coeff_fluxes = []
        for t in rot_angles:
            rot_angle = math.radians(t)
            kpoint = mp.Vector3(math.cos(rot_angle), math.sin(rot_angle), 0)
            sources = [
                mp.EigenModeSource(
                    src=mp.GaussianSource(1
```

## NanoComp/meep: python/tests/test_verbosity_mgr.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest

from meep.verbosity_mgr import Verbosity


class VerbosityForTest(Verbosity):
    """Allows for testing of Verbosity without interfering with the singleton."""

    _instance = None


class MyCvar:
    def __init__(self):
        self.verbosity = 1


class TestVerbosity(unittest.TestCase):
    def setUp(self):
        VerbosityForTest.reset()
        self.v1 = VerbosityForTest(name="foo")
        self.v2 = VerbosityForTest(MyCvar(), "bar")

    def test_identity(self):
        # Ensure each verbosity is really the same singleton instance
        v1, v2 = self.v1, self.v2
```

## NanoComp/meep: python/tests/test_conductivity.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,mode-source,official,waveguide`

MEEP official examples & tests

```python
import unittest

import numpy as np

import meep as mp

dB_cm_to_dB_um = 1e-4


class TestConductivity(unittest.TestCase):
    def wvg_flux(self, res, att_coeff):
        """
        Computes the Poynting flux in a single-mode waveguide at two
        locations (5 and 10 μm) downstream from the source given the
        grid resolution res (pixels/μm) and material attenuation
        coefficient att_coeff (dB/cm).
        """

        cell_size = mp.Vector3(14.0, 14.0)

        pml_layers = [mp.PML(thickness=2.0)]

        w = 1.0  # width of waveguide

        fsrc = 0.15  # frequency (in vacu
```

## NanoComp/meep: python/tests/test_dispersive_eigenmode.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
# dispersive_eigenmode.py - Tests the meep eigenmode features (eigenmode source,
# eigenmode decomposition, and get_eigenmode) with dispersive materials.
# TODO:
#  * check materials with off diagonal components
#  * check magnetic profiles
#  * once imaginary component is supported, check that
import os
import unittest

import h5py
import numpy as np
from utils import ApproxComparisonTestCase

import meep as mp


class TestDispersiveEigenmode(ApproxComparisonTestCase):
    # ----------------------------------------- #
    # ----------- Helper Functions ------------ #
    # -------------------
```

## NanoComp/meep: python/tests/utils.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
from typing import Union
import unittest

import numpy as np


class ApproxComparisonTestCase(unittest.TestCase):
    """A mixin for adding correct scalar/vector comparison."""

    def assertClose(
        self,
        x: Union[float, np.ndarray],
        y: Union[float, np.ndarray],
        epsilon: float = 1e-2,
        msg: str = "",
    ):
        """Checks if two scalars or vectors satisfy ‖x-y‖ ≤ ε * max(‖x‖, ‖y‖).

        Args:
            x, y: two quantities to be compared (scalars or 1d arrays).
            epsilon: threshold value (maximum) of the relative error.
            msg:
```

## NanoComp/meep: python/tests/test_integrated_source.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest

import numpy as np

import meep as mp

# Test that is_integrated=True source correctly generates planewaves
# for sources extending into the PML, as in this tutorial:
#      https://meep.readthedocs.io/en/latest/Perfectly_Matched_Layer/#planewave-sources-extending-into-pml
# Regression test for issue #2043.


class TestIntegratedSource(unittest.TestCase):
    def test_integrated_source(self):
        sources = [
            mp.Source(
                mp.ContinuousSource(1, is_integrated=True),
                center=mp.Vector3(-2),
                size=mp.Vector3(y=6),
```

## NanoComp/meep: python/tests/test_chunks.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest

import meep as mp


class TestChunks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = mp.make_output_directory()

    @classmethod
    def tearDownClass(cls):
        mp.delete_directory(cls.temp_dir)

    def test_chunks(self):
        sxy = 10
        cell = mp.Vector3(sxy, sxy, 0)

        fcen = 1.0  # pulse center frequency
        df = 0.1  # pulse width (in frequency)

        sources = [mp.Source(mp.GaussianSource(fcen, fwidth=df), mp.Ez, mp.Vector3())]

        dpml = 1.0
        pml_layers = [mp.PML(dpml)]
```

## NanoComp/meep: python/tests/test_dump_load.py
**Source:** `NanoComp/meep` | **Tags:** `dft,fdtd,meep,official`

MEEP official examples & tests

```python
import itertools
import os
import re
import sys
import unittest
import warnings

import h5py
import numpy as np
from utils import ApproxComparisonTestCase

import meep as mp

try:
    unicode
except NameError:
    unicode = str


class TestLoadDump(ApproxComparisonTestCase):

    fname_base = re.sub(r"\.py$", "", os.path.split(sys.argv[0])[1])
    fname = fname_base + "-ez-000200.00.h5"

    def setUp(self):
        print(f"Running {self._testMethodName}")

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = mp.make_output_directory()
        print(f"Saving temp files to dir: {cls
```

## NanoComp/meep: python/tests/test_mode_coeffs.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,mode-source,official,waveguide`

MEEP official examples & tests

```python
import unittest

import numpy as np

import meep as mp


class TestModeCoeffs(unittest.TestCase):
    def run_mode_coeffs(self, mode_num, kpoint_func, nf=1, resolution=15):

        w = 1  # width of waveguide
        L = 10  # length of waveguide

        Si = mp.Medium(epsilon=12.0)

        dair = 3.0
        dpml = 3.0

        sx = dpml + L + dpml
        sy = dpml + dair + w + dair + dpml
        cell_size = mp.Vector3(sx, sy, 0)

        prism_x = sx + 1
        prism_y = w / 2
        vertices = [
            mp.Vector3(-prism_x, prism_y),
            mp.Vector3(prism_x, prism_y),
```

## NanoComp/meep: python/tests/test_absorber_1d.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest

from meep.materials import Al

import meep as mp


class TestAbsorber(unittest.TestCase):
    def setUp(self):

        resolution = 40
        cell_size = mp.Vector3(z=10)

        absorber_layers = [mp.Absorber(1, direction=mp.Z)]

        sources = [
            mp.Source(
                src=mp.GaussianSource(1 / 0.803, fwidth=0.1),
                center=mp.Vector3(),
                component=mp.Ex,
            )
        ]

        self.sim = mp.Simulation(
            cell_size=cell_size,
            resolution=resolution,
            dimensions=1,
            default_m
```

## NanoComp/meep: python/tests/test_adjoint_cyl.py
**Source:** `NanoComp/meep` | **Tags:** `adjoint,fdtd,gradient,meep,meep-adjoint,official`

MEEP official examples & tests

```python
import meep as mp

try:
    import meep.adjoint as mpa
except:
    import adjoint as mpa

import unittest
from enum import Enum

import numpy as np
from autograd import numpy as npa
from autograd import tensor_jacobian_product
from utils import ApproxComparisonTestCase
import parameterized

rng = np.random.RandomState(2)
resolution = 20
dimensions = mp.CYLINDRICAL
Si = mp.Medium(index=3.4)
SiO2 = mp.Medium(index=1.44)

sr = 6
sz = 6
cell_size = mp.Vector3(sr, 0, sz)
dpml = 1.0
boundary_layers = [mp.PML(thickness=dpml)]

design_region_resolution = int(2 * resolution)
design_r = 5
design_z = 2
N
```

## NanoComp/meep: python/tests/test_force.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest

import meep as mp


class TestForce(unittest.TestCase):
    def setUp(self):

        resolution = 20
        cell = mp.Vector3(10, 10)
        pml_layers = mp.PML(1.0)
        fcen = 1.0
        df = 1.0
        sources = mp.Source(
            src=mp.GaussianSource(fcen, fwidth=df), center=mp.Vector3(), component=mp.Ez
        )

        self.sim = mp.Simulation(
            resolution=resolution,
            cell_size=cell,
            boundary_layers=[pml_layers],
            sources=[sources],
        )

        fr = mp.ForceRegion(mp.Vector3(y=1.27), direction=mp.Y, size
```

## NanoComp/meep: python/tests/test_medium_evaluations.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
# medium_evaluations.py - Tests the evaluation of material permitivity profiles.
# Checks materials with lorentizian, drude, and non uniform diagonals.
# The extracted values are compared against actual datapoints pulled from
#   refractiveindex.info.
# TODO:
#  * check materials with off diagonal components
#  * check magnetic profiles
import unittest

import numpy as np

import meep as mp


class TestMediumEvaluations(unittest.TestCase):
    def test_medium_evaluations(self):
        from meep.materials import Ag, LiNbO3, Si, fused_quartz

        # Check that scalars work
        w0 = LiNbO
```

## NanoComp/meep: python/tests/test_wvg_src.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,mode-source,official`

MEEP official examples & tests

```python
import sys
import unittest

import meep as mp


class TestWvgSrc(unittest.TestCase):
    def setUp(self):

        cell = mp.Vector3(16, 8)

        geometry = [
            mp.Block(
                center=mp.Vector3(),
                size=mp.Vector3(mp.inf, 1, mp.inf),
                material=mp.Medium(epsilon=12),
            ),
            mp.Block(
                center=mp.Vector3(y=0.3),
                size=mp.Vector3(mp.inf, 0.1, mp.inf),
                material=mp.Medium(),
            ),
        ]

        sources = [
            mp.EigenModeSource(
                src=mp.Continu
```

## NanoComp/meep: python/tests/test_physical.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import unittest

import meep as mp


class TestPhysical(unittest.TestCase):
    def test_physical(self):

        a = 10.0
        ymax = 3.0
        xmax = 8.0
        dx = 2.0
        w = 0.30

        cell_size = mp.Vector3(xmax, ymax)
        pml_layers = [mp.PML(ymax / 3.0)]

        sources = [
            mp.Source(
                src=mp.ContinuousSource(w),
                component=mp.Ez,
                center=mp.Vector3(-dx),
                size=mp.Vector3(),
            )
        ]

        sim = mp.Simulation(
            cell_size=cell_size,
            resolution=a,
```

## NanoComp/meep: python/tests/test_timing_measurements.py
**Source:** `NanoComp/meep` | **Tags:** `fdtd,meep,official`

MEEP official examples & tests

```python
import time
import unittest

import meep as mp
from meep import timing_measurements as timing


class TimingTest(unittest.TestCase):
    def test_timing_measurements(self):
        """Tests that timing measurements have expected names and can be updated."""
        sim = mp.Simulation(
            cell_size=mp.Vector3(2, 2, 2),
            resolution=20,
        )
        time_start = time.time()
        sim.run(until=5)
        timing_measurements = timing.MeepTimingMeasurements.new_from_simulation(sim)

        # Check for expected names after updating
        self.assertSetEqual(
```

## NanoComp/meep: python/tests/test_adjoint_jax.py
**Source:** `NanoComp/meep` | **Tags:** `adjoint,fdtd,gradient,meep,meep-adjoint,mode-source,official,waveguide`

MEEP official examples & tests

```python
import unittest

import jax
import jax.numpy as jnp
import meep.adjoint as mpa
import numpy as onp
import parameterized
from utils import ApproxComparisonTestCase

import meep as mp

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
# (one for each f
```

