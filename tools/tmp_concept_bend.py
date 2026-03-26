import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 14, 14
dpml = 1.5
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)
w = 0.5; R = 4.0  # bend radius

# L-shaped waveguide: horizontal + 90-deg bend + vertical
geometry = [
    # Horizontal section (left)
    mp.Block(size=mp.Vector3(sx/2+R, w), center=mp.Vector3(-(sx/2-R)/2, 0), material=Si),
    # Vertical section (top)
    mp.Block(size=mp.Vector3(w, sy/2-R), center=mp.Vector3(R, (sy/2+R)/2), material=Si),
    # Corner fill (approximate quarter circle with blocks)
]
# Add quarter-circle corner
n_seg = 12
for i in range(n_seg):
    th0 = np.pi * i / (2*n_seg)
    th1 = np.pi * (i+1) / (2*n_seg)
    th_mid = (th0+th1)/2
    # Center of segment on arc
    xc = R * (1 - np.cos(th_mid))
    yc = R * np.sin(th_mid)
    seg_w = R * (th1-th0) * 1.3  # overlap
    geometry.append(mp.Block(
        size=mp.Vector3(seg_w, w),
        center=mp.Vector3(xc - R + 0, yc),
        e1=mp.Vector3(np.cos(th_mid), np.sin(th_mid)),
        e2=mp.Vector3(-np.sin(th_mid), np.cos(th_mid)),
        material=Si
    ))

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=geometry,
    sources=[mp.EigenModeSource(
        mp.GaussianSource(fcen, fwidth=df),
        center=mp.Vector3(-sx/2+dpml+0.5), size=mp.Vector3(0, sy),
        eig_band=1, eig_parity=mp.ODD_Z
    )],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(R, sy/2-dpml-1), 1e-6))

eps    = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
im0 = axes[0].imshow(eps.T, cmap='Blues', origin='lower', aspect='equal',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im0, ax=axes[0], label='\u03b5_r')
axes[0].set_title('90\u00b0 Bend Waveguide Geometry\n(R={} \u03bcm)'.format(R))
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='equal',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im1, ax=axes[1], label='|Ez|\u00b2')
axes[1].set_title('|Ez|\u00b2 DFT: Guided Mode through Bend')
plt.suptitle('bend: 90\u00b0 Waveguide Bend (R={} \u03bcm)'.format(R), fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_bend.png', dpi=100, bbox_inches='tight')
print("Done")
