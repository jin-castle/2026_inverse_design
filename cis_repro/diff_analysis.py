"""
원본 재현 코드 vs 자동 생성 코드 정밀 비교 분석
모든 파라미터 차이와 오차 원인 분석
"""
import json, re
from pathlib import Path

NB_DIR   = Path(r"C:\Users\user\.openclaw\workspace\dev\cis_reproduce")
CISPRO   = Path(r"C:\Users\user\projects\meep-kb\cis_repro\results")

def nb_code(nb_path):
    data = json.loads(Path(nb_path).read_text(encoding="utf-8", errors="replace"))
    return "\n".join("".join(c["source"]) for c in data["cells"] if c["cell_type"]=="code")

def get(pattern, code, default="—"):
    m = re.search(pattern, code)
    return m.group(1) if m else default

# ══════════════════════════════════════════════════════════════
print("=" * 70)
print("SMA2023 — Sparse meta-atom: 원본 vs 자동생성 비교")
print("=" * 70)

orig = nb_code(NB_DIR / "Pixelated Bayer spectral router based on a sparse meta-atom array_Chinese Optics Letters" / "SMA_Re.ipynb")
gen_path = CISPRO / "SMA2023" / "reproduce_SMA2023.py"
gen = gen_path.read_text(encoding="utf-8", errors="replace") if gen_path.exists() else ""

params = [
    ("resolution",    r"resolution\s*=\s*(\d+)"),
    ("SP_size",       r"SP_size\s*=\s*([\d.]+)"),
    ("Layer_thick",   r"Layer_thickness\s*=\s*([\d.]+)"),
    ("FL_thickness",  r"FL_thickness\s*=\s*([\d.]+)"),
    ("focal_material",r"Focal Layer.*?material=(\w+)"),
    ("decay_by",      r"decay_by\s*=\s*(1e-\d+)"),
    ("stop_decay",    r"stop_when_dft_decayed\((1e-\d+)"),
    ("n_material",    r"SiN\s*=\s*mp\.Medium\(index=([\d.]+)\)"),
]

print(f"\n{'파라미터':<20} {'원본':>15} {'자동생성':>15} {'일치'}")
print("─" * 55)
for name, pat in params:
    ov = get(pat, orig)
    gv = get(pat, gen) if gen else "—"
    match = "✓" if ov == gv else "✗ DIFF"
    print(f"  {name:<18} {ov:>15} {gv:>15}  {match}")

# 원본 pillar 좌표
print("\n[원본 SMA pillar 좌표]")
w1 = get(r"w1\s*=\s*([\d.]+)", orig); w2 = get(r"w2\s*=\s*([\d.]+)", orig); w3 = get(r"w3\s*=\s*([\d.]+)", orig)
print(f"  w1(R)={w1}μm  w2(G)={w2}μm  w3(B)={w3}μm")
# 실제 Block 좌표
blocks_orig = re.findall(r"mp\.Block\([^)]+\)", orig, re.DOTALL)
for b in blocks_orig[:5]:
    center = re.search(r"center=mp\.Vector3\(([^)]+)\)", b)
    size   = re.search(r"size=mp\.Vector3\(([^)]+)\)", b)
    mat    = re.search(r"material=(\w+)\s*\)", b)
    if center:
        print(f"  center=({center.group(1)})  size=({size.group(1) if size else '?'})  mat={mat.group(1) if mat else '?'}")

print("\n[자동생성 SMA pillar 좌표]")
if gen:
    blocks_gen = re.findall(r"mp\.Block\([^)]+\)", gen, re.DOTALL)
    for b in blocks_gen[:5]:
        center = re.search(r"center=mp\.Vector3\(([^)]+)\)", b)
        size   = re.search(r"size=mp\.Vector3\(([^)]+)\)", b)
        mat    = re.search(r"material=(\w+)\s*\)", b)
        if center:
            print(f"  center=({center.group(1)})  size=({size.group(1) if size else '?'})  mat={mat.group(1) if mat else '?'}")

# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("Simplest2023 — Cylinder GA: 원본 vs 자동생성 비교")
print("=" * 70)

orig2 = nb_code(NB_DIR / "simplest-but-efficient-design-of-a-color-router-optimized-by-genetic-algorithms" / "Simplest_Re.ipynb")
gen2_path = CISPRO / "Simplest2023" / "reproduce_Simplest2023.py"
gen2 = gen2_path.read_text(encoding="utf-8", errors="replace") if gen2_path.exists() else ""

params2 = [
    ("resolution",    r"resolution\s*=\s*(\d+)"),
    ("SP_size",       r"SP_size\s*=\s*([\d.]+)"),
    ("Layer_thick",   r"Layer_thickness\s*=\s*([\d.]+)"),
    ("FL_thickness",  r"FL_thickness\s*=\s*([\d.]+)"),
    ("focal_material",r"Focal Layer.*?material=(\w+)"),
    ("decay_by",      r"decay_by\s*=\s*(1e-\d+)"),
    ("stop_decay",    r"stop_when_dft_decayed\((1e-\d+)"),
    ("D_R",           r"D_R\s*=\s*([\d.]+)"),
    ("D_G",           r"D_G\s*=\s*([\d.]+)"),
    ("D_B",           r"D_B\s*=\s*([\d.]+)"),
    ("Nb2O5_n",       r"Nb2O5\s*=\s*mp\.Medium\(index=([\d.]+)\)"),
]

print(f"\n{'파라미터':<20} {'원본':>15} {'자동생성':>15} {'일치'}")
print("─" * 55)
for name, pat in params2:
    ov = get(pat, orig2)
    gv = get(pat, gen2) if gen2 else "—"
    match = "✓" if ov == gv else "✗ DIFF"
    print(f"  {name:<18} {ov:>15} {gv:>15}  {match}")

# cylinder 위치
print("\n[원본 Simplest cylinder 좌표]")
xc_o = get(r"xc\s*=\s*\[([^\]]+)\]", orig2)
yc_o = get(r"yc\s*=\s*\[([^\]]+)\]", orig2)
print(f"  xc=[{xc_o}]  yc=[{yc_o}]")
pos_lines = re.findall(r"pos_[A-Za-z0-9]+\s*=\s*mp\.Vector3[^\n]+", orig2)
for p in pos_lines:
    print(f"  {p.strip()}")

print("\n[자동생성 Simplest cylinder 좌표]")
if gen2:
    cyls = re.findall(r"mp\.Cylinder[^)]+\)", gen2, re.DOTALL)
    for c in cyls[:6]:
        clean = " ".join(c.split())
        print(f"  {clean[:110]}")

# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("RGBIR2025 — RGB+IR 22×22: 원본 vs 자동생성 비교")
print("=" * 70)

orig3 = nb_code(NB_DIR / "pixel-level-spectral-routers-for-rgb-ir-sensing" / "RGB_IR_ACS2025_Re.ipynb")
gen3_path = CISPRO / "RGBIR2025" / "reproduce_RGBIR2025.py"
gen3 = gen3_path.read_text(encoding="utf-8", errors="replace") if gen3_path.exists() else ""

params3 = [
    ("resolution",    r"resolution\s*=\s*(\d+)"),
    ("SP_size",       r"SP_size\s*=\s*([\d.]+)"),
    ("Layer_thick",   r"Layer_thickness\s*=\s*([\d.]+)"),
    ("FL_thickness",  r"FL_thickness\s*=\s*([\d.]+)"),
    ("tile_w",        r"\bw\s*=\s*(0\.\d+)\s*#"),
    ("Nx",            r"Nx\s*=\s*(\d+)"),
    ("focal_material",r"Focal Layer.*?material=(\w+)"),
    ("stop_decay",    r"stop_when_dft_decayed\((1e-\d+)"),
    ("TiO2_n",        r"TiO2\s*=\s*mp\.Medium\(index=([\d.]+)\)"),
]

print(f"\n{'파라미터':<20} {'원본':>15} {'자동생성':>15} {'일치'}")
print("─" * 55)
for name, pat in params3:
    ov = get(pat, orig3)
    gv = get(pat, gen3) if gen3 else "—"
    match = "✓" if ov == gv else "✗ DIFF"
    print(f"  {name:<18} {ov:>15} {gv:>15}  {match}")

# pillar_mask 비교
print("\n[pillar_mask 비교]")
mask_orig = re.search(r"pillar_mask\s*=\s*(\[[\s\S]*?\])\n\n", orig3)
mask_gen  = re.search(r"pillar_mask\s*=\s*(\[[\s\S]*?\])\n", gen3) if gen3 else None

if mask_orig and mask_gen:
    mo = json.loads(mask_orig.group(1).replace("\n","").replace(" ",""))
    mg = json.loads(mask_gen.group(1).replace("\n","").replace(" ",""))
    total = sum(len(r) for r in mo)
    ones_o = sum(v for row in mo for v in row)
    ones_g = sum(v for row in mg for v in row)
    diff = sum(abs(mo[i][j]-mg[i][j]) for i in range(len(mo)) for j in range(len(mo[0])))
    print(f"  원본 fill: {ones_o}/{total} ({100*ones_o/total:.1f}%)")
    print(f"  생성 fill: {ones_g}/{total} ({100*ones_g/total:.1f}%)")
    print(f"  불일치 셀: {diff}개/{total}개 ({100*diff/total:.1f}%)")
elif mask_orig:
    print("  자동생성에 pillar_mask 없음")

# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("오차 원인 종합 분석")
print("=" * 70)

analysis = """
[논문별 오차 원인]

1. Single2022 → 오차 1.3% ✅
   - 원인: 재현 코드의 pillar_mask를 그대로 사용 (정확)
   - 결론: 정확한 mask = 정확한 재현

2. Pixel2022 → 오차 0.7% ✅
   - 원인: 재현 코드의 pillar_mask + resolution 변경(40→50)
   - 결론: res 차이는 효율에 미미한 영향

3. RGBIR2025 → 오차 76% ✗
   - 원인 1 (주요): pillar_mask 22×22를 논문 figure에서 손으로 읽음 → 불정확
   - 원인 2: stop_when_dft_decayed(1e-8) 조건이 우리 코드에 없음 → 수렴 기준 다름
   - 원인 3: focal_material SiO2를 생성 코드가 올바르게 사용했는지 확인 필요
   
4. SMA2023 → 오차 82% ✗
   - 원인 1 (주요): pillar 4개의 cx,cy 좌표
     원본: (-0.56, +0.56), (-0.56, -0.56), (+0.56, +0.56), (+0.56, -0.56)
     생성: (-0.56, +0.56), (-0.56, -0.56), (+0.56, +0.56), (+0.56, -0.56)
     → 좌표는 맞으나 재료 배치(R,G,G,B 어느 위치?)가 다를 수 있음
   - 원인 2: stop_when_dft_decayed(1e-8) 없음 → 너무 빨리 종료
   - 원인 3: SiO2 기판 geometry가 SMA에서 더 복잡할 수 있음

5. Simplest2023 → 오차 89% ✗
   - 원인 1 (주요): cylinder 좌표가 원본과 다름
     원본: pos_R=(-Sx/4, +Sy/4), pos_G1=(+Sx/4, +Sy/4) [Sx=2*SP=1.6μm]
     생성: cx=-0.4, cy=+0.4 (SP_size/2=0.4 맞지만 확인 필요)
   - 원인 2: SiO2 cover glass geometry 누락 여부
   - 원인 3: resolution=100 맞지만 stop_decay 조건 차이

[공통 원인 분류]
A. pillar_mask / geometry 정확도 (가장 큰 영향)
B. 수렴 조건 차이 (stop_when_dft_decayed 값)
C. geometry 세부 구조 (cover glass, substrate 처리)
D. focal_material 정확도 (Air vs SiO2)
"""
print(analysis)
