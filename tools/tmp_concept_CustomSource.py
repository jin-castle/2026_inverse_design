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

# Custom source: modulated Gaussian
def custom_src_func(t):
    return np.exp(-((t-20)**2)/(2*5**2)) * np.cos(2*np.pi*fcen*t)

src = mp.CustomSource(src_func=custom_src_func, center_frequency=fcen, fwidth=df)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.Source(src, component=mp.Ez, center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until=150)

ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

t_arr = np.linspace(0, 150, 1000)
src_arr = [custom_src_func(t) for t in t_arr]

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].plot(t_arr, src_arr, 'b-', lw=1)
axes[0].set_title('CustomSource Time Profile'); axes[0].set_xlabel('Time'); axes[0].set_ylabel('Amplitude')
axes[0].grid(True, alpha=0.4)
im1 = axes[1].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[1].set_title('Ez Time Domain'); plt.colorbar(im1, ax=axes[1])
im2 = axes[2].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[2].set_title('|Ez|\u00b2 DFT'); plt.colorbar(im2, ax=axes[2])
plt.suptitle('CustomSource: User-Defined Source Function', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_CustomSource.png', dpi=100, bbox_inches='tight')
print("Done")
