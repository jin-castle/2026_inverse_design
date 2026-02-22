# MEEP Python API Cheatsheet

_자주 사용하는 패턴 요약_

## Simulation 기본 구조
```python
import meep as mp

cell = mp.Vector3(sx, sy, 0)
geom = [mp.Block(...), mp.Cylinder(...)]
src  = [mp.Source(mp.GaussianSource(fcen, fwidth), ...)]
pml  = [mp.PML(dpml)]

sim = mp.Simulation(cell_size=cell, geometry=geom,
                    sources=src, boundary_layers=pml,
                    resolution=res)
sim.run(until_after_sources=mp.stop_when_fields_decayed(50, mp.Ez, ...))
```

## Mode Source (EigenModeSource)
```python
src = mp.EigenModeSource(
    mp.GaussianSource(fcen, fwidth=df),
    center=mp.Vector3(-sx/2+dpml+0.1, 0),
    size=mp.Vector3(0, sy-2*dpml),
    eig_band=1,          # 밴드 번호 (1-indexed)
    eig_parity=mp.ODD_Z, # TE: ODD_Z, TM: EVEN_Z
)
```

## Flux 측정
```python
flux_obj = sim.add_flux(fcen, df, nfreq,
    mp.FluxRegion(center=mp.Vector3(x, 0), size=mp.Vector3(0, sy)))
sim.run(...)
flux_data = mp.get_fluxes(flux_obj)
freqs     = mp.get_flux_freqs(flux_obj)
```

## Adjoint 최적화 (meep.adjoint)
```python
import meep.adjoint as mpa

opt = mpa.OptimizationProblem(
    simulation=sim,
    objective_functions=[J],
    objective_arguments=[ob_list],
    design_regions=[mpa.DesignRegion(...)],
    frequencies=[fcen],
)
f, dJ_du = opt([params], need_gradient=True)
```

## legume GME 기본
```python
import legume

lattice = legume.Lattice('hexagonal')
phc     = legume.PhotCryst(lattice)
phc.add_layer(d=1.0, eps_b=1.0)       # cladding
phc.add_layer(d=h, eps_b=eps_si)      # slab
phc.add_layer(d=1.0, eps_b=1.0)       # substrate

gme = legume.GuidedModeExp(phc, gmax=4.0)
gme.run(kpoints=kpts, gmode_inds=[0], numeig=20)

# 모드 프로파일
fi, xg, yg = gme.get_field_xy('E', kind=0, mind=0, z=z_val,
                               component='xyz', Nx=60, Ny=60)
```

## MPB 밴드 계산
```python
import mpb

ms = mpb.ModeSolver(
    geometry=[...],
    geometry_lattice=mp.Lattice(size=mp.Vector3(1, 1)),
    k_points=mp.interpolate(4, [mp.Vector3(), mp.Vector3(0.5)]),
    resolution=32,
    num_bands=8,
)
ms.run_tm()  # or run_te()
```

## 자주 쓰는 유닛
- frequency: `f = c/λ` → `f_norm = a/λ` (a=격자 상수)
- 1550 nm → `f_norm = a/1.55` (a in μm)
- Courant factor: 기본 0.5, 불안정하면 줄이기

## 디버깅 팁
- `mp.verbosity(1)` → 상세 출력
- `sim.plot2D()` → 구조 시각화
- PML이 흡수 안 되면 → `dpml >= λ/2` 확인
- 수렴 안 되면 → resolution ×2 후 비교
