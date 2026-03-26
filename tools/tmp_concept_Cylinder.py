import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 12, 12
dpml = 1.0
fcen = 0.3; df = 0.2
n_rod = 3.5
a = 1.0  # lattice constant

# Photonic crystal: 3x3 array of cylinders
cylinders = []
for ix in range(-1, 2):
    for iy in range(-1, 2):
        cylinders.append(mp.Cylinder(
            radius=0.2*a, height=mp.inf,
            material=mp.Medium(index=n_rod),
            center=mp.Vector3(ix*a, iy*a)
        ))

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=cylinders,
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+1))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

eps   = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
im0 = axes[0].imshow(eps.T, cmap='hot', origin='lower', aspect='equal',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im0, ax=axes[0], label='\u03b5_r')
axes[0].set_title('mp.Cylinder Array\nPhotonic Crystal (3x3 rods)')
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='inferno', origin='lower', aspect='equal',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im1, ax=axes[1], label='|Ez|\u00b2')
axes[1].set_title('|Ez|\u00b2 DFT: Scattering through PhC')
plt.suptitle('mp.Cylinder: Photonic Crystal Rod Array', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_Cylinder.png', dpi=100, bbox_inches='tight')
print("Done")
