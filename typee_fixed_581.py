# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys, os
os.makedirs('/tmp/kb_results', exist_ok=True)

if '__file__' not in dir():
    __file__ = '/tmp/typee_581.py'

_fig_count = [0]
_orig_show = plt.show
def _patched_show(*a, **kw):
    _n = _fig_count[0]
    plt.savefig('/tmp/kb_results/typee_581_%02d.png' % _n, dpi=80, bbox_inches='tight')
    _fig_count[0] += 1
    plt.close('all')
plt.show = _patched_show

import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 20  # pixels/μm

eps = 13  # dielectric constant of waveguide
w = 1.2  # width of waveguide
r = 0.36  # radius of holes
d = 1.4  # defect spacing (ordinary spacing = 1)
N = 3  # number of holes on either side of defect

sy = 6  # size of cell in y direction (perpendicular to wvg.)
pad = 2  # padding between last hole and PML edge
dpml = 1  # PML thickness
sx = 2 * (pad + dpml + N) + d - 1  # size of cell in x direction

cell = mp.Vector3(sx, sy, 0)
pml_layers = mp.PML(dpml)

geometry = [
    mp.Block(
        center=mp.Vector3(),
        size=mp.Vector3(mp.inf, w, mp.inf),
        material=mp.Medium(epsilon=eps),
    )
]

for i in range(N):
    geometry.append(mp.Cylinder(r, center=mp.Vector3(0.5 * d + i)))
    geometry.append(mp.Cylinder(r, center=mp.Vector3(-0.5 * d - i)))

fcen = 0.25  # pulse center frequency
df = 0.2  # pulse width (in frequency)

sources = mp.Source(
    src=mp.GaussianSource(fcen, fwidth=df), component=mp.Hz, center=mp.Vector3()
)

symmetries = [mp.Mirror(mp.X, phase=-1), mp.Mirror(mp.Y, phase=-1)]

sim = mp.Simulation(
    cell_size=cell,
    geometry=geometry,
    sources=[sources],
    symmetries=symmetries,
    boundary_layers=[pml_layers],
    resolution=resolution,
)

d1 = 0.2

nearfield = sim.add_near2far(
    fcen,
    0,
    1,
    mp.Near2FarRegion(mp.Vector3(y=0.5 * w + d1), size=mp.Vector3(sx - 2 * dpml)),
    mp.Near2FarRegion(
        mp.Vector3(-0.5 * sx + dpml, 0.5 * w + 0.5 * d1),
        size=mp.Vector3(y=d1),
        weight=-1.0,
    ),
    mp.Near2FarRegion(
        mp.Vector3(0.5 * sx - dpml, 0.5 * w + 0.5 * d1), size=mp.Vector3(y=d1)
    ),
)

sim.run(
    until_after_sources=mp.stop_when_fields_decayed(
        50, mp.Hz, mp.Vector3(0.12, -0.37), 1e-8
    )
)

d2 = 20
h = 4

ff = sim.get_farfields(
    nearfield,
    resolution,
    center=mp.Vector3(y=0.5 * w + d2 + 0.5 * h),
    size=mp.Vector3(sx - 2 * dpml, h),
)

plt.figure(dpi=200)
plt.imshow(np.rot90(np.real(ff["Hz"]), 1), cmap="RdBu")
plt.axis("off")
plt.show()
