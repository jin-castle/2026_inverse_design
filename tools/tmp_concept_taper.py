import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 20
sx, sy = 12.0, 4.0
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
w_in = 0.4; w_out = 1.5; L = 5.0
eps_wg = 12

vertices = [mp.Vector3(-L/2, -w_in/2), mp.Vector3(-L/2, w_in/2),
            mp.Vector3(L/2, w_out/2), mp.Vector3(L/2, -w_out/2)]
taper = mp.Prism(vertices=vertices, height=mp.inf, material=mp.Medium(epsilon=eps_wg))
wg_in  = mp.Block(center=mp.Vector3(-sx/2+dpml+(sx/2-L/2-dpml)/2, 0),
                  size=mp.Vector3(sx/2-L/2-dpml, w_in, mp.inf), material=mp.Medium(epsilon=eps_wg))
wg_out = mp.Block(center=mp.Vector3(L/2+(sx/2-dpml-L/2)/2, 0),
                  size=mp.Vector3(sx/2-dpml-L/2, w_out, mp.inf), material=mp.Medium(epsilon=eps_wg))

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[wg_in, taper, wg_out],
    sources=[mp.EigenModeSource(mp.GaussianSource(fcen, fwidth=df),
                                center=mp.Vector3(-sx/2+dpml+0.5), size=mp.Vector3(0, sy),
                                eig_band=1, eig_parity=mp.ODD_Z)],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)
eps    = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].imshow(eps.T, cmap='Greys', origin='lower', aspect='auto')
axes[0].set_title(f'Taper Geometry (w_in={w_in}, w_out={w_out})')
im1 = axes[1].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[1].set_title('Ez Time Domain'); plt.colorbar(im1, ax=axes[1])
im2 = axes[2].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[2].set_title('|Ez|\u00b2 DFT'); plt.colorbar(im2, ax=axes[2])
plt.suptitle('Linear Taper Waveguide: Mode Expansion', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_taper.png', dpi=100, bbox_inches='tight')
print("Done")
