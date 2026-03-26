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

# TE mode: ODD_Z parity for Ez (Ez != 0)
# TM mode: EVEN_Y (Hz field dominant, use Hz component)
results = {}

# TE mode (ODD_Z, Ez)
sim_te = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 1.0), material=Si)],
    sources=[mp.EigenModeSource(
        mp.GaussianSource(fcen, fwidth=df),
        center=mp.Vector3(-sx/2+dpml+0.5), size=mp.Vector3(0, sy),
        eig_band=1, eig_parity=mp.ODD_Z
    )],
    resolution=resolution
)
dft_te = sim_te.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim_te.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))
ez_te = sim_te.get_dft_array(dft_te, mp.Ez, 0)

# eig_band=2 mode (higher order, still ODD_Z)
sim_ho = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 1.0), material=Si)],
    sources=[mp.EigenModeSource(
        mp.GaussianSource(fcen, fwidth=df),
        center=mp.Vector3(-sx/2+dpml+0.5), size=mp.Vector3(0, sy),
        eig_band=2, eig_parity=mp.ODD_Z
    )],
    resolution=resolution
)
dft_ho = sim_ho.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim_ho.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))
ez_ho = sim_ho.get_dft_array(dft_ho, mp.Ez, 0)

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
im0 = axes[0].imshow(np.abs(ez_te).T**2, cmap='hot', origin='lower', aspect='auto')
axes[0].set_title('|Ez|\u00b2 DFT: eig_parity=ODD_Z, eig_band=1\n(Fundamental TE mode)')
plt.colorbar(im0, ax=axes[0])
im1 = axes[1].imshow(np.abs(ez_ho).T**2, cmap='hot', origin='lower', aspect='auto')
axes[1].set_title('|Ez|\u00b2 DFT: eig_parity=ODD_Z, eig_band=2\n(Higher-order TE mode)')
plt.colorbar(im1, ax=axes[1])
plt.suptitle('eig_parity: Parity Selection for EigenModeSource', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_eig_parity.png', dpi=100, bbox_inches='tight')
print("Done")
