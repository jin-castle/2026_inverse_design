"""
meep-kb 회귀 테스트 실행기
Usage: python tests/run_regression.py [--verbose]
"""
import requests, json, sys, time
from pathlib import Path

KB_URL = "http://localhost:8765"
VERBOSE = "--verbose" in sys.argv

CASES = [
    # ── Metagrating (C1-C7 기반) ──────────────────────────────────────
    {
        "id": "C1_circular_import",
        "query": "ImportError: circular import code.py pdb",
        "expected_keywords": ["circular", "code.py", "pdb", "import"],
        "must_not_contain": ["PML", "DiffractedPlanewave"],
        "category": "setup",
    },
    {
        "id": "C2_PML_center_kwarg",
        "query": "TypeError: PML() got unexpected keyword argument center",
        "expected_keywords": ["PML", "center", "thickness"],
        "must_not_contain": ["DiffractedPlanewave", "adjoint"],
        "category": "setup",
    },
    {
        "id": "C3_ContinuousSource_timeout",
        "query": "ContinuousSource simulation not terminating timeout",
        "expected_keywords": ["ContinuousSource", "GaussianSource", "timeout"],
        "must_not_contain": ["PML", "gradient"],
        "category": "setup",
    },
    {
        "id": "C4_DiffractedPlanewave_kwarg",
        "query": "DiffractedPlanewave unexpected keyword argument orders grating_vec",
        "expected_keywords": ["DiffractedPlanewave", "positional", "orders"],
        "must_not_contain": ["PML", "ContinuousSource"],
        "category": "dft",
    },
    {
        "id": "C5_load_minus_flux",
        "query": "T+R greater than 2.0 energy conservation violation reflection normalization",
        "expected_keywords": ["load_minus_flux_data", "normalization", "T+R"],
        "must_not_contain": ["ContinuousSource", "gradient"],
        "category": "dft",
    },
    {
        "id": "C6_eigenmode_band_index",
        "query": "eig_band=0 eigenmode zero band index MEEP 1-based",
        "expected_keywords": ["eig_band", "band", "index"],
        "must_not_contain": ["PML", "ContinuousSource"],
        "category": "dft",
    },
    {
        "id": "C7_3D_detection",
        "query": "2D simulation for 3D device wrong dimensionality CSV shape Nx Ny",
        "expected_keywords": ["3D", "dimension", "CSV"],
        "must_not_contain": ["PML", "ContinuousSource"],
        "category": "setup",
    },
    # ── Metalens (오늘 발견) ─────────────────────────────────────────
    {
        "id": "ML1_cylindrical_m0",
        "query": "zone plate cylindrical MEEP m=0 no focusing wrong polarization",
        "expected_keywords": ["m=-1", "cylindrical", "linear"],
        "must_not_contain": ["PML center", "T+R"],
        "category": "setup",
    },
    {
        "id": "ML2_U_SUM_invalid",
        "query": "MaterialGrid grid_type U_SUM ValueError invalid MEEP 1.31",
        "expected_keywords": ["U_DEFAULT", "MaterialGrid", "grid_type"],
        "must_not_contain": ["PML", "ContinuousSource"],
        "category": "adjoint",
    },
    {
        "id": "ML3_Source_keyword",
        "query": "mp.Source positional args AttributeError Vector3 has no attribute center",
        "expected_keywords": ["keyword", "center", "size", "component"],
        "must_not_contain": ["PML", "DiffractedPlanewave"],
        "category": "setup",
    },
    {
        "id": "ML4_near2far_top_only",
        "query": "zone plate near2far PSF asymmetric low intensity top surface only",
        "expected_keywords": ["Near2FarRegion", "side", "top"],
        "must_not_contain": ["PML center", "gradient"],
        "category": "dft",
    },
    {
        "id": "ML5_beta_zero_eval",
        "query": "adjoint metalens final efficiency 0.0 all zeros after optimization binarized",
        "expected_keywords": ["beta", "binarize", "evaluation"],
        "must_not_contain": ["PML", "ContinuousSource"],
        "category": "optimizer",
    },
    {
        "id": "ML6_FOM_normalization",
        "query": "adjoint metalens FOM 4-6 but paper says 0.45 inconsistent normalization reference",
        "expected_keywords": ["normalization", "reference", "substrate"],
        "must_not_contain": ["PML", "geometry"],
        "category": "adjoint",
    },
    {
        "id": "ML7_N2F_unit_cell",
        "query": "1D metalens unit cell near2far grating diffraction pattern not focal spot",
        "expected_keywords": ["aperture", "num_cells", "cell_size"],
        "must_not_contain": ["PML center", "gradient"],
        "category": "dft",
    },
    {
        "id": "ML8_cylindrical_Ez",
        "query": "cylindrical MEEP mp.Ez source wrong field pattern no focusing zone plate",
        "expected_keywords": ["mp.Er", "mp.Ep", "amplitude", "linear"],
        "must_not_contain": ["T+R", "adjoint"],
        "category": "setup",
    },
    # ── Adjoint / Optimizer ─────────────────────────────────────────
    {
        "id": "ADJ1_gradient_2x",
        "query": "adjoint gradient finite difference ratio 2.0 chain rule factor",
        "expected_keywords": ["chain rule", "gradient", "|grad/fd|"],
        "must_not_contain": ["PML", "ContinuousSource"],
        "category": "adjoint",
    },
    {
        "id": "ADJ2_FOM_plateau",
        "query": "topology optimization FOM plateau not improving after many iterations",
        "expected_keywords": ["beta", "schedule", "learning rate"],
        "must_not_contain": ["PML", "ContinuousSource"],
        "category": "optimizer",
    },
    {
        "id": "ADJ3_checkerboard",
        "query": "binary design shows checkerboard pattern after high beta binarization",
        "expected_keywords": ["conic_filter", "radius", "minimum_length"],
        "must_not_contain": ["PML", "source"],
        "category": "fabrication",
    },
    {
        "id": "NUM1_NaN_adjoint",
        "query": "NaN values in adjoint gradient simulation blow up instability",
        "expected_keywords": ["NaN", "instability", "gradient"],
        "must_not_contain": ["PML center", "ContinuousSource"],
        "category": "numerical",
    },
    {
        "id": "MPI1_slot_error",
        "query": "mpirun slots error previous process not terminated pkill",
        "expected_keywords": ["pkill", "mpirun", "slots"],
        "must_not_contain": ["adjoint", "gradient"],
        "category": "performance",
    },
]


def run_test(case: dict) -> dict:
    """단일 테스트 케이스 실행"""
    query = case["query"]
    try:
        r = requests.post(f"{KB_URL}/api/diagnose",
                          json={"error": query, "n": 3},
                          timeout=15)
        data = r.json()
        suggestions = data.get("suggestions", [])
        
        # 검색된 텍스트 수집
        retrieved_text = " ".join([
            s.get("title", "") + " " +
            str(s.get("solution", "")) + " " +
            str(s.get("cause", ""))
            for s in suggestions
        ]).lower()
        
        # 기대 키워드 매칭 체크
        found_keywords = []
        missing_keywords = []
        for kw in case["expected_keywords"]:
            if kw.lower() in retrieved_text:
                found_keywords.append(kw)
            else:
                missing_keywords.append(kw)
        
        # 금지 키워드 체크 (오검출 방지)
        false_positives = [kw for kw in case.get("must_not_contain", [])
                           if kw.lower() in retrieved_text[:200]]
        
        # 점수 계산
        if not case["expected_keywords"]:
            keyword_score = 0.0
        else:
            keyword_score = len(found_keywords) / len(case["expected_keywords"])
        
        fp_penalty = len(false_positives) * 0.2
        score = max(0, keyword_score - fp_penalty)
        
        passed = score >= 0.5 and not false_positives
        
        return {
            "id": case["id"],
            "passed": passed,
            "score": round(score, 2),
            "found_keywords": found_keywords,
            "missing_keywords": missing_keywords,
            "false_positives": false_positives,
            "top_result": suggestions[0].get("title", "N/A") if suggestions else "NO RESULT",
            "n_results": len(suggestions),
        }
    except Exception as e:
        return {
            "id": case["id"],
            "passed": False,
            "score": 0.0,
            "error": str(e),
            "top_result": "ERROR",
        }


def main():
    print("=" * 60)
    print("meep-kb 회귀 테스트")
    print(f"총 {len(CASES)}개 케이스")
    print("=" * 60)
    
    results = []
    passed = 0
    
    for i, case in enumerate(CASES, 1):
        result = run_test(case)
        results.append(result)
        
        status = "PASS" if result["passed"] else "FAIL"
        if result["passed"]:
            passed += 1
        
        print(f"\n[{i:02d}/{len(CASES)}] {case['id']} — {status} (score={result.get('score', 0):.2f})")
        print(f"       Top: {result.get('top_result', 'N/A')[:60]}")
        
        if VERBOSE or not result["passed"]:
            if result.get("found_keywords"):
                print(f"       ✓ Found: {result['found_keywords']}")
            if result.get("missing_keywords"):
                print(f"       ✗ Missing: {result['missing_keywords']}")
            if result.get("false_positives"):
                print(f"       ⚠ False pos: {result['false_positives']}")
        
        time.sleep(0.3)  # API rate limit
    
    print("\n" + "=" * 60)
    print(f"결과: {passed}/{len(CASES)} PASS ({passed/len(CASES)*100:.0f}%)")
    print("=" * 60)
    
    # 카테고리별 분석
    cat_results = {}
    for r, c in zip(results, CASES):
        cat = c.get("category", "unknown")
        if cat not in cat_results:
            cat_results[cat] = {"pass": 0, "total": 0}
        cat_results[cat]["total"] += 1
        if r["passed"]:
            cat_results[cat]["pass"] += 1
    
    print("\n카테고리별 결과:")
    for cat, r in sorted(cat_results.items()):
        print(f"  {cat:15s}: {r['pass']}/{r['total']}")
    
    # 결과 저장
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(CASES),
        "passed": passed,
        "pass_rate": passed/len(CASES),
        "results": results,
        "category_results": cat_results,
    }
    out_file = Path("tests/regression_result_latest.json")
    out_file.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\n결과 저장: {out_file}")
    
    return 0 if passed >= 15 else 1  # 15/20 이상 목표


if __name__ == "__main__":
    sys.exit(main())
