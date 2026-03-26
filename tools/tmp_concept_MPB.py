import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# MPB: mode profile via MEEP eigenmode solver
resolution = 20
sx, sy = 6, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si   = mp.Medium(epsilon=12)
w = 0.5

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, w), material=Si)],
    sources=[mp.EigenModeSource(
        mp.GaussianSource(fcen, fwidth=df),
        center=mp.Vector3(-sx/2+dpml+0.5), size=mp.Vector3(0, sy),
        eig_band=1, eig_parity=mp.ODD_Z
    )],
    resolution=resolution
)

dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

eps   = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

# Cross-section profile at center
mid_x = ez_dft.shape[0]//2
y_vals = np.linspace(-(sy-2*dpml)/2, (sy-2*dpml)/2, ez_dft.shape[1])
mode_profile = np.abs(ez_dft[mid_x, :])

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
im0 = axes[0].imshow(eps.T, cmap='Blues', origin='lower', aspect='auto',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im0, ax=axes[0], label='\u03b5_r')
axes[0].set_title('SOI Waveguide Structure\n(MPB-like geometry)')
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im1, ax=axes[1], label='|Ez|\u00b2')
axes[1].set_title('Guided Mode |Ez|\u00b2 (DFT)\nFundamental TE mode')
axes[2].plot(y_vals, mode_profile/mode_profile.max(), 'b-', lw=2, label='|Ez| DFT')
axes[2].axvspan(-w/2, w/2, alpha=0.2, color='orange', label=f'Core (w={w}\u03bcm)')
axes[2].set_xlabel('y (\u03bcm)'); axes[2].set_ylabel('|Ez| normalized')
axes[2].set_title('Mode Profile Cross-section\n(MPB-equivalent)')
axes[2].legend(); axes[2].grid(True, alpha=0.4)
plt.suptitle('MPB: Waveguide Mode Profile Analysis', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_MPB.png', dpi=100, bbox_inches='tight')
print("Done")
