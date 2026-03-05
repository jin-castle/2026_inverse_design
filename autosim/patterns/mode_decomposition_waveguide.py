#!/usr/bin/env python3
"""
Pattern: mode_decomposition_waveguide
Complete example of waveguide mode decomposition: EigenModeSource + get_eigenmode_coefficients, transmission/reflection 
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "mode_decomposition_waveguide"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # -*- coding: utf-8 -*-

    resolution = 25   # pixels/μm

    w1 = 1.0          # width of waveguide 1
    w2 = 2.0          # width of waveguide 2
    Lw = 10.0         # length of waveguides 1 and 2

    # lengths of waveguide taper
    Lts = [2**m for m in range(4)]

    dair = 3.0        # length of air region
    dpml_x = 6.0      # length of PML in x direction
    dpml_y = 2.0      # length of PML in y direction

    sy = dpml_y+dair+w2+dair+dpml_y

    Si = mp.Medium(epsilon=12.0)

    boundary_layers = [mp.PML(dpml_x,direction=mp.X),
                       mp.PML(dpml_y,direction=mp.Y)]

    lcen = 6.67       # mode wavelength
    fcen = 1/lcen     # mode frequency

    symmetries = [mp.Mirror(mp.Y)]

    R_coeffs = []
    R_flux = []

    for Lt in Lts:
        sx = dpml_x+Lw+Lt+Lw+dpml_x
        cell_size = mp.Vector3(sx,sy,0)

        src_pt = mp.Vector3(-0.5*sx+dpml_x+0.2*Lw)
        sources = [mp.EigenModeSource(src=mp.GaussianSource(fcen,fwidth=0.2*fcen),
                                      center=src_pt,
                                      size=mp.Vector3(y=sy-2*dpml_y),
                                      eig_match_freq=True,
                                      eig_parity=mp.ODD_Z+mp.EVEN_Y)]

        # straight waveguide
        vertices = [mp.Vector3(-0.5*sx-1,0.5*w1),
                    mp.Vector3(0.5*sx+1,0.5*w1),
                    mp.Vector3(0.5*sx+1,-0.5*w1),
                    mp.Vector3(-0.5*sx-1,-0.5*w1)]

        sim = mp.Simulation(resolution=resolution,
                            cell_size=cell_size,
                            boundary_layers=boundary_layers,
                            geometry=[mp.Prism(vertices,height=mp.inf,material=Si)],
                            sources=sources,
                            symmetries=symmetries)

        mon_pt = mp.Vector3(-0.5*sx+dpml_x+0.7*Lw)
        flux = sim.add_flux(fcen,0,1,mp.FluxRegion(center=mon_pt,size=mp.Vector3(y=sy-2*dpml_y)))

        sim.run(until_after_sources=mp.stop_when_fields_decayed(50,mp.Ez,mon_pt,1e-9))

        res = sim.get_eigenmode_coefficients(flux,[1],eig_parity=mp.ODD_Z+mp.EVEN_Y)
        incident_coeffs = res.alpha
        incident_flux = mp.get_fluxes(flux)
        incident_flux_data = sim.get_flux_data(flux)

        sim.reset_meep()

        # linear taper
        vertices = [mp.Vector3(-0.5*sx-1,0.5*w1),
                    mp.Vector3(-0.5*Lt,0.5*w1),
                    mp.Vector3(0.5*Lt,0.5*w2),
                    mp.Vector3(0.5*sx+1,0.5*w2),
                    mp.Vector3(0.5*sx+1,-0.5*w2),
                    mp.Vector3(0.5*Lt,-0.5*w2),
                    mp.Vector3(-0.5*Lt,-0.5*w1),
                    mp.Vector3(-0.5*sx-1,-0.5*w1)]

        sim = mp.Simulation(resolution=resolution,
                            cell_size=cell_size,
                            boundary_layers=boundary_layers,
                            geometry=[mp.Prism(vertices,height=mp.inf,material=Si)],
                            sources=sources,
                            symmetries=symmetries)

        flux = sim.add_flux(fcen,0,1,mp.FluxRegion(center=mon_pt,size=mp.Vector3(y=sy-2*dpml_y)))
        sim.load_minus_flux_data(flux,incident_flux_data)

        sim.run(until_after_sources=mp.stop_when_fields_decayed(50,mp.Ez,mon_pt,1e-9))

        res2 = sim.get_eigenmode_coefficients(flux,[1],eig_parity=mp.ODD_Z+mp.EVEN_Y)
        taper_coeffs = res2.alpha
        taper_flux = mp.get_fluxes(flux)

        R_coeffs.append(abs(taper_coeffs[0,0,1])**2/abs(incident_coeffs[0,0,0])**2)
        R_flux.append(-taper_flux[0]/incident_flux[0])
        print("refl:, {}, {:.8f}, {:.8f}".format(Lt,R_coeffs[-1],R_flux[-1]))

    if mp.am_master():
        plt.figure()
        plt.loglog(Lts,R_coeffs,'bo-',label='mode decomposition')
        plt.loglog(Lts,R_flux,'ro-',label='Poynting flux')
        plt.loglog(Lts,[0.005/Lt**2 for Lt in Lts],'k-',label=r'quadratic reference (1/Lt$^2$)')
        plt.legend(loc='upper right')
        plt.xlabel('taper length Lt (μm)')
        plt.ylabel('reflectance')
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
