#!/usr/bin/env python3
"""
Pattern: material_dispersion_simulation
Dispersive material simulation: Drude-Lorentz model, frequency-dependent refractive index
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "material_dispersion_simulation"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # Material dispersion example, from the Meep tutorial.  Here, we simply
    # simulate homogenous space filled with a dispersive material, and compute
    # its modes as a function of wavevector k.  Since omega/c = k/n, we can
    # extract the dielectric function epsilon(omega) = (ck/omega)^2.

    cell = mp.Vector3()
    resolution = 20

    # We'll use a dispersive material with two polarization terms, just for
    # illustration.  The first one is a strong resonance at omega=1.1,
    # which leads to a polaritonic gap in the dispersion relation.  The second
    # one is a weak resonance at omega=0.5, whose main effect is to add a
    # small absorption loss around that frequency.

    susceptibilities = [
        mp.LorentzianSusceptibility(frequency=1.1, gamma=1e-5, sigma=0.5),
        mp.LorentzianSusceptibility(frequency=0.5, gamma=0.1, sigma=2e-5)
    ]

    default_material = mp.Medium(epsilon=2.25, E_susceptibilities=susceptibilities)

    fcen = 1.0
    df = 2.0

    sources = [mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez, center=mp.Vector3())]

    kmin = 0.3
    kmax = 2.2
    k_interp = 99

    kpts = mp.interpolate(k_interp, [mp.Vector3(kmin), mp.Vector3(kmax)])

    sim = mp.Simulation(
        cell_size=cell,
        geometry=[],
        sources=sources,
        default_material=default_material,
        resolution=resolution
    )

    all_freqs = sim.run_k_points(200, kpts)  # a list of lists of frequencies

    for fs, kx in zip(all_freqs, [v.x for v in kpts]):
        for f in fs:
            print("eps:, {:.6g}, {:.6g}, {:.6g}".format(f.real, f.imag, (kx / f)**2))
    # ─────────────────────────────────────────────────────────

    # figure 자동 저장
    _outputs = []
    if plt.get_fignums():
        _out = savefig_safe(_PATTERN)
        if _out:
            _outputs.append("output.png")

    _elapsed = round(_time.time() - _t0, 2)
    save_result(_PATTERN, outputs=_outputs, elapsed=_elapsed)
    if mp.am_master():
        print(f"[OK] {_PATTERN} ({_elapsed}s) outputs={_outputs}")

except Exception as _e:
    _elapsed = round(_time.time() - _t0, 2)
    save_result(_PATTERN, error=_e, elapsed=_elapsed)
    import traceback
    traceback.print_exc()
    sys.exit(1)
