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

# Time profile of GaussianSource
t_arr = np.linspace(0, 60, 2000)
# GaussianSource envelope: Gaussian * cos(2pi*fcen*t)
t0 = 1.0/df  # peak time
width = t0
src_envelope = np.exp(-((t_arr - t0)**2) / (2*width**2))
src_signal = src_envelope * np.cos(2*np.pi*fcen*t_arr)

# Frequency spectrum via FFT
dt = t_arr[1]-t_arr[0]
freqs_fft = np.fft.rfftfreq(len(t_arr), d=dt)
spectrum = np.abs(np.fft.rfft(src_signal))**2
spectrum /= spectrum.max()

# Run simulation
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
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
# Time profile
axes[0].plot(t_arr, src_signal, 'b-', lw=1, alpha=0.7, label='Signal')
axes[0].plot(t_arr, src_envelope, 'r--', lw=2, label='Envelope')
axes[0].set_xlabel('Time'); axes[0].set_ylabel('Amplitude')
axes[0].set_title(f'GaussianSource Time Profile\nfcen={fcen:.3f}, df={df:.3f}')
axes[0].legend(); axes[0].grid(True, alpha=0.4)
# Spectrum
mask = (freqs_fft > fcen-df*1.5) & (freqs_fft < fcen+df*1.5)
axes[1].plot(freqs_fft[mask], spectrum[mask], 'g-', lw=2)
axes[1].axvline(fcen, color='r', ls='--', label=f'fcen={fcen:.3f}')
axes[1].axvline(fcen-df/2, color='orange', ls=':', label='FWHM')
axes[1].axvline(fcen+df/2, color='orange', ls=':')
axes[1].set_xlabel('Frequency'); axes[1].set_ylabel('Power (normalized)')
axes[1].set_title('Frequency Spectrum'); axes[1].legend(fontsize=8)
axes[1].grid(True, alpha=0.4)
# DFT field
im = axes[2].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[2].set_title('|Ez|\u00b2 DFT at fcen')
plt.colorbar(im, ax=axes[2])
plt.suptitle('GaussianSource: Broadband Pulse Source', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_GaussianSource.png', dpi=100, bbox_inches='tight')
print("Done")
