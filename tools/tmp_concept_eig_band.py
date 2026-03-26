import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 12, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

results = {}
for band in [1, 2]:
    sim = mp.Simulation(
        cell_size=mp.Vector3(sx, sy),
        boundary_layers=[mp.PML(dpml)],
        geometry=[mp.Block(size=mp.Vector3(mp.inf, 1.0), material=Si)],
        sources=[mp.EigenModeSource(
            mp.GaussianSource(fcen, fwidth=df),
            center=mp.Vector3(-sx/2+dpml+0.5), size=mp.Vector3(0, sy),
            eig_band=band, eig_parity=mp.ODD_Z
        )],
        resolution=resolution
    )
    dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
        where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
    sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))
    ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)
    results[band] = ez_dft

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
for i, (band, ez_dft) in enumerate(results.items()):
    im = axes[i].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
    axes[i].set_title(f'|Ez|\u00b2 DFT: eig_band={band}\n({"Fundamental" if band==1 else "2nd order"} mode)')
    plt.colorbar(im, ax=axes[i])
plt.suptitle('EigenModeSource eig_band: Mode Selection', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_eig_band.png', dpi=100, bbox_inches='tight')
print("Done")
