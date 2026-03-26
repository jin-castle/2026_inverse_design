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

# Compare two Courant numbers
results = {}
for courant in [0.4, 0.5]:
    sim = mp.Simulation(
        cell_size=mp.Vector3(sx, sy),
        boundary_layers=[mp.PML(dpml)],
        geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
        sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                           center=mp.Vector3(-sx/2+dpml+0.5))],
        resolution=resolution,
        Courant=courant
    )
    dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
        where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
    sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))
    ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
    ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)
    results[courant] = (ez_td, ez_dft)

fig, axes = plt.subplots(2, 2, figsize=(12, 7))
for i, (c, (ez_td, ez_dft)) in enumerate(results.items()):
    im0 = axes[i][0].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
    axes[i][0].set_title(f'Ez Time Domain (Courant={c})')
    plt.colorbar(im0, ax=axes[i][0])
    im1 = axes[i][1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
    axes[i][1].set_title(f'|Ez|\u00b2 DFT (Courant={c})')
    plt.colorbar(im1, ax=axes[i][1])
plt.suptitle('Courant Number Stability Comparison', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_courant.png', dpi=100, bbox_inches='tight')
print("Done")
