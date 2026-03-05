#!/usr/bin/env python3
"""
Pattern: ring_mode_overlap
Ring resonator mode overlap: coupling between ring and bus waveguide, mode overlap integral
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "ring_mode_overlap"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # Calculating 2d ring-resonator modes, from the Meep tutorial.

    n = 3.4  # index of waveguide
    w = 1  # width of waveguide
    r = 1  # inner radius of ring

    pad = 4  # padding between waveguide and edge of PML
    dpml = 2  # thickness of PML

    sxy = 2 * (r + w + pad + dpml)  # cell size
    cell = mp.Vector3(sxy, sxy)

    # Create a ring waveguide by two overlapping cylinders - later objects
    # take precedence over earlier objects, so we put the outer cylinder first.
    # and the inner (air) cylinder second.
    geometry = [
        mp.Cylinder(radius=r + w, height=mp.inf, material=mp.Medium(index=n)),
        mp.Cylinder(radius=r, height=mp.inf, material=mp.air),
    ]

    pml_layers = [mp.PML(dpml)]
    resolution = 20

    # If we don't want to excite a specific mode symmetry, we can just
    # put a single point source at some arbitrary place, pointing in some
    # arbitrary direction. We will only look for Ez-polarized modes.

    fcen = 0.118  # pulse center frequency
    df = 0.010  # pulse width (in frequency)
    sources = [
        mp.Source(
            src=mp.GaussianSource(fcen, fwidth=df),
            component=mp.Ez,
            center=mp.Vector3(r + 0.1),
        )
    ]

    # exploit the mirror symmetry in structure+source:
    symmetries = [mp.Mirror(mp.Y)]

    sim = mp.Simulation(
        cell_size=cell,
        resolution=resolution,
        geometry=geometry,
        boundary_layers=pml_layers,
        sources=sources,
        symmetries=symmetries,
    )

    h1 = mp.Harminv(mp.Ez, mp.Vector3(r + 0.1), fcen, df)
    sim.run(mp.after_sources(h1), until_after_sources=300)

    fields2 = sim.fields
    sim.reset_meep()

    fcen = 0.236
    h2 = mp.Harminv(mp.Ez, mp.Vector3(r + 0.1), fcen, df)
    sim.run(mp.after_sources(h2), until_after_sources=300)

    def overlap_integral(r, ez1, ez2):
        return ez1.conjugate() * ez2

    res = sim.integrate2_field_function(fields2, [mp.Ez], [mp.Ez], overlap_integral)
    print(f"overlap integral of mode at w and 2w: {abs(res)}")
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
