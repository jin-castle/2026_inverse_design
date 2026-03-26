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

# Track field values over time
times_list = []
ez_max_list = []

def record_field(sim):
    ez = sim.get_array(component=mp.Ez, center=mp.Vector3(sx/2-dpml-1), size=mp.Vector3(0.1, 0.1))
    times_list.append(sim.meep_time())
    ez_max_list.append(float(np.max(np.abs(ez))))

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

sim.run(
    mp.at_every(1, record_field),
    until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6)
)

ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
axes[0].semilogy(times_list, ez_max_list, 'b-')
axes[0].axhline(max(ez_max_list)*1e-6, color='r', ls='--', label='decay threshold 1e-6')
axes[0].set_xlabel('MEEP time'); axes[0].set_ylabel('|Ez| max')
axes[0].set_title('Field Decay at Monitor Point\n(stop_when_fields_decayed)')
axes[0].legend(); axes[0].grid(True, alpha=0.4)
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[1].set_title('|Ez|\u00b2 DFT at Convergence')
plt.colorbar(im1, ax=axes[1])
plt.suptitle('stop_when_fields_decayed: Automatic Termination', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_stop_when_fields_decayed.png', dpi=100, bbox_inches='tight')
print("Done")
