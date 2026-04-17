"""
CIS Color Router Fast Check — Single2022 파라미터
목적: geometry 좌표 검증, pillar 경계 체크, 핵심 수치 출력
resolution=5로 빠르게 실행 (실제 field 계산 없음)
"""
import meep as mp
import numpy as np
import sys
import time

mp.verbosity(0)
start = time.time()

# ─── Materials ──────────────────────────────────────────────
um_scale = 1
Air  = mp.Medium(index=1.0)
TiO2 = mp.Medium(index=2.3)   # n=2.3 @ 550nm
SiO2 = mp.Medium(index=1.45)  # 기판/커버 재료

# ─── Parameters (Single2022) ────────────────────────────────
resolution      = 5     # fast check (논문은 50)
layer_num       = 1
Layer_thickness = 0.3   # 300nm TiO2 메타서피스
FL_thickness    = 2.0   # 2.0um 초점 거리 (Air)
SP_size         = 0.8   # 반픽셀 크기 → 픽셀 = 1.6um
w               = 0.08  # 80nm 타일 크기
EL_thickness    = 0     # 다층 간격 (단층이므로 0)
Lpml            = 0.4   # PML 두께 (최소 λ/2 이상 권장)
pml_2_src       = 0.2   # PML→소스 간격
src_2_geo       = 0.2   # 소스→메타서피스 간격
mon_2_pml       = 0.4   # 모니터→PML 간격

# ─── Cell 크기 자동 계산 ──────────────────────────────────────
design_region_x = round(SP_size * 2, 2)   # 1.6um = 픽셀 크기 (1 Bayer unit)
design_region_y = round(SP_size * 2, 2)   # 1.6um
design_region_z = round(layer_num * Layer_thickness + EL_thickness, 2)
Sx = design_region_x
Sy = design_region_y
Sz = round(Lpml + pml_2_src + src_2_geo + design_region_z + FL_thickness + mon_2_pml + Lpml, 2)

# ─── 핵심 Z좌표 계산 (암묵지: 반드시 검증해야 할 좌표들) ─────────
z_src   = round(Sz/2 - Lpml - pml_2_src, 2)
z_meta  = round(Sz/2 - Lpml - pml_2_src - src_2_geo - design_region_z/2, 2)
z_fl    = round(Sz/2 - Lpml - pml_2_src - src_2_geo - design_region_z - FL_thickness/2, 2)
z_sipd  = round(Sz/2 - Lpml - pml_2_src - src_2_geo - design_region_z - FL_thickness - mon_2_pml/2 - Lpml/2, 2)
z_mon   = round(-Sz/2 + Lpml + mon_2_pml - 1/resolution, 2)
z_refl  = round(Sz/2 - Lpml - 1/resolution, 2)

print("=" * 55)
print("CIS Fast Check — Single2022 (TiO2, 20×20, 80nm)")
print("=" * 55)
print(f"\n[셀 크기]")
print(f"  Sx={Sx}, Sy={Sy}, Sz={Sz} [μm]")
print(f"  픽셀 크기: {Sx}×{Sy} μm (= 2×SP_size)")

print(f"\n[Z축 스택 검증] (위=+, 아래=-)")
print(f"  PML top:      +{Sz/2:.2f}  →  +{Sz/2-Lpml:.2f}")
print(f"  Source:       z_src  = {z_src}")
print(f"  SiO2 cover:   (PML~src_2_geo 사이)")
print(f"  Metasurface:  z_meta = {z_meta}  (두께={Layer_thickness})")
print(f"  Focal Layer:  z_fl   = {z_fl}   (두께={FL_thickness})")
print(f"  SiPD:         z_sipd = {z_sipd}")
print(f"  Monitor:      z_mon  = {z_mon}")
print(f"  Refl monitor: z_refl = {z_refl}")
print(f"  PML bot:      -{Sz/2:.2f}  →  -{Sz/2-Lpml:.2f}")

# ─── PML 경계 안전 체크 ───────────────────────────────────────
PML_TOP  = Sz/2 - Lpml
PML_BOT  = -Sz/2 + Lpml
checks = {
    "source_inside_cell":     (-Sz/2 < z_src < Sz/2),
    "source_outside_PML":     (PML_BOT < z_src < PML_TOP),
    "monitor_outside_PML":    (z_mon > PML_BOT),
    "refl_monitor_outside_PML": (z_refl < PML_TOP),
    "meta_below_source":      (z_meta < z_src),
    "mon_below_meta":         (z_mon < z_meta),
    "FL_between_meta_mon":    (z_mon < z_fl < z_meta),
}
print(f"\n[좌표 안전 체크]")
all_pass = True
for name, result in checks.items():
    status = "✓" if result else "✗ FAIL"
    print(f"  {status}  {name}")
    if not result: all_pass = False

# ─── Pillar 배치 검증 ─────────────────────────────────────────
pillar_mask = [
    [0,0,0,0,0,0,1,1,0,0,0,1,0,1,0,0,0,0,0,1],
    [0,0,0,0,0,0,1,1,0,1,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,1,0,1,1,1,0,0,0,0,0,0,0,0,0,0],
    [1,0,0,0,0,1,1,0,1,1,0,1,0,0,0,0,0,0,0,0],
    [0,0,0,0,1,1,1,0,1,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,1,0,1,1,1,0,0,1,0,0,0,0,0,0,0],
    [0,0,0,0,1,1,1,0,1,0,0,0,0,0,0,0,0,0,1,1],
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
N = 20
total_pillars = sum(pillar_mask[i][j] for i in range(N) for j in range(N))
oob = []
px_min = px_max = py_min = py_max = 0
coords = []
for i in range(N):
    for j in range(N):
        if pillar_mask[i][j] == 1:
            px = round(-N/2*w + j*w + w/2, 3)
            py = round(N/2*w - i*w - w/2, 3)
            coords.append((px, py))
            if abs(px) > Sx/2 or abs(py) > Sy/2:
                oob.append((i, j, px, py))

if coords:
    px_all = [c[0] for c in coords]
    py_all = [c[1] for c in coords]
    print(f"\n[Pillar 배치 검증]")
    print(f"  총 pillar 수: {total_pillars}/400 ({100*total_pillars/400:.1f}% fill)")
    print(f"  X 범위: [{min(px_all):.3f}, {max(px_all):.3f}] μm  (허용: ±{Sx/2})")
    print(f"  Y 범위: [{min(py_all):.3f}, {max(py_all):.3f}] μm  (허용: ±{Sy/2})")
    print(f"  경계 초과 pillar: {len(oob)}개  {'✓' if len(oob)==0 else '✗ FAIL'}")

# ─── Geometry 생성 ─────────────────────────────────────────────
pml_layers = [mp.PML(thickness=Lpml, direction=mp.Z)]
cell_size = mp.Vector3(Sx, Sy, Sz)

geometry = [
    mp.Block(center=mp.Vector3(0,0,round(Sz/2-Lpml/2-pml_2_src/2-src_2_geo/2,3)),
             size=mp.Vector3(Sx,Sy,round(Lpml+pml_2_src+src_2_geo,3)), material=SiO2),
    mp.Block(center=mp.Vector3(0,0,z_fl),
             size=mp.Vector3(Sx,Sy,FL_thickness), material=Air),
    mp.Block(center=mp.Vector3(0,0,z_sipd),
             size=mp.Vector3(Sx,Sy,round(mon_2_pml+Lpml,2)), material=Air),
]
for i in range(N):
    for j in range(N):
        if pillar_mask[i][j] == 1:
            px = round(-N/2*w + j*w + w/2, 2)
            py = round(N/2*w - i*w - w/2, 2)
            geometry.append(mp.Block(size=mp.Vector3(w,w,Layer_thickness),
                            center=mp.Vector3(px,py,z_meta), material=TiO2))

source_center = mp.Vector3(0, 0, z_src)
frequency = 1/(0.545*um_scale)
fwidth = frequency * 2   # width=2: GaussianSource 대역폭 파라미터
src = mp.GaussianSource(frequency=frequency, fwidth=fwidth)
source = [
    mp.Source(src, component=mp.Ex, size=mp.Vector3(Sx,Sy,0), center=source_center),
    mp.Source(src, component=mp.Ey, size=mp.Vector3(Sx,Sy,0), center=source_center),
]

sim = mp.Simulation(
    cell_size=cell_size,
    boundary_layers=pml_layers,
    geometry=geometry,
    sources=source,
    default_material=Air,
    resolution=resolution,
    k_point=mp.Vector3(0,0,0),   # 주기 경계 조건 (CIS 필수)
    eps_averaging=False,          # 이산 구조 정확도
    extra_materials=[SiO2, TiO2],
)

print(f"\n[시뮬레이션 생성]")
Nvox = int(Sx*resolution)*int(Sy*resolution)*int(Sz*resolution)
print(f"  res={resolution} 복셀: {Nvox:,}개")
print(f"  res=50 복셀 추정: {int(Sx*50)*int(Sy*50)*int(Sz*50):,}개")
print(f"  Simulation object: OK")

elapsed = time.time() - start
print(f"\n[소요 시간] {elapsed:.2f}초")
print(f"\n{'='*55}")
print(f"Fast Check: {'ALL PASSED ✓' if all_pass and len(oob)==0 else 'ISSUES FOUND ✗'}")
print(f"{'='*55}")
