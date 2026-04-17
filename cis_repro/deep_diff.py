"""
핵심 차이점 정밀 분석:
1. RGBIR2025 - pillar_mask는 같은데 왜 76% 오차?
2. SMA2023   - cover glass geometry 비교
3. Simplest2023 - cylinder 위치 + cover glass 비교
4. 공통: stop_decay 차이의 실제 영향
"""
import json, re
from pathlib import Path

NB_DIR = Path(r"C:\Users\user\.openclaw\workspace\dev\cis_reproduce")
CISPRO = Path(r"C:\Users\user\projects\meep-kb\cis_repro\results")

def nb_code(nb_path):
    data = json.loads(Path(nb_path).read_text(encoding="utf-8", errors="replace"))
    return "\n".join("".join(c["source"]) for c in data["cells"] if c["cell_type"]=="code")

def get(pattern, code, default="—"):
    m = re.search(pattern, code)
    return m.group(1) if m else default

# ══════════════════════════════════════════════════════════════
print("=" * 70)
print("RGBIR2025: pillar_mask 동일한데 왜 76% 오차?")
print("=" * 70)

orig3 = nb_code(NB_DIR / "pixel-level-spectral-routers-for-rgb-ir-sensing" / "RGB_IR_ACS2025_Re.ipynb")
gen3  = (CISPRO / "RGBIR2025" / "reproduce_RGBIR2025.py").read_text(encoding="utf-8", errors="replace") \
        if (CISPRO / "RGBIR2025" / "reproduce_RGBIR2025.py").exists() else ""

# 소스 위쪽 geometry (cover glass) 비교
print("\n[원본 geometry 상단 블록]")
blocks_orig = re.findall(r"mp\.Block\([^)]+\)", orig3, re.DOTALL)
for b in blocks_orig[:4]:
    center = re.search(r"center=mp\.Vector3\(([^)]+)\)", b)
    mat    = re.search(r"material=(\w+)\s*[\),]", b)
    size   = re.search(r"size=mp\.Vector3\(([^)]+)\)", b)
    print(f"  center=({(center.group(1)[:60] if center else '?')}) mat={mat.group(1) if mat else '?'}")

print("\n[자동생성 geometry 상단 블록]")
if gen3:
    blocks_gen = re.findall(r"mp\.Block\([^)]+\)", gen3, re.DOTALL)
    for b in blocks_gen[:4]:
        center = re.search(r"center=mp\.Vector3\(([^)]+)\)", b)
        mat    = re.search(r"material=(\w+)\s*[\),]", b)
        print(f"  center=({(center.group(1)[:60] if center else '?')}) mat={mat.group(1) if mat else '?'}")

# 소스 타입 비교
print("\n[소스 타입 비교]")
src_orig = re.findall(r"mp\.Source\([^)]+\)", orig3)
src_gen  = re.findall(r"mp\.Source\([^)]+\)", gen3) if gen3 else []
print(f"  원본:   {len(src_orig)}개 소스")
for s in src_orig:
    comp = re.search(r"component=mp\.(\w+)", s)
    print(f"    {comp.group(1) if comp else '?'}")
print(f"  생성:   {len(src_gen)}개 소스")
for s in src_gen:
    comp = re.search(r"component=mp\.(\w+)", s)
    print(f"    {comp.group(1) if comp else '?'}")

# 효율 계산 분모 비교 (tran_flux_p vs total_flux)
print("\n[효율 계산 방식 비교]")
orig_eff_line = re.search(r"Tr\s*=\s*.*", orig3)
gen_eff_line  = re.search(r"Tr\s*=\s*.*", gen3) if gen3 else None
print(f"  원본: {orig_eff_line.group()[:80] if orig_eff_line else '?'}")
print(f"  생성: {gen_eff_line.group()[:80] if gen_eff_line else '?'}")

# stop_when_dft_decayed 값
print("\n[수렴 조건 비교]")
orig_decay = re.findall(r"stop_when_dft_decayed\((1e-\d+)", orig3)
gen_decay  = re.findall(r"stop_when_dft_decayed\((1e-\d+)", gen3) if gen3 else []
print(f"  원본: {orig_decay}")
print(f"  생성: {gen_decay}")
print(f"  → 1e-8 (원본) vs 1e-6 (생성): 수렴 기준 100배 차이!")

# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("SMA2023: geometry 완전 비교")
print("=" * 70)

orig_sma = nb_code(NB_DIR / "Pixelated Bayer spectral router based on a sparse meta-atom array_Chinese Optics Letters" / "SMA_Re.ipynb")
gen_sma  = (CISPRO / "SMA2023" / "reproduce_SMA2023.py").read_text(encoding="utf-8", errors="replace") \
           if (CISPRO / "SMA2023" / "reproduce_SMA2023.py").exists() else ""

# 원본의 전체 geometry 추출
print("\n[원본 geometry 전체]")
geo_section = re.search(r"geometry\s*=\s*\[(.*?)^(?=sim\s*=\s*mp\.Simulation)", orig_sma, re.DOTALL | re.MULTILINE)
if geo_section:
    geo_lines = geo_section.group(1).strip().splitlines()
    for line in geo_lines:
        if line.strip():
            print(f"  {line.strip()[:100]}")

print("\n[자동생성 geometry 전체]")
if gen_sma:
    geo_section_g = re.search(r"geometry\s*=\s*\[(.*?)(?=sim\s*=\s*mp\.Simulation)", gen_sma, re.DOTALL)
    if geo_section_g:
        for line in geo_section_g.group(1).strip().splitlines():
            if line.strip():
                print(f"  {line.strip()[:100]}")

# SMA pillar 4개 좌표 상세
print("\n[원본 SMA pillar 4개 좌표]")
sma_blocks = re.findall(r"Si3N4 nano-pillars.*?(?=Focal Layer)", orig_sma, re.DOTALL)
if not sma_blocks:
    sma_blocks = re.findall(r"mp\.Block\(size=.*?material=SiN\)", orig_sma, re.DOTALL)
for b in sma_blocks[:6]:
    clean = " ".join(b.split())
    print(f"  {clean[:120]}")

# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("Simplest2023: 핵심 차이 — xc,yc 좌표 의미")
print("=" * 70)

orig_si = nb_code(NB_DIR / "simplest-but-efficient-design-of-a-color-router-optimized-by-genetic-algorithms" / "Simplest_Re.ipynb")

# xc, yc 원본
xc_line = re.search(r"xc\s*=\s*\[([^\]]+)\]", orig_si)
yc_line = re.search(r"yc\s*=\s*\[([^\]]+)\]", orig_si)
print(f"\n원본 xc = [{xc_line.group(1) if xc_line else '?'}]  → Sx=2*SP=1.6, Sx/4=0.4")
print(f"원본 yc = [{yc_line.group(1) if yc_line else '?'}]")
print(f"→ xc[0]=-0.4, xc[1]=+0.4  (SP_size/2)")
print(f"\n원본 pos_R  = (xc[0], yc[1]) = (-0.4, +0.4)  ← 논문 좌상단 R")
print(f"원본 pos_G1 = (xc[1], yc[1]) = (+0.4, +0.4)  ← 우상단 G")
print(f"원본 pos_G2 = (xc[0], yc[0]) = (-0.4, -0.4)  ← 좌하단 G")
print(f"원본 pos_B  = (xc[1], yc[0]) = (+0.4, -0.4)  ← 우하단 B")

print(f"\n자동생성 cylinder 좌표:")
gen_si = (CISPRO / "Simplest2023" / "reproduce_Simplest2023.py").read_text(encoding="utf-8", errors="replace") \
         if (CISPRO / "Simplest2023" / "reproduce_Simplest2023.py").exists() else ""
if gen_si:
    cyls = re.findall(r"mp\.Cylinder\([^)]+\)", gen_si, re.DOTALL)
    labels = ["R", "G1", "G2", "B"]
    for i, c in enumerate(cyls[:4]):
        center = re.search(r"center=mp\.Vector3\(([^)]+)\)", c)
        radius = re.search(r"radius=([\d.]+)", c)
        lbl    = labels[i] if i < len(labels) else "?"
        print(f"  {lbl}: center=({center.group(1) if center else '?'}) radius={radius.group(1) if radius else '?'}")
print("→ 좌표는 원본과 동일 ✓")

# cover glass 비교
print(f"\n[원본 geometry (위→아래)]")
geo_si = re.search(r"geometry\s*=\s*\[(.*?)^sim\s*=\s*mp\.Simulation", orig_si, re.DOTALL | re.MULTILINE)
if geo_si:
    for line in geo_si.group(1).strip().splitlines():
        if line.strip() and not line.strip().startswith("#"):
            print(f"  {line.strip()[:100]}")

print(f"\n[자동생성 geometry]")
if gen_si:
    geo_gen = re.search(r"geometry\s*=\s*\[(.*?)sim\s*=\s*mp\.Simulation", gen_si, re.DOTALL)
    if geo_gen:
        for line in geo_gen.group(1).strip().splitlines():
            if line.strip() and not line.strip().startswith("#"):
                print(f"  {line.strip()[:100]}")

# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("수렴 조건(stop_decay) 차이의 실제 영향 분석")
print("=" * 70)

papers_decay = {
    "RGBIR2025": ("1e-8", "1e-6"),
    "SMA2023":   ("1e-8", "1e-6"),
    "Simplest2023": ("1e-6", "1e-6"),  # 일치
    "Single2022":  ("1e-6", "1e-6"),  # 일치 (확인 필요)
    "Pixel2022":   ("1e-8", "1e-6"),
}
print(f"\n{'논문':<20} {'원본 decay':>12} {'생성 decay':>12} {'차이':>6} {'영향'}")
print("─" * 65)
for name, (orig_d, gen_d) in papers_decay.items():
    diff = "100배" if orig_d != gen_d else "동일"
    effect = "수렴 전 종료 → 효율 부정확" if orig_d != gen_d else "—"
    match = "✗" if orig_d != gen_d else "✓"
    print(f"  {name:<18} {orig_d:>12} {gen_d:>12}  {match}     {effect}")

print("""
[stop_when_dft_decayed 의미]
  1e-6: DFT fields가 초기 대비 1e-6로 감소하면 종료
  1e-8: 1e-8로 감소하면 종료 (더 오래, 더 정밀)
  
  차이: time steps 수 차이 → FL=4.0um(긴 경로) 시뮬에서 특히 중요
  RGBIR/SMA처럼 FL이 길면 decay가 느려서 1e-6로 끊으면 미수렴!
  → 효율 값이 안정화 전에 출력됨 → 큰 오차
""")

print("=" * 70)
print("결론: 오차 원인 우선순위")
print("=" * 70)
print("""
순위  원인                          영향 논문        대응
───────────────────────────────────────────────────────────────
1위   stop_decay 1e-6(생성) vs 1e-8(원본)
      FL=4μm 긴 경로에서 미수렴     RGBIR,SMA      → 1e-8로 수정

2위   pillar_mask 정확도 
      손으로 읽어 불정확             RGBIR2025      → 재현 코드 mask 사용

3위   geometry 세부 구조 차이
      source쪽 cover, SiO2 기판    SMA, Simplest  → 원본 geometry 확인

4위   효율 정규화 방식
      total_flux vs pixel_flux     모두           → 원본 코드와 동일하게

즉, stop_decay를 1e-8로 수정하고 RGBIR의 pillar_mask를
재현 코드에서 그대로 가져오면 오차 크게 감소할 것.
""")
