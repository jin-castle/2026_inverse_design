# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys, os, types

if '__file__' not in dir():
    __file__ = '/tmp/fixed_400.py'

_script_id = 400
_fig_count = [0]
_orig_show = plt.show
def _patched_show(*args, **kwargs):
    os.makedirs('/tmp/kb_results', exist_ok=True)
    plt.savefig(f'/tmp/kb_results/fixed_{_script_id}_{_fig_count[0]:02d}.png', dpi=80, bbox_inches='tight')
    _fig_count[0] += 1
plt.show = _patched_show

import meep as mp
import numpy as np

resolution = 50  # pixels/μm

cell_size = mp.Vector3(14, 14)

pml_layers = [mp.PML(thickness=2)]

rot_angle = np.radians(20)
w = 1.0

geometry = [mp.Block(center=mp.Vector3(),
                     size=mp.Vector3(mp.inf, w, mp.inf),
                     e1=mp.Vector3(x=1).rotate(mp.Vector3(z=1), rot_angle),
                     e2=mp.Vector3(y=1).rotate(mp.Vector3(z=1), rot_angle),
                     material=mp.Medium(epsilon=12))]

fsrc = 0.15
bnum = 1

kpoint = mp.Vector3(x=1).rotate(mp.Vector3(z=1), rot_angle)

# First: compute flux (fast)
sources_flux = [mp.EigenModeSource(src=mp.GaussianSource(fsrc, fwidth=0.2 * fsrc),
                                   center=mp.Vector3(),
                                   size=mp.Vector3(y=3 * w),
                                   direction=mp.NO_DIRECTION,
                                   eig_kpoint=kpoint,
                                   eig_band=bnum,
                                   eig_parity=mp.ODD_Z,
                                   eig_match_freq=True)]

sim = mp.Simulation(cell_size=cell_size,
                    resolution=resolution,
                    boundary_layers=pml_layers,
                    sources=sources_flux,
                    geometry=geometry)

tran = sim.add_flux(fsrc, 0, 1, mp.FluxRegion(center=mp.Vector3(x=5), size=mp.Vector3(y=14)))
sim.run(until_after_sources=50)
flux_val = mp.get_fluxes(tran)[0]
print(f"Flux: {flux_val:.6f}")

# Second: quick field visualization with ContinuousSource + short run
sim.reset_meep()

sources_vis = [mp.Source(src=mp.ContinuousSource(fsrc),
                         center=mp.Vector3(),
                         size=mp.Vector3(y=3 * w),
                         component=mp.Ez)]

sim2 = mp.Simulation(cell_size=cell_size,
                     resolution=resolution,
                     boundary_layers=pml_layers,
                     sources=sources_vis,
                     geometry=geometry)

sim2.run(until=30)  # Short run for visualization only

if mp.am_master():
    sim2.plot2D(output_plane=mp.Volume(center=mp.Vector3(), size=mp.Vector3(10, 10)),
                fields=mp.Ez,
                field_parameters={'alpha': 0.9})
    plt.title("Oblique Waveguide - Ez field (t=30)")
    plt.show()

print("Done.")
