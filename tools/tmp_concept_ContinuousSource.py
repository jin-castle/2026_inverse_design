import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55
Si = mp.Medium(epsilon=12)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.Source(mp.ContinuousSource(fcen), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until=100)

ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)
eps    = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].imshow(eps.T, cmap='Greys', origin='lower', aspect='auto')
axes[0].set_title('Waveguide Structure')
t = np.linspace(0, 4/fcen, 500)
axes[0].text(0.5, -0.18, f'ContinuousSource(freq={fcen:.3f}): sin(2\u03c0ft)', 
             ha='center', transform=axes[0].transAxes, fontsize=8, style='italic')
im1 = axes[1].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[1].set_title('Ez Steady-State (CW)'); plt.colorbar(im1, ax=axes[1])
im2 = axes[2].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[2].set_title('|Ez|\u00b2 DFT (CW steady state)'); plt.colorbar(im2, ax=axes[2])
plt.suptitle('ContinuousSource: CW Excitation Demo', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_ContinuousSource.png', dpi=100, bbox_inches='tight')
print("Done")
