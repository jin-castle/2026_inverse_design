#!/usr/bin/env python3
"""
Pattern: solve_cw_steady_state
CW steady-state simulation: solve_cw, convergence condition, ContinuousSource
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "solve_cw_steady_state"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    n = 3.4
    w = 1
    r = 1
    pad = 4
    dpml = 2

    sxy = 2*(r+w+pad+dpml)
    cell_size = mp.Vector3(sxy,sxy)

    pml_layers = [mp.PML(dpml)]

    nonpml_vol = mp.Volume(mp.Vector3(), size=mp.Vector3(sxy-2*dpml,sxy-2*dpml))

    geometry = [mp.Cylinder(radius=r+w, material=mp.Medium(index=n)),
                mp.Cylinder(radius=r)]

    fcen = 0.118

    src = [mp.Source(mp.ContinuousSource(fcen),
                     component=mp.Ez,
                     center=mp.Vector3(r+0.1)),
           mp.Source(mp.ContinuousSource(fcen),
                     component=mp.Ez,
                     center=mp.Vector3(-(r+0.1)),
                     amplitude=-1)]

    symmetries = [mp.Mirror(mp.X,phase=-1),
                  mp.Mirror(mp.Y,phase=+1)]

    sim = mp.Simulation(cell_size=cell_size,
                        geometry=geometry,
                        sources=src,
                        resolution=10,
                        force_complex_fields=True,
                        symmetries=symmetries,
                        boundary_layers=pml_layers)

    num_tols = 5
    tols = np.power(10, np.arange(-8.0,-8.0-num_tols,-1.0))
    ez_dat = np.zeros((122,122,num_tols), dtype=np.complex_)

    for i in range(num_tols):
        sim.init_sim()
        sim.solve_cw(tols[i], 10000, 10)
        ez_dat[:,:,i] = sim.get_array(vol=nonpml_vol, component=mp.Ez)

    err_dat = np.zeros(num_tols-1)
    for i in range(num_tols-1):
        err_dat[i] = LA.norm(ez_dat[:,:,i]-ez_dat[:,:,num_tols-1])

    plt.figure(dpi=150)
    plt.loglog(tols[:num_tols-1], err_dat, 'bo-');
    plt.xlabel("frequency-domain solver tolerance");
    plt.ylabel("L2 norm of error in fields");
    # plt.show() suppressed

    eps_data = sim.get_array(vol=nonpml_vol, component=mp.Dielectric)
    ez_data = np.real(ez_dat[:,:,num_tols-1])

    plt.figure()
    plt.imshow(eps_data.transpose(), interpolation='spline36', cmap='binary')
    plt.imshow(ez_data.transpose(), interpolation='spline36', cmap='RdBu', alpha=0.9)
    plt.axis('off')
    # plt.show() suppressed

    if np.all(np.diff(err_dat) < 0):
        print("PASSED solve_cw test: error in the fields is decreasing with increasing resolution")
    else:
        print("FAILED solve_cw test: error in the fields is NOT decreasing with increasing resolution")

    sim.reset_meep()

    df = 0.08
    src = [mp.Source(mp.GaussianSource(fcen,fwidth=df),
                     component=mp.Ez,
                     center=mp.Vector3(r+0.1)),
           mp.Source(mp.GaussianSource(fcen,fwidth=df),
                     component=mp.Ez,
                     center=mp.Vector3(-(r+0.1)),
                     amplitude=-1)]

    sim = mp.Simulation(cell_size=mp.Vector3(sxy,sxy),
                        geometry=geometry,
                        sources=src,
                        resolution=10,
                        symmetries=symmetries,
                        boundary_layers=pml_layers)

    dft_obj = sim.add_dft_fields([mp.Ez], fcen, 0, 1, where=nonpml_vol)

    sim.run(until_after_sources=100)

    eps_data = sim.get_array(vol=nonpml_vol, component=mp.Dielectric)
    ez_data = np.real(sim.get_dft_array(dft_obj, mp.Ez, 0))

    plt.figure()
    plt.imshow(eps_data.transpose(), interpolation='spline36', cmap='binary')
    plt.imshow(ez_data.transpose(), interpolation='spline36', cmap='RdBu', alpha=0.9)
    plt.axis('off')
    # plt.show() suppressed
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
