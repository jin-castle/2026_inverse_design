import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

results = {}
for res in [5, 10, 20]:
    sim = mp.Simulation(
        cell_size=mp.Vector3(sx, sy),
        boundary_layers=[mp.PML(dpml)],
        geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
        sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                           center=mp.Vector3(-sx/2+dpml+0.5))],
        resolution=res
    )
    dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
        where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
    sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))
    ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)
    results[res] = ez_dft

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
for i, (res, ez_dft) in enumerate(results.items()):
    im = axes[i].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
    axes[i].set_title(f'resolution={res}\n({ez_dft.shape[0]}x{ez_dft.shape[1]} grid points)')
    plt.colorbar(im, ax=axes[i])
plt.suptitle('resolution: Grid Density Effect on DFT Field Quality', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_resolution.png', dpi=100, bbox_inches='tight')
print("Done")
