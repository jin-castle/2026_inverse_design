# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys, os
os.makedirs('/tmp/kb_results', exist_ok=True)

if '__file__' not in dir():
    __file__ = '/tmp/typeb_412.py'

_fig_count = [0]
_orig_show = plt.show
def _patched_show(*a, **kw):
    _n = _fig_count[0]
    plt.savefig('/tmp/kb_results/typeb_412_%02d.png' % _n, dpi=80, bbox_inches='tight')
    _fig_count[0] += 1
    plt.close('all')
plt.show = _patched_show

import meep as mp
import meep.adjoint as mpa
import numpy as np
from autograd import numpy as npa
import nlopt
from matplotlib import pyplot as plt
mp.quiet(quietval=True)
Si = mp.Medium(index=3.4)
SiO2 = mp.Medium(index=1.44)

resolution = 20

Sx = 6
Sy = 5
cell_size = mp.Vector3(Sx,Sy)

pml_layers = [mp.PML(1.0)]

fcen = 1/1.55
width = 0.2
fwidth = width * fcen
source_center  = [-1.5,0,0]
source_size    = mp.Vector3(0,2,0)
kpoint = mp.Vector3(1,0,0)
src = mp.GaussianSource(frequency=fcen,fwidth=fwidth)
source = [mp.EigenModeSource(src,
                    eig_band = 1,
                    direction=mp.NO_DIRECTION,
                    eig_kpoint=kpoint,
                    size = source_size,
                    center=source_center)]

design_region_resolution = 10
Nx = design_region_resolution
Ny = design_region_resolution

design_variables = mp.MaterialGrid(mp.Vector3(Nx,Ny),SiO2,Si,grid_type='U_MEAN')
design_region = mpa.DesignRegion(design_variables,volume=mp.Volume(center=mp.Vector3(), size=mp.Vector3(1, 1, 0)))


geometry = [
    mp.Block(center=mp.Vector3(x=-Sx/4), material=Si, size=mp.Vector3(Sx/2, 0.5, 0)), # horizontal waveguide
    mp.Block(center=mp.Vector3(y=Sy/4), material=Si, size=mp.Vector3(0.5, Sy/2, 0)),  # vertical waveguide
    mp.Block(center=design_region.center, size=design_region.size, material=design_variables), # design region
    mp.Block(center=design_region.center, size=design_region.size, material=design_variables,
             e1=mp.Vector3(x=-1).rotate(mp.Vector3(z=1), np.pi/2), e2=mp.Vector3(y=1).rotate(mp.Vector3(z=1), np.pi/2))
]

sim = mp.Simulation(cell_size=cell_size,
                    boundary_layers=pml_layers,
                    geometry=geometry,
                    sources=source,
                    eps_averaging=False,
                    resolution=resolution)

TE_top = mpa.EigenmodeCoefficient(sim,mp.Volume(center=mp.Vector3(0,1,0),size=mp.Vector3(x=2)),mode=1)
ob_list = [TE_top]

def J(alpha):
    return npa.abs(alpha) ** 2

opt = mpa.OptimizationProblem(
    simulation=sim,
    objective_functions=J,
    objective_arguments=ob_list,
    design_regions=[design_region],
    fcen=fcen,
    df = 0,
    nf = 1,
    # decay_fields=[mp.Ez]  # removed: API not supported in this meep version
)

x0 = 0.5*np.ones((Nx*Ny,))
opt.update_design([x0])

opt.plot2D(True)
plt.show()

evaluation_history = []
sensitivity = [0]
def f(x, grad):
    f0, dJ_du = opt([x])
    if grad.size > 0:
        grad[:] = np.squeeze(dJ_du)
    evaluation_history.append(np.real(f0))
    sensitivity[0] = dJ_du
    return np.real(f0)

algorithm = nlopt.LD_MMA
n = Nx * Ny
maxeval = 10

solver = nlopt.opt(algorithm, n)
solver.set_lower_bounds(0)
solver.set_upper_bounds(1)
solver.set_max_objective(f)
solver.set_maxeval(maxeval)
x = solver.optimize(x0);

plt.figure()
plt.plot(evaluation_history,'o-')
plt.grid(True)
plt.xlabel('Iteration')
plt.ylabel('FOM')
plt.show()

opt.update_design([x])
opt.plot2D(True,plot_monitors_flag=False,output_plane=mp.Volume(center=(0,0,0),size=(2,2,0)))
plt.axis("off");

TE0 = mpa.EigenmodeCoefficient(sim,mp.Volume(center=mp.Vector3(-1,0,0),size=mp.Vector3(y=2)),mode=1)
ob_list = [TE0,TE_top]

def J(source,top):
    return npa.abs(top/source) ** 2

opt.objective_functions = [J]
opt.objective_arguments = ob_list
opt.update_design([x0])

evaluation_history = []
solver = nlopt.opt(algorithm, n)
solver.set_lower_bounds(0)
solver.set_upper_bounds(1)
solver.set_max_objective(f)
solver.set_maxeval(maxeval)
x = solver.optimize(x0)

plt.figure()
plt.plot(np.array(evaluation_history)*100,'o-')
plt.grid(True)
plt.xlabel('Iteration')
plt.ylabel('Transmission (%)')
plt.show()

improvement = max(evaluation_history) / min(evaluation_history)
print("Achieved an improvement of {0:1.1f}x".format(improvement))

opt.update_design([x])
opt.plot2D(True,plot_monitors_flag=False,output_plane=mp.Volume(center=(0,0,0),size=(2,2,0)))
plt.axis("off");

plt.imshow(np.rot90(np.squeeze(np.abs(sensitivity[0].reshape(Nx,Ny)))));
