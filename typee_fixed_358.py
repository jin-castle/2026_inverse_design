# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys, os
os.makedirs('/tmp/kb_results', exist_ok=True)

if '__file__' not in dir():
    __file__ = '/tmp/typee_358.py'

_fig_count = [0]
_orig_show = plt.show
def _patched_show(*a, **kw):
    _n = _fig_count[0]
    plt.savefig('/tmp/kb_results/typee_358_%02d.png' % _n, dpi=80, bbox_inches='tight')
    _fig_count[0] += 1
    plt.close('all')
plt.show = _patched_show

import meep as mp

cell = mp.Vector3(16,8,0)

geometry = [mp.Block(mp.Vector3(mp.inf,1,mp.inf),
                     center=mp.Vector3(),
                     material=mp.Medium(epsilon=12))]

sources = [mp.Source(mp.ContinuousSource(frequency=0.15),
                     component=mp.Ez,
                     center=mp.Vector3(-7,0))]

pml_layers = [mp.PML(1.0)]

resolution = 10

sim = mp.Simulation(cell_size=cell,
                    boundary_layers=pml_layers,
                    geometry=geometry,
                    sources=sources,
                    resolution=resolution)

from matplotlib import pyplot as plt
plt.figure(dpi=100)
sim.plot2D()
plt.show()

sim.run(until=200)

plt.figure(dpi=100)
sim.plot2D(fields=mp.Ez)
plt.show()

sim.reset_meep()
f = plt.figure(dpi=100)
Animate = mp.Animate2D(sim, fields=mp.Ez, f=f, realtime=False, normalize=True)
plt.close()

sim.run(mp.at_every(1,Animate),until=100)
plt.close()
