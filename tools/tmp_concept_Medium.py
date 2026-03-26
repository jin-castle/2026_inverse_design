import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 12, 4
dpml = 1.0
fcen = 1/1.55; df = 0.8*fcen
nfreq = 60
Si   = mp.Medium(epsilon=12)
SiO2 = mp.Medium(epsilon=2.25)
Air  = mp.Medium(epsilon=1)

results = {}
for mat, name in [(Si, 'Si (\u03b5=12)'), (SiO2, 'SiO\u2082 (\u03b5=2.25)'), (Air, 'Air (\u03b5=1)')]:
    sim = mp.Simulation(
        cell_size=mp.Vector3(sx, sy),
        boundary_layers=[mp.PML(dpml)],
        geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=mat)],
        sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                           center=mp.Vector3(-sx/2+dpml+0.5))],
        resolution=resolution
    )
    flux_mon = sim.add_flux(fcen, df*2, nfreq,
                            mp.FluxRegion(center=mp.Vector3(sx/2-dpml-0.5), size=mp.Vector3(0, sy)))
    sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))
    freqs  = mp.get_flux_freqs(flux_mon)
    fluxes = mp.get_fluxes(flux_mon)
    results[name] = (freqs, fluxes)

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
colors = ['steelblue', 'tomato', 'green']
for i, (name, (freqs, fluxes)) in enumerate(results.items()):
    axes[0].plot(freqs, np.array(fluxes)/max(max(f) for _,(_,f) in results.items()), 
                 color=colors[i], label=name, lw=2)
axes[0].set_xlabel('Frequency (c/\u03bcm)'); axes[0].set_ylabel('Normalized Flux')
axes[0].set_title('Waveguide Transmission vs Frequency\n(Different mp.Medium materials)')
axes[0].legend(); axes[0].grid(True, alpha=0.4)
wavelengths = [1e3/f for f in results['Si (\u03b5=12)'][0]]  # nm
for i, (name, (freqs, fluxes)) in enumerate(results.items()):
    axes[1].plot(wavelengths, np.array(fluxes)/max(max(f) for _,(_,f) in results.items()),
                 color=colors[i], label=name, lw=2)
axes[1].set_xlabel('Wavelength (\u03bcm)'); axes[1].set_ylabel('Normalized Flux')
axes[1].set_title('Transmission vs Wavelength')
axes[1].legend(); axes[1].grid(True, alpha=0.4)
plt.suptitle('mp.Medium: Material Definition (Si, SiO\u2082, Air)', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_Medium.png', dpi=100, bbox_inches='tight')
print("Done")
