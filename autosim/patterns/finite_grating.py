#!/usr/bin/env python3
"""
Pattern: finite_grating
Finite-size grating: finite element of periodic structure. Comparison of diffraction efficiency vs infinite grating
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "finite_grating"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    import math

    # True:  plot the scattered fields in the extended air region adjacent to the grating
    # False: plot the diffraction spectra based on a 1d cross section of the scattered fields
    field_profile = True

    resolution = 50         # pixels/μm

    dpml = 1.0              # PML thickness
    dsub = 2.0              # substrate thickness
    dpad = 1.0              # flat-surface padding
    gp = 1.0                # grating periodicity
    gh = 0.5                # grating height
    gdc = 0.5               # grating duty cycle
    num_cells = 5           # number of grating unit cells

    # air region thickness adjacent to grating
    dair = 10 if field_profile else dpad

    wvl = 0.5               # center wavelength
    fcen = 1/wvl            # center frequency

    k_point = mp.Vector3()

    glass = mp.Medium(index=1.5)

    pml_layers = [mp.PML(thickness=dpml)]

    symmetries=[mp.Mirror(mp.Y)]

    sx = dpml+dsub+gh+dair+dpml
    sy = dpml+dpad+num_cells*gp+dpad+dpml
    cell_size = mp.Vector3(sx,sy)

    src_pt = mp.Vector3(-0.5*sx+dpml+0.5*dsub)
    sources = [mp.Source(mp.GaussianSource(fcen,fwidth=0.2*fcen,is_integrated=True),
                         component=mp.Ez,
                         center=src_pt,
                         size=mp.Vector3(y=sy))]

    geometry = [mp.Block(material=glass,
                         size=mp.Vector3(dpml+dsub,mp.inf,mp.inf),
                         center=mp.Vector3(-0.5*sx+0.5*(dpml+dsub)))]

    sim = mp.Simulation(resolution=resolution,
                        cell_size=cell_size,
                        boundary_layers=pml_layers,
                        geometry=geometry,
                        k_point=k_point,
                        sources=sources,
                        symmetries=symmetries)

    mon_pt = mp.Vector3(0.5*sx-dpml-0.5*dair)
    near_fields = sim.add_dft_fields([mp.Ez], fcen, 0, 1, center=mon_pt, size=mp.Vector3(dair if field_profile else 0,sy-2*dpml))

    sim.run(until_after_sources=100)

    flat_dft = sim.get_dft_array(near_fields, mp.Ez, 0)

    sim.reset_meep()

    for j in range(num_cells):
      geometry.append(mp.Block(material=glass,
                               size=mp.Vector3(gh,gdc*gp,mp.inf),
                               center=mp.Vector3(-0.5*sx+dpml+dsub+0.5*gh,-0.5*sy+dpml+dpad+(j+0.5)*gp)))

    sim = mp.Simulation(resolution=resolution,
                        cell_size=cell_size,
                        boundary_layers=pml_layers,
                        geometry=geometry,
                        k_point=k_point,
                        sources=sources,
                        symmetries=symmetries)

    near_fields = sim.add_dft_fields([mp.Ez], fcen, 0, 1, center=mon_pt, size=mp.Vector3(dair if field_profile else 0,sy-2*dpml))

    sim.run(until_after_sources=100)

    grating_dft = sim.get_dft_array(near_fields, mp.Ez, 0)

    scattered_field = grating_dft-flat_dft
    scattered_amplitude = np.abs(scattered_field)**2

    [x,y,z,w] = sim.get_array_metadata(dft_cell=near_fields)

    if field_profile:
      if mp.am_master():
        plt.figure(dpi=150)
        plt.pcolormesh(x,y,np.rot90(scattered_amplitude),cmap='inferno',shading='gouraud',vmin=0,vmax=scattered_amplitude.max())
        plt.gca().set_aspect('equal')
        plt.xlabel('x (μm)')
        plt.ylabel('y (μm)')

        # ensure that the height of the colobar matches that of the plot
        from mpl_toolkits.axes_grid1 import make_axes_locatable
        divider = make_axes_locatable(plt.gca())
        cax = divider.append_axes("right", size="5%", pad=0.05)
        plt.colorbar(cax=cax)
        plt.tight_layout()
        # plt.show() suppressed
    else:
      ky = np.fft.fftshift(np.fft.fftfreq(len(scattered_field), 1/resolution))
      FT_scattered_field = np.fft.fftshift(np.fft.fft(scattered_field))
      if mp.am_master():
        plt.figure(dpi=150)
        plt.subplots_adjust(hspace=0.3)

        plt.subplot(2,1,1)
        plt.plot(y,scattered_amplitude,'bo-')
        plt.xlabel("y (μm)")
        plt.ylabel("field amplitude")

        plt.subplot(2,1,2)
        plt.plot(ky,np.abs(FT_scattered_field)**2,'ro-')
        plt.gca().ticklabel_format(axis='y',style='sci',scilimits=(0,0))
        plt.xlabel(r'wavevector k$_y$, 2π (μm)$^{-1}$')
        plt.ylabel("Fourier transform")
        plt.gca().set_xlim([-3, 3])

        plt.tight_layout(pad=1.0)
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
