"""
Resolution sweep 검증 — Single2022 파라미터로 res=10,20,30,40,50 비교
목표: res 낮춰도 정성적(색 분리) 결과가 비슷한지 확인
"""
import meep as mp
import numpy as np
import json, time, sys

mp.verbosity(0)

um_scale = 1
Air  = mp.Medium(index=1.0)
TiO2 = mp.Medium(index=2.3)
SiO2 = mp.Medium(index=1.45)

# Single2022 파라미터
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
z_mon  = -99  # placeholder

pillar_mask = [
    [0,0,0,0,0,0,1,1,0,0,0,1,0,1,0,0,0,0,0,1],
    [0,0,0,0,0,0,1,1,0,1,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,1,0,1,1,1,0,0,0,0,0,0,0,0,0,0],
    [1,0,0,0,0,1,1,0,1,1,0,1,0,0,0,0,0,0,0,0],
    [0,0,0,0,1,1,1,0,1,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,1,0,1,1,1,0,0,1,0,0,0,0,0,0,0],
    [0,0,0,0,1,1,1,0,1,0,0,0,0,0,0,0,0,0,0,1],
    [0,1,0,1,1,1,0,1,1,0,0,1,0,0,1,0,0,0,0,0],
    [0,0,0,1,1,0,1,1,1,1,0,0,1,0,0,0,1,0,0,1],
    [0,0,1,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0],
    [1,1,1,1,1,0,1,0,1,1,0,1,0,0,1,0,1,1,1,0],
    [1,1,1,1,0,1,0,1,0,1,0,1,1,1,1,1,1,1,0,0],
    [0,1,0,1,1,0,1,0,1,0,1,1,1,0,1,0,0,1,1,1],
    [1,1,1,0,0,1,0,1,0,1,1,1,0,1,0,1,1,0,1,1],
    [0,1,0,1,0,0,1,0,1,0,1,0,1,1,1,1,1,1,0,0],
    [0,1,1,1,0,0,0,1,0,1,1,1,1,1,0,1,0,0,0,0],
    [0,1,1,0,1,1,0,1,1,1,0,1,1,0,0,0,0,0,0,0],
    [0,1,1,1,1,0,1,0,1,1,1,0,0,0,0,0,0,0,0,0],
    [0,1,1,1,1,1,1,1,1,1,0,0,1,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,1,0,1,1,0,0,0,0,0,0,1,0,0,0],
]

def run_one(resolution):
    t0 = time.time()
    z_mon_r = round(-Sz/2 + Lpml + mon_2_pml - 1/resolution, 2)
    z_refl  = round(Sz/2 - Lpml - 1/resolution, 2)

    pml_layers = [mp.PML(thickness=Lpml, direction=mp.Z)]
    cell_size  = mp.Vector3(Sx, Sy, Sz)

    geometry = [
        mp.Block(center=mp.Vector3(0,0,round(Sz/2-Lpml/2-pml_2_src/2-src_2_geo/2,3)),
                 size=mp.Vector3(Sx,Sy,round(Lpml+pml_2_src+src_2_geo,3)), material=SiO2),
        mp.Block(center=mp.Vector3(0,0,z_fl), size=mp.Vector3(Sx,Sy,FL_thickness), material=Air),
        mp.Block(center=mp.Vector3(0,0,z_sipd), size=mp.Vector3(Sx,Sy,round(mon_2_pml+Lpml,2)), material=Air),
    ]
    for i in range(20):
        for j in range(20):
            if pillar_mask[i][j] == 1:
                px = round(-10*w + j*w + w/2, 2)
                py = round(10*w - i*w - w/2, 2)
                geometry.append(mp.Block(size=mp.Vector3(w,w,Layer_thickness),
                                center=mp.Vector3(px,py,z_meta), material=TiO2))

    fcen = (1/0.350 + 1/0.800)/2
    df   = 1/0.350 - 1/0.800
    nfreq = 50  # 빠른 sweep용

    src_obj = mp.GaussianSource(frequency=fcen, fwidth=df)
    source  = [mp.Source(src_obj, component=mp.Ex,
                         size=mp.Vector3(Sx,Sy,0), center=mp.Vector3(0,0,z_src))]

    # 참조 시뮬
    sim_ref = mp.Simulation(cell_size=cell_size, boundary_layers=pml_layers,
        geometry=[mp.Block(center=mp.Vector3(0,0,0),size=mp.Vector3(Sx,Sy,Sz),material=Air)],
        sources=source, default_material=Air, resolution=resolution,
        k_point=mp.Vector3(0,0,0), extra_materials=[SiO2])

    refl_fr = mp.FluxRegion(center=mp.Vector3(0,0,z_refl),   size=mp.Vector3(Sx,Sy,0))
    tran_fr = mp.FluxRegion(center=mp.Vector3(0,0,z_mon_r),  size=mp.Vector3(Sx,Sy,0))
    refl_r  = sim_ref.add_flux(fcen,df,nfreq,refl_fr)
    tran_r  = sim_ref.add_flux(fcen,df,nfreq,tran_fr)
    sim_ref.run(until_after_sources=mp.stop_when_dft_decayed(1e-4, 0))
    straight_refl = sim_ref.get_flux_data(refl_r)
    total_flux    = mp.get_fluxes(tran_r)
    flux_freqs    = mp.get_flux_freqs(tran_r)

    # 메인 시뮬
    sim = mp.Simulation(cell_size=cell_size, boundary_layers=pml_layers,
        geometry=geometry, sources=source, default_material=Air, resolution=resolution,
        k_point=mp.Vector3(0,0,0), eps_averaging=False, extra_materials=[SiO2,TiO2])

    sim.load_minus_flux_data(sim.add_flux(fcen,df,nfreq,refl_fr), straight_refl)
    tran_m  = sim.add_flux(fcen,df,nfreq,tran_fr)
    tran_px = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(0,0,z_mon_r),
                                                         size=mp.Vector3(Sx,Sy,0)))
    dx = dy = Sx
    tran_R  = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(-dx/4,-dy/4,z_mon_r),size=mp.Vector3(dx/2,dy/2,0)))
    tran_Gr = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(-dx/4,+dy/4,z_mon_r),size=mp.Vector3(dx/2,dy/2,0)))
    tran_B  = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(+dx/4,+dy/4,z_mon_r),size=mp.Vector3(dx/2,dy/2,0)))
    tran_Gb = sim.add_flux(fcen,df,nfreq,mp.FluxRegion(center=mp.Vector3(+dx/4,-dy/4,z_mon_r),size=mp.Vector3(dx/2,dy/2,0)))
    sim.load_minus_flux_data(sim.fields, straight_refl) if False else None

    sim.run(until_after_sources=mp.stop_when_dft_decayed(1e-4, 0))

    tran_p = mp.get_fluxes(tran_px)
    r_f    = mp.get_fluxes(tran_R)
    gr_f   = mp.get_fluxes(tran_Gr)
    b_f    = mp.get_fluxes(tran_B)
    gb_f   = mp.get_fluxes(tran_Gb)
    wl_arr = np.array([1/flux_freqs[d] for d in range(nfreq)])

    def eff_at(wl_t, fl):
        idx = np.argmin(np.abs(wl_arr - wl_t))
        return max(0, fl[idx] / (tran_p[idx] + 1e-20))

    elapsed = time.time() - t0
    return {
        "res": resolution,
        "elapsed_sec": round(elapsed, 1),
        "R":  round(eff_at(0.65, r_f),  3),
        "G":  round(eff_at(0.55, [gr_f[d]+gb_f[d] for d in range(nfreq)]), 3),
        "B":  round(eff_at(0.45, b_f),  3),
        "Nvox": int(Sx*resolution)**2 * int(Sz*resolution),
    }

if __name__ == "__main__":
    target_res = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    result = run_one(target_res)
    print(json.dumps(result))
