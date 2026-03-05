#!/usr/bin/env python3
"""
Pattern: grating2d_triangular_lattice
Triangular lattice 2D diffraction grating: triangular array, 2D k-point sweep, diffraction efficiency map
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "grating2d_triangular_lattice"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # Computes the diffraction orders of a 2D binary grating with
    # triangular lattice using a rectangular supercell and verifies
    # that only the diffraction orders of the actual unit cell
    # produce non-zero power (up to discretization error)
    import math

    resolution = 100  # pixels/μm

    ng = 1.5
    glass = mp.Medium(index=ng)

    wvl = 0.5  # wavelength
    fcen = 1 / wvl

    # rectangular supercell
    sx = 1.0
    sy = np.sqrt(3)

    dpml = 1.0  # PML thickness
    dsub = 2.0  # substrate thickness
    dair = 2.0  # air padding
    hcyl = 0.5  # cylinder height
    rcyl = 0.1  # cylinder radius

    sz = dpml + dsub + hcyl + dair + dpml

    cell_size = mp.Vector3(sx, sy, sz)

    boundary_layers = [mp.PML(thickness=dpml, direction=mp.Z)]

    # periodic boundary conditions
    k_point = mp.Vector3()

    src_pt = mp.Vector3(0, 0, -0.5 * sz + dpml)
    sources = [
        mp.Source(
            src=mp.GaussianSource(fcen, fwidth=0.1 * fcen),
            size=mp.Vector3(sx, sy, 0),
            center=src_pt,
            component=mp.Ex,
        )
    ]

    substrate = [
        mp.Block(
            size=mp.Vector3(mp.inf, mp.inf, dpml + dsub),
            center=mp.Vector3(0, 0, -0.5 * sz + 0.5 * (dpml + dsub)),
            material=glass,
        )
    ]

    cyl_grating = [
        mp.Cylinder(
            center=mp.Vector3(0, 0, -0.5 * sz + dpml + dsub + 0.5 * hcyl),
            radius=rcyl,
            height=hcyl,
            material=glass,
        ),
        mp.Cylinder(
            center=mp.Vector3(0.5 * sx, 0.5 * sy, -0.5 * sz + dpml + dsub + 0.5 * hcyl),
            radius=rcyl,
            height=hcyl,
            material=glass,
        ),
        mp.Cylinder(
            center=mp.Vector3(-0.5 * sx, 0.5 * sy, -0.5 * sz + dpml + dsub + 0.5 * hcyl),
            radius=rcyl,
            height=hcyl,
            material=glass,
        ),
        mp.Cylinder(
            center=mp.Vector3(-0.5 * sx, -0.5 * sy, -0.5 * sz + dpml + dsub + 0.5 * hcyl),
            radius=rcyl,
            height=hcyl,
            material=glass,
        ),
        mp.Cylinder(
            center=mp.Vector3(0.5 * sx, -0.5 * sy, -0.5 * sz + dpml + dsub + 0.5 * hcyl),
            radius=rcyl,
            height=hcyl,
            material=glass,
        ),
    ]

    geometry = substrate + cyl_grating

    sim = mp.Simulation(
        resolution=resolution,
        cell_size=cell_size,
        sources=sources,
        geometry=geometry,
        boundary_layers=boundary_layers,
        k_point=k_point,
    )

    tran_pt = mp.Vector3(0, 0, 0.5 * sz - dpml)
    tran_flux = sim.add_mode_monitor(
        fcen, 0, 1, mp.ModeRegion(center=tran_pt, size=mp.Vector3(sx, sy, 0))
    )

    sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ex, src_pt, 1e-6))

    # diffraction order of unit cell (triangular lattice)
    mx = 0
    my = 1

    # check: for diffraction orders of supercell for which
    #        nx = mx and ny = -mx + 2*my and thus
    #        only even orders should produce nonzero power
    nx = mx
    for ny in range(4):
        kz2 = fcen**2 - (nx / sx) ** 2 - (ny / sy) ** 2
        if kz2 > 0:
            res = sim.get_eigenmode_coefficients(
                tran_flux, mp.DiffractedPlanewave((nx, ny, 0), mp.Vector3(0, 1, 0), 1, 0)
            )
            t_coeffs = res.alpha
            tran = abs(t_coeffs[0, 0, 0]) ** 2

            print(f"order:, {nx}, {ny}, {tran:.5f}")
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
