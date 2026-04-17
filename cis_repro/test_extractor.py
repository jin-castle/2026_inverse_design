import sys
sys.path.insert(0, 'C:/Users/user/projects/meep-kb/cis_repro/stage0')
from param_extractor import rule_based_extract, validate_and_fill, PARAM_SCHEMA

# Single2022 텍스트 시뮬레이션
test_cases = [
    {
        "name": "Single2022 (TiO2 discrete pillar)",
        "text": """
            We design a single-layer Bayer-type color router using TiO2 nanopillars.
            The refractive index of TiO2 is n = 2.3 at visible wavelengths.
            The pixel size is 1.6 um (SP_size = 0.8 um half-pixel).
            Nanopillar height (thickness) is 300 nm.
            The focal length between metasurface and photodetector is 2.0 um.
            FDTD resolution is 50 pixels/um.
            The design consists of a 20x20 binary pillar array with 80 nm tile size.
            Target routing efficiency: R = 70%, G = 60%, B = 65%.
        """,
        "expected": {"material_name": "TiO2", "SP_size": 0.8, "Layer_thickness": 0.3,
                     "FL_thickness": 2.0, "resolution": 50, "design_type": "discrete_pillar"},
    },
    {
        "name": "Freeform (SiN MaterialGrid)",
        "text": """
            We present a freeform metasurface color router for deep submicron CIS pixels.
            Silicon nitride (SiN) with refractive index n = 1.92 is used.
            The pixel pitch is 1.2 um (sub-pixel 0.6 um).
            The SiN layer thickness is 600 nm.
            The focal length is 0.6 um (short focal distance for compact integration).
            Inverse design via topology optimization (MaterialGrid approach).
            FDTD resolution 50 pixels/um.
        """,
        "expected": {"material_name": "SiN", "SP_size": 0.6, "Layer_thickness": 0.6,
                     "FL_thickness": 0.6, "design_type": "materialgrid"},
    },
    {
        "name": "Simplest (Nb2O5 Cylinder GA)",
        "text": """
            A simple color router optimized by genetic algorithms using Nb2O5 cylinders.
            Refractive index n = 2.32.
            Four cylinders placed at Bayer pixel centers: pixel size 1.6 um.
            Cylinder heights: 510 nm.
            Focal layer: 1.08 um.
            GA-optimized diameters: R=470nm, Gr=370nm, Gb=370nm, B=210nm.
            Resolution 100 pixels/um for 10nm grid.
        """,
        "expected": {"material_name": "Nb2O5", "Layer_thickness": 0.51,
                     "FL_thickness": 1.08, "resolution": 100, "design_type": "cylinder"},
    },
]

print("=" * 60)
print("param_extractor 규칙 기반 추출 테스트")
print("=" * 60)

all_pass = True
for tc in test_cases:
    print(f"\n[케이스] {tc['name']}")
    params = rule_based_extract(tc["text"])
    params = validate_and_fill(params, tc["name"].split()[0])

    # 기대값 검사
    errors = []
    for k, v in tc["expected"].items():
        got = params.get(k)
        if got is None:
            errors.append(f"  누락: {k}")
        elif isinstance(v, str) and got != v:
            errors.append(f"  {k}: 기대={v}, 실제={got}")
        elif isinstance(v, float) and abs(got - v) > 0.05:
            errors.append(f"  {k}: 기대={v}, 실제={got}")

    if errors:
        print(f"  [PARTIAL] {len(tc['expected'])-len(errors)}/{len(tc['expected'])} 일치")
        for e in errors:
            print(e)
        all_pass = False
    else:
        print(f"  [PASS] {len(tc['expected'])}/{len(tc['expected'])} 일치")

    # 핵심 파라미터 출력
    for k in ["material_name","n_material","SP_size","Layer_thickness","FL_thickness",
              "resolution","design_type","focal_material"]:
        v = params.get(k, "—")
        print(f"    {k:<20}: {v}")

print(f"\n{'='*60}")
print(f"결과: {'전체 PASS' if all_pass else 'PARTIAL (LLM 없이 규칙만으로 한계 있음)'}")
print("LLM 추출은 --no-llm 제거 후 실제 PDF로 테스트 필요")
print(f"{'='*60}")
