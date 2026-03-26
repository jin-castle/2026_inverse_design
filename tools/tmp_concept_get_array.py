import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)
eps    = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))

# Cross-section profile
mid_x = ez_td.shape[0]//2
y_vals = np.linspace(-(sy-2*dpml)/2, (sy-2*dpml)/2, ez_td.shape[1])

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
im0 = axes[0].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[0].set_title('get_array(Ez) - Time Domain'); plt.colorbar(im0, ax=axes[0])
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[1].set_title('|Ez|\u00b2 DFT'); plt.colorbar(im1, ax=axes[1])
axes[2].plot(y_vals, ez_td[mid_x,:], 'b-', label='Ez (time domain)')
axes[2].plot(y_vals, np.abs(ez_dft[ez_dft.shape[0]//2,:]), 'r--', label='|Ez| DFT')
axes[2].set_xlabel('y'); axes[2].set_ylabel('Ez')
axes[2].set_title('Cross-section at x=0')
axes[2].legend(); axes[2].grid(True, alpha=0.4)
plt.suptitle('sim.get_array() - Field Data Extraction', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_get_array.png', dpi=100, bbox_inches='tight')
print("Done")
