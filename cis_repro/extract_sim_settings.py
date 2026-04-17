"""
모든 논문에서 시뮬레이션 핵심 설정 추출 + 재현 코드와 비교
"""
import pdfplumber, json, re
from pathlib import Path

NB_DIR = Path(r"C:\Users\user\.openclaw\workspace\dev\cis_reproduce")

PAPERS = {
    "Single2022": "single-layer-bayer-metasurface-via-inverse-design/single-layer-bayer-metasurface-via-inverse-design.pdf",
    "Pixel2022":  "Pixel-level Bayer-type colour router based on metasurfaces/Pixel level Bayer type colour router based on metasurfaces.pdf",
    "Freeform":   "Freeform metasurface color router for deep submicron pixel image sensors/Freeform metasurface color router for deep submicron pixel image sensors.pdf",
    "Multilayer": "Multilayer topological metasurface-based color routers/Multilayer topological metasurface-based color routers.pdf",
    "SMA":        "Pixelated Bayer spectral router based on a sparse meta-atom array_Chinese Optics Letters/Pixelated+Bayer+spectral+router+based+on+a+sparse+meta-atom+array_Chinese+Optics+Letters.pdf",
    "Simplest":   "simplest-but-efficient-design-of-a-color-router-optimized-by-genetic-algorithms/Simplest but Efficient Design of a Color Router Optimized by Genetic Algorithms.pdf",
    "RGBIR":      "pixel-level-spectral-routers-for-rgb-ir-sensing/pixel-level-spectral-routers-for-rgb-ir-sensing.pdf",
}

def extract_text(pdf_path, max_pages=8):
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            return " ".join(p.extract_text() or "" for p in pdf.pages[:max_pages])
    except:
        return ""

def find(pattern, text, default="—"):
    m = re.search(pattern, text, re.I | re.DOTALL)
    return m.group(1).strip() if m else default

def find_all(pattern, text):
    return re.findall(pattern, text, re.I)

print("=" * 80)
print("논문별 시뮬레이션 설정 완전 추출")
print("=" * 80)

for name, pdf_rel in PAPERS.items():
    pdf_path = NB_DIR / pdf_rel
    if not pdf_path.exists():
        print(f"\n[{name}] PDF 없음")
        continue

    text = extract_text(pdf_path)
    t = text.lower()

    print(f"\n{'─'*80}")
    print(f"📄 [{name}]")
    print(f"{'─'*80}")

    # 1. 소자 구조 파라미터
    print("\n[1] 소자 구조]")

    # pixel/supercell 크기
    px = find_all(r'(?:pixel|supercell|unit.?cell)\s*(?:size|pitch|period).*?(\d+\.?\d*)\s*[μµu]m', text)
    px2 = find_all(r'(\d+\.?\d*)\s*[μµu]m.*?(?:pixel|supercell)', text)
    print(f"  픽셀/수퍼셀 크기: {list(set(px+px2))[:4]}")

    # pillar 높이/두께
    h = find_all(r'(?:height|thickness|h\s*[=:])\s*(?:is\s*|of\s*|=\s*)?(\d+)\s*nm', text)
    h2 = find_all(r'(\d+)\s*nm.*?(?:height|thick|tall)', text)
    print(f"  Pillar 높이: {list(set(h+h2))[:5]}nm")

    # 재료 굴절률
    n_vals = find_all(r'(?:n\s*[=≈~]|index\s*(?:of\s*)?(?:refraction\s*)?(?:is\s*)?[=:])\s*(\d+\.?\d+)', text)
    mats = find_all(r'(tio2|sin|si3n4|nb2o5|sio2|quartz|hafnium|alumina|al2o3).*?n\s*[=≈~]\s*(\d+\.?\d+)', t)
    print(f"  굴절률 값: {n_vals[:6]}")
    print(f"  재료별:    {mats[:4]}")

    # Focal length
    fl = find_all(r'(?:focal|f\.?l\.?|working distance).*?(\d+\.?\d*)\s*[μµu]m', text)
    print(f"  Focal length: {fl[:3]}μm")

    # 2. 광원 및 경계 조건
    print("\n[2] 광원 & 경계 조건]")

    # 입사 방식
    if "normal incidence" in t or "normally incident" in t:
        inc = "정상 입사 (normal incidence)"
    elif "oblique" in t:
        inc = "경사 입사 포함"
    else:
        inc = "—"
    print(f"  입사 방식: {inc}")

    # 편광
    if "unpolarized" in t or "un-polarized" in t:
        pol = "비편광 (unpolarized)"
    elif "both polarization" in t or "both ex and ey" in t:
        pol = "Ex+Ey 동시"
    elif "te" in t[:2000] and "tm" in t[:2000]:
        pol = "TE+TM 모두"
    else:
        pol = "—"
    print(f"  편광: {pol}")

    # 광원 종류
    if "plane wave" in t:
        src = "평면파 (plane wave)"
    elif "gaussian" in t:
        src = "Gaussian source"
    else:
        src = "—"
    print(f"  광원 종류: {src}")

    # 주기 경계
    if "periodic" in t:
        pbc = "주기 경계 조건 (periodic BC)"
    else:
        pbc = "—"
    print(f"  경계 조건: {pbc}")

    # PML
    if "pml" in t or "perfectly matched" in t:
        pml = "PML 사용"
    else:
        pml = "—"
    print(f"  흡수층: {pml}")

    # 3. 효율 정의
    print("\n[3] 효율 정의]")

    # 정규화 방식
    if "total incident" in t or "incident power" in t:
        norm = "total incident flux 기준"
    elif "pixel area" in t or "tran_flux_p" in t:
        norm = "pixel area flux 기준"
    else:
        norm = "—"

    # 수치 정의 텍스트
    eff_def = find(r'(?:spectral routing efficiency|collection efficiency|routing efficiency)\s+(?:is\s+)?(?:defined\s+as\s+)?([^.]+\.)', text)
    print(f"  정규화: {norm}")
    print(f"  효율 정의: {eff_def[:120] if eff_def != '—' else '—'}")

    # 논문 보고 수치
    eff_nums = find_all(r'(\d+\.?\d*)\s*%.*?(?:R|G|B|red|green|blue)', text)
    print(f"  보고 효율 수치: {list(set(eff_nums))[:8]}%")

    # 4. FDTD 설정
    print("\n[4] FDTD 설정]")

    # resolution/grid
    res_vals = find_all(r'(?:grid\s*size|mesh\s*size|resolution)\s*(?:of\s*)?(\d+)\s*(?:nm|px|pixel)', text)
    res_vals2 = find_all(r'(\d+)\s*nm.*?(?:grid|mesh|resolution)', text)
    print(f"  격자 크기: {list(set(res_vals+res_vals2))[:4]}nm")

    # 수렴 기준
    decay = find_all(r'(?:convergence|decay|criterion).*?1e[-−]?(\d)', text)
    print(f"  수렴 기준: {decay[:3]}")

    # 5. 기판/환경
    print("\n[5] 기판 & 환경]")

    sub = find(r'(?:substrate|deposited on|grown on)\s+([^,.]+)', text)
    cov = find(r'(?:cover|cladding|superstrate)\s+(?:glass|layer|material)?\s*(?:is\s*|of\s*)?([^,.]+)', text)
    air_gap = "air gap" in t or "air focal" in t
    print(f"  기판: {sub}")
    print(f"  커버: {cov}")
    print(f"  Air gap: {'있음' if air_gap else '—'}")

print("\n" + "=" * 80)
