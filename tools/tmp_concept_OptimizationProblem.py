import matplotlib
matplotlib.use('Agg')
import meep as mp
import meep.adjoint as mpa
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 8.0, 4.0
dpml = 1.0
w = 0.5
fcen = 1/1.55; df = 0.3
Si   = mp.Medium(epsilon=12)
SiO2 = mp.Medium(epsilon=2.25)

Nx, Ny = 20, 10
rho_init = np.ones((Nx, Ny)) * 0.5

design_region = mpa.DesignRegion(
    mp.MaterialGrid(mp.Vector3(Nx, Ny), SiO2, Si, weights=rho_init.flatten()),
    volume=mp.Volume(center=mp.Vector3(), size=mp.Vector3(2.0, 1.0))
)

geometry = [
    mp.Block(mp.Vector3(mp.inf, w), material=Si),
    mp.Block(mp.Vector3(2.0, 1.0), material=mp.MaterialGrid(
        mp.Vector3(Nx, Ny), SiO2, Si, weights=rho_init.flatten()
    )),
]

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=geometry,
    resolution=resolution
)
sim.init_sim()

eps = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
design_eps = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(2.0, 1.0))

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
im0 = axes[0].imshow(eps.T, cmap='Blues', origin='lower', aspect='auto',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im0, ax=axes[0], label='\u03b5_r')
axes[0].set_title('Full Structure: SOI + Design Region\nBlue=Si, White=SiO\u2082')
# Mark design region boundary
from matplotlib.patches import Rectangle
rect = Rectangle((-1, -0.5), 2, 1, linewidth=2, edgecolor='red', facecolor='none')
axes[0].add_patch(rect)
axes[0].set_xlabel('x (\u03bcm)'); axes[0].set_ylabel('y (\u03bcm)')

im1 = axes[1].imshow(rho_init.T, cmap='RdBu_r', origin='lower', aspect='auto',
                     vmin=0, vmax=1, extent=[-1, 1, -0.5, 0.5])
plt.colorbar(im1, ax=axes[1], label='\u03c1 (design var)')
axes[1].set_title('Design Variable \u03c1 (Initial: 0.5)\nmpa.OptimizationProblem')
axes[1].text(0, 0, 'Adjoint optimization:\nFOM gradient via \u2202T/\u2202\u03c1', 
             ha='center', va='center', fontsize=9, color='white',
             bbox=dict(boxstyle='round', facecolor='navy', alpha=0.7))
plt.suptitle('mpa.OptimizationProblem: Inverse Design Setup', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_OptimizationProblem.png', dpi=100, bbox_inches='tight')
print("Done")
