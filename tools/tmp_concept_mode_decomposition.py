import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 14.0, 4.0
dpml = 1.0
w = 0.5
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, w), material=Si)],
    sources=[mp.EigenModeSource(
        mp.GaussianSource(fcen, fwidth=df),
        center=mp.Vector3(-sx/2+dpml+1), size=mp.Vector3(0, sy),
        eig_band=1, eig_parity=mp.ODD_Z
    )],
    resolution=resolution
)

mon_trans = sim.add_flux(fcen, 0, 1, mp.FluxRegion(center=mp.Vector3(sx/2-dpml-0.5), size=mp.Vector3(0, sy)))
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))

sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

res1 = sim.get_eigenmode_coefficients(mon_trans, [1], eig_parity=mp.ODD_Z)
res2 = sim.get_eigenmode_coefficients(mon_trans, [2], eig_parity=mp.ODD_Z)
p1 = abs(res1.alpha[0,0,0])**2
p2 = abs(res2.alpha[0,0,0])**2
total = p1+p2+1e-30

ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[0].set_title('Ez Time Domain')
axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[1].set_title('|Ez|\u00b2 DFT')
axes[2].bar(['Mode 1\n(fundamental)', 'Mode 2\n(higher)'], [p1/total, p2/total], color=['steelblue','tomato'])
axes[2].set_ylim(0,1.1); axes[2].set_title('Mode Power Decomposition')
axes[2].set_ylabel('Power Fraction')
plt.suptitle('Mode Decomposition Demo', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_mode_decomposition.png', dpi=100, bbox_inches='tight')
print("Done")
