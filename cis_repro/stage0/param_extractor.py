"""
CIS Paper Parameter Extractor
==============================
논문 PDF / 이미지 / 텍스트 → params.json

흐름:
  1. PDF 텍스트 추출 (pdfplumber)
  2. Figure 이미지 추출 (PDF에서 크롭)
  3. LLM (Claude Vision / Gemini Vision)으로 파라미터 추출
  4. 암묵지 기반 검증 + 기본값 보완
  5. params.json 저장

사용법:
  python param_extractor.py --pdf paper.pdf --out results/NewPaper/params.json
  python param_extractor.py --pdf paper.pdf --notes "TiO2, 20x20, SP=0.8"
  python param_extractor.py --text "material: TiO2, n=2.3, SP=0.8um..."
"""

import argparse, json, os, re, sys, base64
from pathlib import Path
from typing import Optional
import anthropic  # Claude API

BASE = Path(__file__).parent.parent
TACIT = BASE / "CIS_TACIT_KNOWLEDGE.md"

# ─── CIS 파라미터 스키마 (추출 대상 전체) ─────────────────────────
PARAM_SCHEMA = {
    # 논문 메타
    "paper_id":      {"type": "str",   "required": True,  "example": "Pixel2022"},
    "paper_title":   {"type": "str",   "required": True,  "example": "Pixel-level Bayer-type..."},
    "doi":           {"type": "str",   "required": False, "default": ""},
    "journal":       {"type": "str",   "required": False, "default": ""},

    # 재료
    "material_name": {"type": "str",   "required": True,  "choices": ["TiO2","SiN","Nb2O5","HfO2","Si"]},
    "n_material":    {"type": "float", "required": True,  "range": [1.5, 4.5]},
    "n_SiO2":        {"type": "float", "required": False, "default": 1.45},

    # 구조 파라미터
    "SP_size":       {"type": "float", "required": True,  "unit": "um", "range": [0.3, 2.0]},
    "Layer_thickness":{"type":"float", "required": True,  "unit": "um", "range": [0.1, 2.0]},
    "FL_thickness":  {"type": "float", "required": True,  "unit": "um", "range": [0.3, 5.0]},
    "EL_thickness":  {"type": "float", "required": False, "default": 0.0, "unit": "um"},
    "n_layers":      {"type": "int",   "required": False, "default": 1},

    # 시뮬레이션 파라미터
    "resolution":    {"type": "int",   "required": True,  "range": [20, 150]},
    "focal_material":{"type": "str",   "required": True,  "choices": ["Air", "SiO2"]},
    "wavelengths":   {"type": "list",  "required": False, "default": [0.45, 0.55, 0.65]},

    # 설계 타입별
    "design_type":   {"type": "str",   "required": True,
                      "choices": ["discrete_pillar", "materialgrid", "sparse", "cylinder"]},
    "grid_n":        {"type": "int",   "required": False, "for": "discrete_pillar"},
    "tile_w":        {"type": "float", "required": False, "for": "discrete_pillar", "unit": "um"},
    "pillar_mask":   {"type": "list",  "required": False, "for": "discrete_pillar"},
    "weights_dir":   {"type": "str",   "required": False, "for": "materialgrid"},
    "sparse_pillars":{"type": "list",  "required": False, "for": "sparse"},
    "cylinders":     {"type": "list",  "required": False, "for": "cylinder"},

    # 논문 성능 수치 (검증용)
    "target_efficiency": {"type": "dict", "required": False,
                          "example": {"R": 0.70, "G": 0.60, "B": 0.65}},

    # 입력 모드
    "has_code":      {"type": "bool",  "required": False, "default": False},
    "has_structure": {"type": "bool",  "required": False, "default": False},
    "notes":         {"type": "str",   "required": False, "default": ""},
}

# ─── 암묵지 기반 기본값 ────────────────────────────────────────────
TACIT_DEFAULTS = {
    "n_SiO2":      1.45,
    "EL_thickness":0.0,
    "n_layers":    1,
    "wavelengths": [0.45, 0.55, 0.65],
    "has_code":    False,
    "has_structure": False,
}

# 재료별 일반 굴절률 (논문에서 명시 안 할 때)
MATERIAL_N_MAP = {
    "TiO2":  2.3,    # visible range
    "SiN":   2.02,   # standard PECVD SiN
    "Nb2O5": 2.32,   # ALD deposited
    "HfO2":  1.9,
    "Al2O3": 1.7,
    "SiO2":  1.45,
}


# ══════════════════════════════════════════════════════════════════
# PDF 텍스트 추출
# ══════════════════════════════════════════════════════════════════

def extract_pdf_text(pdf_path: str) -> str:
    """PDF에서 텍스트 추출 (pdfplumber 사용)"""
    try:
        import pdfplumber
        text = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text.append(t)
        return "\n".join(text)
    except ImportError:
        print("[WARN] pdfplumber 미설치. pip install pdfplumber")
        return ""
    except Exception as e:
        print(f"[WARN] PDF 텍스트 추출 실패: {e}")
        return ""


def extract_pdf_figures(pdf_path: str, out_dir: str, max_images: int = 5) -> list[str]:
    """PDF에서 이미지(figure) 추출 — 구조도 figure 대상"""
    try:
        import pdfplumber
        from PIL import Image
        import io
        paths = []
        with pdfplumber.open(pdf_path) as pdf:
            count = 0
            for i, page in enumerate(pdf.pages):
                for j, img in enumerate(page.images):
                    if count >= max_images:
                        break
                    # 이미지 크롭
                    bbox = (img["x0"], img["top"], img["x1"], img["bottom"])
                    try:
                        cropped = page.crop(bbox).to_image(resolution=150)
                        out_path = str(Path(out_dir) / f"fig_p{i+1}_{j+1}.png")
                        cropped.save(out_path)
                        paths.append(out_path)
                        count += 1
                    except Exception:
                        continue
        return paths
    except Exception as e:
        print(f"[WARN] Figure 추출 실패: {e}")
        return []


# ══════════════════════════════════════════════════════════════════
# LLM 파라미터 추출
# ══════════════════════════════════════════════════════════════════

EXTRACTION_PROMPT = """
당신은 MEEP FDTD 시뮬레이션 전문가입니다.
아래 CIS (Color Image Sensor) color router 논문 텍스트와 figure를 분석하여
MEEP 시뮬레이션에 필요한 파라미터를 JSON으로 추출하세요.

## 추출할 파라미터 (모두 μm 단위)

```json
{
  "paper_id": "저자연도 형식 예: Single2022",
  "paper_title": "논문 제목",
  "material_name": "TiO2 | SiN | Nb2O5 | HfO2",
  "n_material": 굴절률 (숫자),
  "SP_size": 서브픽셀 반크기 μm (픽셀크기/2),
  "Layer_thickness": 메타서피스 두께 μm,
  "FL_thickness": focal length μm (메타서피스→검출기 거리),
  "EL_thickness": 레이어간 스페이서 두께 μm (단층=0),
  "n_layers": 레이어 수 (1 또는 2),
  "resolution": MEEP 해상도 px/μm,
  "focal_material": "Air" 또는 "SiO2" (focal layer 재료),
  "design_type": "discrete_pillar" | "materialgrid" | "sparse" | "cylinder",
  "grid_n": N (NxN 격자, discrete_pillar일 때),
  "tile_w": 타일 크기 μm (discrete_pillar일 때),
  "target_efficiency": {"R": 0.xx, "G": 0.xx, "B": 0.xx},
  "has_code": false,
  "has_structure": true,
  "notes": "논문에서 중요한 설계 특이사항"
}
```

## CIS 시뮬레이션 암묵지 (파라미터 추출 시 참고)

{tacit_knowledge}

## 추출 규칙

1. **SP_size 주의**: 논문에서 "pixel size = 1.6μm"이면 SP_size = 0.8 (반크기)
2. **focal_material**: 논문 구조도나 SEM에서 focal layer 재료 확인
   - 빈 공간처럼 보이면 → Air
   - SiO2/glass로 채워진 것처럼 보이면 → SiO2
3. **resolution**: 논문 명시값 그대로. 없으면 구조 최소 feature 기준 계산:
   - resolution = max(40, int(10 / min_feature_um))
4. **n_material**: 논문 명시값. 없으면 재료별 표준값 사용:
   - TiO2 ≈ 2.3~2.65, SiN ≈ 1.9~2.1, Nb2O5 ≈ 2.32
5. **pillar_mask**: figure에서 읽을 수 있으면 NxN 이진 배열로 포함
   - 읽기 어려우면 null
6. **target_efficiency**: 논문 결과 그래프/표에서 RGB 효율 수치 추출
   - pixel-normalized 값 우선 (논문 주 그래프 기준)

반드시 유효한 JSON만 출력하세요. 추가 설명 없음.
"""

def extract_with_llm(
    text: str,
    figure_paths: list[str],
    notes: str = "",
    paper_id: str = "",
    model: str = "claude-sonnet-4-5",
) -> dict:
    """Claude Vision으로 파라미터 추출"""
    client = anthropic.Anthropic()

    # 암묵지 로드 (프롬프트 보강)
    tacit = ""
    if TACIT.exists():
        tacit_full = TACIT.read_text(encoding="utf-8")
        # 핵심 섹션만 (토큰 절약): 첫 200줄
        tacit = "\n".join(tacit_full.splitlines()[:200])

    prompt = EXTRACTION_PROMPT.format(tacit_knowledge=tacit)

    # 메시지 구성
    content = []

    # 텍스트 입력
    input_text = f"## 논문 텍스트\n{text[:8000]}"  # 토큰 제한
    if notes:
        input_text += f"\n\n## 추가 메모\n{notes}"
    if paper_id:
        input_text += f"\n\n## paper_id 힌트\n{paper_id}"
    content.append({"type": "text", "text": input_text})

    # Figure 이미지 추가 (최대 3개)
    for fig_path in figure_paths[:3]:
        try:
            with open(fig_path, "rb") as f:
                img_b64 = base64.standard_b64encode(f.read()).decode()
            ext = Path(fig_path).suffix.lower().lstrip(".")
            media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                          "png": "image/png", "gif": "image/gif"}.get(ext, "image/png")
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": img_b64}
            })
            content.append({"type": "text", "text": f"[Figure: {Path(fig_path).name}]"})
        except Exception as e:
            print(f"[WARN] 이미지 추가 실패 {fig_path}: {e}")

    # API 호출
    print(f"[LLM] Claude {model} 파라미터 추출 중...")
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=2048,
            system=prompt,
            messages=[{"role": "user", "content": content}]
        )
        raw = resp.content[0].text.strip()

        # JSON 추출
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            params = json.loads(json_match.group())
            return params
        else:
            print(f"[WARN] JSON 파싱 실패:\n{raw[:500]}")
            return {}
    except json.JSONDecodeError as e:
        print(f"[WARN] JSON 디코딩 실패: {e}\n{raw[:300]}")
        return {}
    except Exception as e:
        print(f"[ERROR] LLM 호출 실패: {e}")
        return {}


# ══════════════════════════════════════════════════════════════════
# 텍스트 기반 규칙 추출 (LLM 보완용)
# ══════════════════════════════════════════════════════════════════

def rule_based_extract(text: str) -> dict:
    """정규식 기반 파라미터 추출 (LLM 전처리/보완용)"""
    params = {}
    t = text.lower()

    # 재료 탐지 — 화학식 + 영문명 모두 탐지, 우선순위 순
    MAT_ALIASES = {
        "Nb2O5":  ["nb2o5", "niobium pentoxide", "niobium oxide"],
        "TiO2":   ["tio2", "titanium dioxide", "titania"],
        "HfO2":   ["hfo2", "hafnium oxide", "hafnia"],
        "Al2O3":  ["al2o3", "alumina", "aluminum oxide"],
        "SiN":    ["sin", "si3n4", "silicon nitride"],
        "SiO2":   ["sio2", "silica", "silicon dioxide"],
    }
    for mat, aliases in MAT_ALIASES.items():
        if any(alias in t for alias in aliases):
            params["material_name"] = mat
            params["n_material"] = MATERIAL_N_MAP.get(mat, 2.0)
            break

    # 굴절률 명시값 (소수점 포함, 문장 끝 점 제외)
    m = re.search(r'(?:refractive index|n\s*=|index of)\s*[≈~]?\s*([\d]+\.?[\d]*)', t)
    if m:
        val_str = m.group(1).rstrip('.')
        try:
            params["n_material"] = float(val_str)
        except ValueError:
            pass

    # SP_size 추출 — 여러 표현 방식 지원
    # "pixel size of 1.6 μm" → SP_size = 0.8
    m = re.search(r'pixel\s*(?:size|pitch|period)\s*(?:of\s*)?([\d.]+)\s*(?:μm|um|µm)', t)
    if m:
        params["SP_size"] = round(float(m.group(1)) / 2, 3)
    # "sub-pixel 0.6 um" 또는 "SP_size = 0.8"
    m2 = re.search(r'(?:sub.?pixel|sp[_\s]?size)\s*[=:]?\s*([\d.]+)\s*(?:μm|um|µm)?', t)
    if m2:
        params["SP_size"] = round(float(m2.group(1)), 3)
    # "half-pixel X um" 패턴
    m3 = re.search(r'half.?pixel\s*([\d.]+)\s*(?:μm|um|µm)', t)
    if m3:
        params["SP_size"] = round(float(m3.group(1)), 3)

    # 두께 추출 — nm/um 단위 변환
    # "thickness 300 nm" 또는 "600 nm thick"
    for pattern in [
        # "nanopillar height (thickness) is 300 nm"
        r'(?:pillar|nanopillar|nanostructure)\s*(?:thickness|height|depth)\s*(?:\([^)]*\)\s*)?is\s*([\d.]+)\s*(nm|um|μm|µm)',
        # "thickness is 600 nm" / "thickness of 300 nm"
        r'thickness\s+(?:of\s+|is\s+)([\d.]+)\s*(nm|um|μm|µm)',
        # "300 nm thick" / "300 nm height"
        r'([\d]+)\s*(nm|um|μm|µm)\s+(?:thick|height|tall|high)',
        # "layer thickness: 0.3 um"
        r'layer\s+thickness\s*[:=]\s*([\d.]+)\s*(nm|um|μm|µm)',
        # "heights: 510 nm" / "height: 600 nm"
        r'heights?\s*[=:]\s*([\d.]+)\s*(nm|um|μm|µm)',
        # "cylinder heights: 510 nm"
        r'cylinder\s+heights?\s*[=:]\s*([\d.]+)\s*(nm|um|μm|µm)',
    ]:
        m = re.search(pattern, t)
        if m:
            val = float(m.group(1))
            unit = m.group(2).strip().lower().replace('μm','um').replace('µm','um')
            params["Layer_thickness"] = round(val/1000 if unit == "nm" else val, 3)
            break

    # focal length 추출
    for pattern in [
        # "focal length between metasurface and photodetector is 2.0 um"
        r'between metasurface and\b.*?([\d.]+)\s*(um|μm|µm|nm)',
        # "focal length of 2.0 um" / "focal length is 2.0 um"
        r'focal\s+(?:length|distance|layer)\s+(?:of\s+|is\s+|:?\s*)([\d.]+)\s*(um|μm|µm|nm)',
        # "2.0 um focal"
        r'([\d.]+)\s*(um|μm|µm)\s+focal',
        # "focal: 1.08 um" / "focal layer: 1.08 um"
        r'focal\s+(?:layer\s*)?[=:]\s*([\d.]+)\s*(um|μm|µm|nm)',
        # "1.08 um" 독립 수치 (focal 관련 컨텍스트)
        r'(?:fl|focal|f)\s*[=:]\s*([\d.]+)\s*(um|μm|µm)',
    ]:
        m = re.search(pattern, t)
        if m:
            val = float(m.group(1))
            unit = m.group(2).strip().lower().replace('μm','um').replace('µm','um')
            params["FL_thickness"] = round(val/1000 if unit == "nm" else val, 3)
            break

    # resolution 추출
    for pattern in [
        # "50 pixels/um" / "50 px/um"
        r'(\d+)\s*(?:pixels?|px)\s*/\s*(?:um|μm|µm)',
        # "resolution of 50 pixels/um"
        r'resolution\s+(?:of\s+|is\s+)?(\d+)\s*(?:pixels?|px)',
        # "10 nm grid" → 1000/10 = 100 px/um
        r'(\d+)\s*nm\s*grid(?:\s*size)?',
    ]:
        m = re.search(pattern, t)
        if m:
            val = int(m.group(1))
            # nm 단위 grid size이면 역수
            if 'nm grid' in t[max(0, m.start()-5):m.end()+10]:
                params["resolution"] = int(1000/val)
            else:
                params["resolution"] = val if val >= 20 else int(1000/val)
            break

    # design_type 탐지
    if "genetic algorithm" in t or "ga optimization" in t:
        params["design_type"] = "cylinder"
    elif "material grid" in t or "inverse design" in t or "topology" in t:
        params["design_type"] = "materialgrid"
    elif "sparse" in t or "meta-atom" in t:
        params["design_type"] = "sparse"
    elif "pillar" in t or "binary" in t or "pixelated" in t:
        params["design_type"] = "discrete_pillar"

    # focal material
    if "air gap" in t or "air focal" in t:
        params["focal_material"] = "Air"
    elif "sio2" in t and "focal" in t:
        params["focal_material"] = "SiO2"

    # 레이어 수
    if "multilayer" in t or "two layer" in t or "double layer" in t:
        params["n_layers"] = 2
        params["design_type"] = "materialgrid"

    return params


# ══════════════════════════════════════════════════════════════════
# 검증 + 기본값 보완
# ══════════════════════════════════════════════════════════════════

def validate_and_fill(params: dict, paper_id: str = "") -> dict:
    """암묵지 기반 검증 및 누락 파라미터 기본값 보완"""
    issues = []

    # 기본값 적용
    for key, default in TACIT_DEFAULTS.items():
        if key not in params:
            params[key] = default

    if paper_id and "paper_id" not in params:
        params["paper_id"] = paper_id

    # 재료 기본 굴절률 보완
    if "material_name" in params and "n_material" not in params:
        params["n_material"] = MATERIAL_N_MAP.get(params["material_name"], 2.0)
        print(f"  [기본값] n_{params['material_name']} = {params['n_material']}")

    # resolution 범위 검증
    if "resolution" in params:
        if params["resolution"] < 20:
            issues.append(f"resolution={params['resolution']} < 20 → 40으로 상향")
            params["resolution"] = 40
        if params["resolution"] > 200:
            issues.append(f"resolution={params['resolution']} > 200 → 이상값")

    # SP_size와 FL_thickness 비율 체크
    if "SP_size" in params and "FL_thickness" in params:
        ratio = params["FL_thickness"] / params["SP_size"]
        if ratio < 0.5:
            issues.append(f"FL/SP={ratio:.1f} < 0.5 — 매우 짧은 초점 거리 (deep submicron?)")
        if ratio > 5.0:
            issues.append(f"FL/SP={ratio:.1f} > 5.0 — 매우 긴 초점 거리")

    # min_feature 체크
    if "tile_w" in params and "resolution" in params:
        min_grids = params["tile_w"] * params["resolution"]
        if min_grids < 4:
            issues.append(
                f"min_feature × resolution = {min_grids:.1f} < 4격자 "
                f"(tile_w={params['tile_w']}μm, res={params['resolution']})"
            )
        params["min_feature_um"] = params["tile_w"]

    # Bayer 파장 기본값
    if "wavelengths" not in params or not params["wavelengths"]:
        params["wavelengths"] = [0.45, 0.55, 0.65]

    # 이슈 출력
    if issues:
        print(f"\n[검증 이슈] {len(issues)}개:")
        for issue in issues:
            print(f"  ⚠ {issue}")

    return params


# ══════════════════════════════════════════════════════════════════
# 메인 파이프라인
# ══════════════════════════════════════════════════════════════════

def extract_params(
    pdf_path: Optional[str] = None,
    text: str = "",
    notes: str = "",
    paper_id: str = "",
    figure_paths: list[str] = [],
    use_llm: bool = True,
    out_path: Optional[str] = None,
) -> dict:
    """
    입력 소스에서 CIS 시뮬레이션 파라미터 추출 → params.json 저장

    Args:
        pdf_path: 논문 PDF 경로
        text: 논문 텍스트 (직접 제공 시)
        notes: 사용자 추가 메모
        paper_id: 논문 ID (예: "NewPaper2024")
        figure_paths: 이미지 파일 경로 목록
        use_llm: LLM 사용 여부
        out_path: 출력 JSON 경로
    """
    print(f"\n{'='*55}")
    print(f"Parameter Extractor — {paper_id or 'unknown'}")
    print(f"{'='*55}")

    # 텍스트 준비
    full_text = text
    figs = list(figure_paths)

    if pdf_path:
        print(f"\n[1] PDF 처리: {pdf_path}")
        pdf_text = extract_pdf_text(pdf_path)
        full_text = (full_text + "\n" + pdf_text).strip()
        print(f"    텍스트: {len(pdf_text)}자")

        # figure 추출
        if paper_id:
            fig_dir = str(Path(out_path).parent) if out_path else "/tmp"
            figs += extract_pdf_figures(pdf_path, fig_dir)
            print(f"    Figure: {len(figs)}개 추출")

    # 규칙 기반 추출 (빠른 초안)
    print("\n[2] 규칙 기반 추출...")
    rule_params = rule_based_extract(full_text)
    print(f"    추출된 파라미터: {list(rule_params.keys())}")

    # LLM 추출 (정확도 향상)
    llm_params = {}
    if use_llm and (full_text or figs):
        print("\n[3] LLM 추출 (Claude Vision)...")
        llm_params = extract_with_llm(full_text, figs, notes, paper_id)
        print(f"    추출된 파라미터: {list(llm_params.keys())}")

    # 병합 (LLM 우선, 규칙 보완)
    params = {**rule_params, **llm_params}
    if notes:
        params["notes"] = notes

    # 검증 + 기본값
    print("\n[4] 검증 및 기본값 보완...")
    params = validate_and_fill(params, paper_id)

    # 저장
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(params, f, indent=2, ensure_ascii=False)
        print(f"\n[완료] 저장: {out_path}")

    # 요약 출력
    print(f"\n{'─'*55}")
    print("추출 결과 요약:")
    key_params = ["material_name","n_material","SP_size","Layer_thickness",
                  "FL_thickness","resolution","design_type","n_layers","focal_material"]
    for k in key_params:
        v = params.get(k, "—")
        print(f"  {k:<20}: {v}")

    missing = [k for k, v in PARAM_SCHEMA.items()
               if v.get("required") and k not in params]
    if missing:
        print(f"\n  ⚠ 필수 파라미터 누락: {missing}")
    else:
        print(f"\n  ✓ 필수 파라미터 모두 추출됨")
    print(f"{'─'*55}")

    return params


# ══════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="CIS Paper Parameter Extractor")
    ap.add_argument("--pdf",   help="논문 PDF 경로")
    ap.add_argument("--text",  help="논문 텍스트 직접 제공", default="")
    ap.add_argument("--notes", help="추가 메모 (재료, 크기 등)", default="")
    ap.add_argument("--paper-id", help="논문 ID (예: NewPaper2024)", default="")
    ap.add_argument("--figures", nargs="*", help="Figure 이미지 경로들", default=[])
    ap.add_argument("--out",   help="출력 params.json 경로")
    ap.add_argument("--no-llm", action="store_true", help="LLM 없이 규칙만 사용")
    args = ap.parse_args()

    if not any([args.pdf, args.text, args.notes]):
        ap.print_help()
        sys.exit(1)

    out = args.out
    if not out and args.paper_id:
        out = str(BASE / "results" / args.paper_id / "params.json")

    extract_params(
        pdf_path=args.pdf,
        text=args.text,
        notes=args.notes,
        paper_id=args.paper_id,
        figure_paths=args.figures or [],
        use_llm=not args.no_llm,
        out_path=out,
    )
