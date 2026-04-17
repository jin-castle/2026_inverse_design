"""
Resolution sweep — 결과를 파일로 저장
"""
import meep as mp
import numpy as np
import json, time, sys

mp.verbosity(0)

um_scale = 1
Air  = mp.Medium(index=1.0)
TiO2 = mp.Medium(index=2.3)
SiO2 = mp.Medium(index=1.45)

Layer_thickness = 0.3
FL_thickness    = 2.0
SP_size         = 0.8
w               = 0.08
Lpml = 0.4; pml_2_src = 0.2; src_2_geo = 0.2; mon_2_pml = 0.4

Sx = Sy = round(SP_size * 2, 2)
Sz = round(Lpml + pml_2_src + src_2_geo + Layer_thickness + FL_thickness + mon_2_pml + Lpml, 2)
z_src  = round(Sz/2 - Lpml - pml_2_src, 2)
z_meta = round(Sz/2 - Lpml - pml_2_src - src_2_geo - Layer_thickness/2, 2)
z_fl   = round(Sz/2 - Lpml - pml_2_src - src_2_geo - Layer_thickness - FL_thickness/2, 2)
z_sipd = round(Sz/2 - Lpml - pml_2_src - src_2_geo - Layer_thickness - FL_thickness - mon_2_pml/2 - Lpml/2, 2)

pillar_mask = [
    [0,0,0,0,0,0,1,1,0,0,0,1,0,1,0,0,0,0,0,1],[0,0,0,0,0,0,1,1,0,1,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,1,0,1,1,1,0,0,0,0,0,0,0,0,0,0],[1,0,0,0,0,1,1,0,1,1,0,1,0,0,0,0,0,0,0,0],
    [0,0,0,0,1,1,1,0,1,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,1,0,1,1,1,0,0,1,0,0,0,0,0,0,0],
    [0,0,0,0,1,1,1,0,1,0,0,0,0,0,0,0,0,0,0,1],[0,1,0,1,1,1,0,1,1,0,0,1,0,0,1,0,0,0,0,0],
    [0,0,0,1,1,0,1,1,1,1,0,0,1,0,0,0,1,0,0,1],[0,0,1,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0],
    [1,1,1,1,1,0,1,0,1,1,0,1,0,0,1,0,1,1,1,0],[1,1,1,1,0,1,0,1,0,1,0,1,1,1,1,1,1,1,0,0],
    [0,1,0,1,1,0,1,0,1,0,1,1,1,0,1,0,0,1,1,1],[1,1,1,0,0,1,0,1,0,1,1,1,0,1,0,1,1,0,1,1],
    [0,1,0,1,0,0,1,0,1,0,1,0,1,1,1,1,1,1,0,0],[0,1,1,1,0,0,0,1,0,1,1,1,1,1,0,1,0,0,0,0],
    [0,1,1,0,1,1,0,1,1,1,0,1,1,0,0,0,0,0,0,0],[0,1,1,1,1,0,1,0,1,1,1,0,0,0,0,0,0,0,0,0],
    [0,1,1,1,1,1,1,1,1,1,0,0,1,0,0,0,0,0,0,0],[0,0,0,0,0,0,1,0,1,1,0,0,0,0,0,0,1,0,0,0],
]

def run_one(resolution):
    t0 = time.time()
    z_mon_r = round(-Sz/2 + Lpml + mon_2_pml - 1/resolution, 2)
    z_refl  = round(Sz/2 - Lpml - 1/resolution, 2)

    cell_size  = mp.Vector3(Sx, Sy, Sz)
    pml_layers = [mp.PML(thickness=Lpml, direction=mp.Z)]

    geometry = [
        mp.Block(center=mp.Vector3(0,0,round(Sz/2-Lpml/2-pml_2_src/2-src_2_geo/2,3)),
                 size=mp.Vector3(Sx,Sy,round(Lpml+pml_2_src+src_2_geo,3)), material=SiO2),
        mp.Block(center=mp.Vector3(0,0,z_fl), size=mp.Vector3(Sx,Sy,FL_thickness), material=Air),
        mp.Block(center=mp.Vector3(0,0,z_sipd), size=mp.Vector3(Sx,Sy,round(mon_2_pml+Lpml,2)), material=Air),
    ]
    for i in range(20):
        for j in range(20):
            if pillar_mask[i][j]:
                px = round(-10*w + j*w + w/2, 2)
                py = round(10*w  - i*w - w/2, 2)
                geometry.append(mp.Block(size=mp.Vector3(w,w,Layer_thickness),
                                center=mp.Vector3(px,py,z_meta), material=TiO2))

    fcen  = (1/0.350 + 1/0.800)/2
    df    = 1/0.350 - 1/0.800
    nfreq = 50
    src_o = mp.GaussianSource(frequency=fcen, fwidth=df)
    source= [mp.Source(src_o, component=mp.Ex,
                       size=mp.Vector3(Sx,Sy,0), center=mp.Vector3(0,0,z_src))]

    # 참조
    sim_r = mp.Simulation(cell_size=cell_size, boundary_layers=pml_layers,
        geometry=[mp.Block(center=mp.Vector3(0,0,0),size=mp.Vector3(Sx,Sy,Sz),material=Air)],
        sources=source, default_material=Air, resolution=resolution,
        k_point=mp.Vector3(0,0,0), extra_materials=[SiO2])
    refl_fr = mp.FluxRegion(center=mp.Vector3(0,0,z_refl), size=mp.Vector3(Sx,Sy,0))
    tran_fr = mp.FluxRegion(center=mp.Vector3(0,0,z_mon_r), size=mp.Vector3(Sx,Sy,0))
    rr = sim_r.add_flux(fcen,df,nfreq,refl_fr)
    tr = sim_r.add_flux(fcen,df,nfreq,tran_fr)
    sim_r.run(until_after_sources=mp.stop_when_dft_decayed(1e-4, 0))
    srd      = sim_r.get_flux_data(rr)
    tot_flux = mp.get_fluxes(tr)
    freqs    = mp.get_flux_freqs(tr)
    wl_arr   = np.array([1/freqs[d] for d in range(nfreq)])

    # 메인
    sim = mp.Simulation(cell_size=cell_size, boundary_layers=pml_layers,
        geometry=geometry, sources=source, default_material=Air,
        resolution=resolution, k_point=mp.Vector3(0,0,0), eps_averaging=False,
        extra_materials=[SiO2, TiO2])

    rfl = sim.add_flux(fcen,df,nfreq,refl_fr); sim.load_minus_flux_data(rfl, srd)
    tpx = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(0,0,z_mon_r),size=mp.Vector3(Sx,Sy,0)))
    dx=dy=Sx
    tR  = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(-dx/4,-dy/4,z_mon_r),size=mp.Vector3(dx/2,dy/2,0)))
    tGr = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(-dx/4,+dy/4,z_mon_r),size=mp.Vector3(dx/2,dy/2,0)))
    tB  = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(+dx/4,+dy/4,z_mon_r),size=mp.Vector3(dx/2,dy/2,0)))
    tGb = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(+dx/4,-dy/4,z_mon_r),size=mp.Vector3(dx/2,dy/2,0)))
    sim.run(until_after_sources=mp.stop_when_dft_decayed(1e-4, 0))

    tp   = mp.get_fluxes(tpx)
    rf   = mp.get_fluxes(tR)
    grf  = mp.get_fluxes(tGr)
    bf   = mp.get_fluxes(tB)
    gbf  = mp.get_fluxes(tGb)

    def eff(wl_t, fl, fl2=None):
        idx = np.argmin(np.abs(wl_arr - wl_t))
        tot = (fl[idx] + (fl2[idx] if fl2 else 0))
        return round(max(0, tot / (tp[idx]+1e-20)), 3)

    elapsed = time.time() - t0
    result = {
        "res": resolution,
        "elapsed_sec": round(elapsed,1),
        "R":  eff(0.65, rf),
        "G":  eff(0.55, grf, gbf),
        "B":  eff(0.45, bf),
        "Nvox": int(Sx*resolution)**2 * int(Sz*resolution),
        "grids_80nm": round(0.08*resolution, 1),
    }
    out = f"/tmp/res_sweep_{resolution}.json"
    with open(out, "w") as f:
        json.dump(result, f)

target_res = int(sys.argv[1]) if len(sys.argv) > 1 else 20
run_one(target_res)
