import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 14, 4
dpml = 1.0
w = 1.0
fcen = 0.25; df = 0.2
Si = mp.Medium(epsilon=12)

# Ring-like resonator: use a Cylinder to create resonance
# Simpler: use a block waveguide with reflections
geometry = [
    mp.Block(size=mp.Vector3(mp.inf, w), material=Si),
    mp.Block(size=mp.Vector3(0.1, w*2), material=mp.Medium(epsilon=1),
             center=mp.Vector3(3, 0)),  # partial gap to create reflection
]

# Record time series at a point
t_data, ez_data = [], []
def record(sim):
    t_data.append(sim.meep_time())
    arr = sim.get_array(component=mp.Ez, center=mp.Vector3(2, 0), size=mp.Vector3(0.1, 0.1))
    ez_data.append(float(np.real(arr.flat[0])))

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=geometry,
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
harminv_obj = mp.Harminv(mp.Ez, mp.Vector3(2, 0), fcen, df)

sim.run(
    mp.at_every(0.5, record),
    mp.after_sources(harminv_obj),
    until_after_sources=300
)

modes = harminv_obj.modes
freqs = [m.freq for m in modes]
Qs    = [abs(m.Q) for m in modes]
amps  = [abs(m.amp) for m in modes]

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
axes[0].plot(t_data, ez_data, 'b-', lw=0.8)
axes[0].set_xlabel('Time (MEEP units)'); axes[0].set_ylabel('Ez')
axes[0].set_title('Time-Domain Signal at Monitor\n(Harminv input)')
axes[0].grid(True, alpha=0.4)
# Spectrum panel
f_range = np.linspace(fcen-df, fcen+df, 400)
gaussian = np.exp(-((f_range-fcen)**2)/(2*(df/3)**2))
axes[1].plot(f_range, gaussian/gaussian.max(), 'b--', alpha=0.5, label='Source spectrum')
if freqs:
    for fi, qi, ai in zip(freqs, Qs, amps):
        axes[1].axvline(fi, color='red', alpha=0.8, lw=2,
                        label=f'f={fi:.3f}, Q={qi:.0f}')
    idx = np.argmax(amps)
    axes[1].scatter(freqs, amps/max(amps), c='red', s=80, zorder=5)
axes[1].set_xlabel('Frequency'); axes[1].set_ylabel('Amplitude (normalized)')
axes[1].set_title(f'Harminv: {len(freqs)} resonance(s) detected')
axes[1].legend(fontsize=7); axes[1].grid(True, alpha=0.4)
plt.suptitle('Harminv: Time-Domain \u2192 Resonance Frequency Extraction', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_Harminv.png', dpi=100, bbox_inches='tight')
print("Done")
