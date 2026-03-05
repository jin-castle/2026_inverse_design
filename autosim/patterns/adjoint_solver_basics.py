#!/usr/bin/env python3
"""
Pattern: adjoint_solver_basics
MEEP adjoint solver fundamentals: set up OptimizationProblem, define FOM using EigenmodeCoefficient, run forward + adjoi
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "adjoint_solver_basics"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    try:
        pass
    except:
        import adjoint as mpa

    import unittest
    from enum import Enum
    mp.quiet(True)

    MonitorObject = Enum('MonitorObject', 'EIGENMODE DFT')

    resolution = 25

    silicon = mp.Medium(epsilon=12)

    sxy = 5.0
    cell_size = mp.Vector3(sxy,sxy,0)

    dpml = 1.0
    boundary_layers = [mp.PML(thickness=dpml)]

    eig_parity = mp.EVEN_Y + mp.ODD_Z

    design_shape = mp.Vector3(1.5,1.5)
    design_region_resolution = int(2*resolution)
    Nx = int(design_region_resolution*design_shape.x)
    Ny = int(design_region_resolution*design_shape.y)

    ## ensure reproducible results
    np.random.seed(9861548)

    ## random design region
    p = np.random.rand(Nx*Ny)

    ## random epsilon perturbation for design region
    deps = 1e-5
    dp = deps*np.random.rand(Nx*Ny)

    w = 1.0
    waveguide_geometry = [mp.Block(material=silicon,
                                   center=mp.Vector3(),
                                   size=mp.Vector3(mp.inf,w,mp.inf))]

    fcen = 1/1.55
    df = 0.23*fcen
    sources = [mp.EigenModeSource(src=mp.GaussianSource(fcen,fwidth=df),
                                  center=mp.Vector3(-0.5*sxy+dpml,0),
                                  size=mp.Vector3(0,sxy),
                                  eig_band=1,
                                  eig_parity=eig_parity)]

    def forward_simulation(design_params,mon_type,frequencies=None):
        matgrid = mp.MaterialGrid(mp.Vector3(Nx,Ny),
                                  mp.air,
                                  silicon,
                                  design_parameters=design_params.reshape(Nx,Ny),
                                  grid_type='U_SUM')
            
        matgrid_geometry = [mp.Block(center=mp.Vector3(),
                                     size=mp.Vector3(design_shape.x,design_shape.y,0),
                                     material=matgrid)]

        geometry = waveguide_geometry + matgrid_geometry

        sim = mp.Simulation(resolution=resolution,
                            cell_size=cell_size,
                            boundary_layers=boundary_layers,
                            sources=sources,
                            geometry=geometry)
        if not frequencies:
            frequencies = [fcen]

        if mon_type.name == 'EIGENMODE':
            mode = sim.add_mode_monitor(frequencies,
                                        mp.ModeRegion(center=mp.Vector3(0.5*sxy-dpml),size=mp.Vector3(0,sxy,0)),
                                        yee_grid=True)

        elif mon_type.name == 'DFT':
            mode = sim.add_dft_fields([mp.Ez],
                                      frequencies,
                                      center=mp.Vector3(1.25),
                                      size=mp.Vector3(0.25,1,0),
                                      yee_grid=False)

        sim.run(until_after_sources=50)

        if mon_type.name == 'EIGENMODE':
            coeff = sim.get_eigenmode_coefficients(mode,[1],eig_parity).alpha[0,:,0]
            S12 = abs(coeff)**2

        elif mon_type.name == 'DFT':
            Ez2 = []
            for f in range(len(frequencies)):
                Ez_dft = sim.get_dft_array(mode, mp.Ez, f)
                Ez2.append(abs(Ez_dft[4,10])**2)
            Ez2 = np.array(Ez2)

        sim.reset_meep()

        if mon_type.name == 'EIGENMODE':
            return S12
        elif mon_type.name == 'DFT':
            return Ez2

    def adjoint_solver(design_params, mon_type, frequencies=None):
        matgrid = mp.MaterialGrid(mp.Vector3(Nx,Ny),
                                  mp.air,
                                  silicon,
                                  design_parameters=np.ones((Nx,Ny)))

        matgrid_region = mpa.DesignRegion(matgrid,
                                          volume=mp.Volume(center=mp.Vector3(),
                                                           size=mp.Vector3(design_shape.x,design_shape.y,0)))

        matgrid_geometry = [mp.Block(center=matgrid_region.center,
                                     size=matgrid_region.size,
                                     material=matgrid)]

        geometry = waveguide_geometry + matgrid_geometry

        sim = mp.Simulation(resolution=resolution,
                            cell_size=cell_size,
                            boundary_layers=boundary_layers,
                            sources=sources,
                            geometry=geometry)
        if not frequencies:
            frequencies = [fcen]

        if mon_type.name == 'EIGENMODE':
            obj_list = [mpa.EigenmodeCoefficient(sim,
                                                 mp.Volume(center=mp.Vector3(0.5*sxy-dpml),
                                                           size=mp.Vector3(0,sxy,0)),1)]

            def J(mode_mon):
                return npa.abs(mode_mon)**2

        elif mon_type.name == 'DFT':
            obj_list = [mpa.FourierFields(sim,
                                          mp.Volume(center=mp.Vector3(1.25),
                                                    size=mp.Vector3(0.25,1,0)),
                                          mp.Ez)]

            def J(mode_mon):
                return npa.abs(mode_mon[:,4,10])**2

        opt = mpa.OptimizationProblem(
            simulation = sim,
            objective_functions = J,
            objective_arguments = obj_list,
            design_regions = [matgrid_region],
            frequencies=frequencies,
            decay_fields=[mp.Ez])

        f, dJ_du = opt([design_params])

        sim.reset_meep()

        return f, dJ_du

    def mapping(x,filter_radius,eta,beta):
        filtered_field = mpa.conic_filter(x,filter_radius,design_shape.x,design_shape.y,design_region_resolution)

        projected_field = mpa.tanh_projection(filtered_field,beta,eta)

        return projected_field.flatten()

    class TestAdjointSolver(unittest.TestCase):

        def test_adjoint_solver_DFT_fields(self):
            print("*** TESTING DFT ADJOINT FEATURES ***")
            ## test the single frequency and multi frequency cases
            for frequencies in [[fcen], [1/1.58, fcen, 1/1.53]]:
                ## compute gradient using adjoint solver
                adjsol_obj, adjsol_grad = adjoint_solver(p, MonitorObject.DFT, frequencies)

                ## compute unperturbed S12
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
