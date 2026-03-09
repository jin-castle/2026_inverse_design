# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys, os
os.makedirs('/tmp/kb_results', exist_ok=True)

if '__file__' not in dir():
    __file__ = '/tmp/typee_570.py'

_fig_count = [0]
_orig_show = plt.show
def _patched_show(*a, **kw):
    _n = _fig_count[0]
    plt.savefig('/tmp/kb_results/typee_570_%02d.png' % _n, dpi=80, bbox_inches='tight')
    _fig_count[0] += 1
    plt.close('all')
plt.show = _patched_show

import meep as mp
import numpy as np
from matplotlib import pyplot as plt


# Some parameters to describe the geometry:
eps = 13  # dielectric constant of waveguide
w = 1.2  # width of waveguide
r = 0.36  # radius of holes

# The cell dimensions
sy = 12  # size of cell in y direction (perpendicular to wvg.)
dpml = 1  # PML thickness (y direction only!)
cell = mp.Vector3(1, sy)

b = mp.Block(size=mp.Vector3(1e20, w, 1e20), material=mp.Medium(epsilon=eps))
c = mp.Cylinder(radius=r)

geometry = [b, c]

resolution = 20

pml_layers = [mp.PML(dpml, direction=mp.Y)]

fcen = 0.25  # pulse center frequency
df = 1.5  # pulse freq. width: large df = short impulse

s = [
    mp.Source(
        src=mp.GaussianSource(fcen, fwidth=df),
        component=mp.Hz,
        center=mp.Vector3(0.1234, 0),
    )
]

sym = [mp.Mirror(direction=mp.Y, phase=-1)]

sim = mp.Simulation(
    cell_size=cell,
    geometry=geometry,
    boundary_layers=pml_layers,
    sources=s,
    symmetries=sym,
    resolution=resolution,
)
f = plt.figure(dpi=150)
sim.plot2D(ax=f.gca())
plt.show()

kx = 0.4
sim.k_point = mp.Vector3(kx)

sim.run(
    mp.after_sources(mp.Harminv(mp.Hz, mp.Vector3(0.1234), fcen, df)),
    until_after_sources=300,
)

sim.restart_fields()
k_interp = 19
kpts = mp.interpolate(k_interp, [mp.Vector3(0), mp.Vector3(0.5)])
all_freqs = sim.run_k_points(300, kpts)

kx = [k.x for k in kpts]
fig = plt.figure(dpi=100, figsize=(5, 5))
ax = plt.subplot(111)
for i in range(len(all_freqs)):
    for ii in range(len(all_freqs[i])):
        plt.scatter(kx[i], np.real(all_freqs[i][ii]), color="b")

ax.fill_between(kx, kx, 1.0, interpolate=True, color="gray", alpha=0.3)
plt.xlim(0, 0.5)
plt.ylim(0, 1)
plt.grid(True)
plt.xlabel("$k_x(2\pi)$")
plt.ylabel("$\omega(2\pi c)$")
plt.tight_layout()
plt.show()
