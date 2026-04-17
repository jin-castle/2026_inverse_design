"""
원본 재현 코드의 geometry 구조 + 효율 계산 방식 정확히 추출
"""
import json, re
from pathlib import Path

NB_DIR = Path(r"C:\Users\user\.openclaw\workspace\dev\cis_reproduce")

papers = {
    "SMA2023":    "Pixelated Bayer spectral router based on a sparse meta-atom array_Chinese Optics Letters/SMA_Re.ipynb",
    "Simplest2023":"simplest-but-efficient-design-of-a-color-router-optimized-by-genetic-algorithms/Simplest_Re.ipynb",
    "RGBIR2025":  "pixel-level-spectral-routers-for-rgb-ir-sensing/RGB_IR_ACS2025_Re.ipynb",
}

for name, nb_rel in papers.items():
    nb_path = NB_DIR / nb_rel
    data = json.loads(nb_path.read_text(encoding="utf-8", errors="replace"))
    code = "\n".join("".join(c["source"]) for c in data["cells"] if c["cell_type"]=="code")
    
    print(f"\n{'='*65}")
    print(f"{name} — 원본 핵심 구조")
    print(f"{'='*65}")
    
    # 1. geometry 전체 (첫 번째 geometry = [...] 블록)
    geo = re.search(r"^geometry\s*=\s*\[(.*?)^\]", code, re.DOTALL | re.MULTILINE)
    if geo:
        print("[geometry 초기화 블록]")
        for line in geo.group(0).splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("mp.Block") or "material=" in stripped or "center=" in stripped or "size=" in stripped:
                if len(stripped) > 5:
                    print(f"  {stripped[:100]}")
    
    # 2. geometry.append() 호출들 (pillar 추가)
    appends = re.findall(r"geometry\.append\([^)]+\)", code, re.DOTALL)
    if appends:
        print(f"[geometry.append() {len(appends)}개]")
        for a in appends[:3]:
            print(f"  {' '.join(a.split())[:100]}")
    
    # 3. 효율 계산 핵심 라인
    print("[효율 계산]")
    eff_lines = re.findall(r"(?:Tr|Tg|Tb|Trt|Tgt|Tbt)\s*=.*", code)
    for l in eff_lines[:6]:
        print(f"  {l[:90]}")
    
    # 4. opt.sim_1 (참조 시뮬) geometry
    sim1_geo = re.search(r"opt\.sim_1\s*=\s*mp\.Simulation.*?geometry_1\s*=\s*\[(.*?)\]", code, re.DOTALL)
    or_geo1  = re.search(r"geometry_1\s*=\s*\[(.*?)\]", code, re.DOTALL)
    if or_geo1:
        print("[참조 시뮬 geometry_1]")
        geo1_content = or_geo1.group(1).strip()
        print(f"  {geo1_content[:200]}")
    
    # 5. tran_flux_p (pixel 모니터) 정의
    tran_p = re.search(r"tran_pixel\s*=.*", code)
    if not tran_p:
        tran_p = re.search(r"tran_p\s*=.*", code)
    if tran_p:
        print(f"[pixel monitor] {tran_p.group()[:90]}")
    
    # 6. flux 정규화 분모
    denom = re.findall(r"(?:tran_flux_p|total_flux)\[d\]", code)
    print(f"[정규화 분모] {set(denom)}")
