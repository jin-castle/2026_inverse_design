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

eps   = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_td = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
im0 = axes[0].imshow(eps.T, cmap='viridis', origin='lower', aspect='auto',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im0, ax=axes[0], label='\u03b5_r (relative permittivity)')
axes[0].set_title('Dielectric Map: \u03b5_r = get_array(mp.Dielectric)\nSi (\u03b5=12) / Air (\u03b5=1)')
axes[0].set_xlabel('x (\u03bcm)'); axes[0].set_ylabel('y (\u03bcm)')
im1 = axes[1].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im1, ax=axes[1], label='Ez')
axes[1].set_title('Ez Field Distribution')
axes[1].set_xlabel('x (\u03bcm)'); axes[1].set_ylabel('y (\u03bcm)')
plt.suptitle('epsilon_r: Relative Permittivity Distribution', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_epsilon_r.png', dpi=100, bbox_inches='tight')
print("Done")
