# -*- coding: utf-8 -*-
"""Phase 2 검토: intent_analyzer pipeline 감지 정확도"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'agent')
from intent_analyzer import analyze, detect_pipeline

tests = [
    # (query, expected_category, expected_stage_idx)
    ("adjoint field plot",           "inv_loop",      2),
    ("adjoint simulation 방법",       "inv_loop",      2),
    ("forward simulation DFT field", "inv_loop",      1),
    ("gradient map visualization",   "inv_loop",      3),
    ("beta scheduling 설정",          "inv_loop",      4),
    ("conic filter length scale",    "inv_loop",      5),
    ("MaterialGrid DesignRegion",    "design_region", 0),
    ("EigenModeSource eig_band",     "sim_setup",     0),
    ("resolution PML cell_size",     "env_setup",     0),
    ("geometry Block layout",        "geometry",      0),
    ("convergence plot 저장",         "output",        0),
    ("NaN 에러 발생",                  None,            0),  # 파이프라인 미감지여야 함
]

print("=== Phase 2: Pipeline 감지 테스트 ===\n")
ok_count = 0
for query, exp_cat, exp_stage in tests:
    result = detect_pipeline(query)
    got_cat   = result['pipeline_category']
    got_stage = result['pipeline_stage_idx']
    hit       = result['pipeline_hit']

    cat_ok   = (got_cat == exp_cat)
    stage_ok = (got_stage == exp_stage)
    passed   = cat_ok and stage_ok

    if passed:
        ok_count += 1
        status = "PASS"
    else:
        status = "FAIL"

    print(f"[{status}] '{query}'")
    if not passed:
        print(f"       expected: cat={exp_cat}, stage={exp_stage}")
        print(f"       got:      cat={got_cat}, stage={got_stage}")

print(f"\n결과: {ok_count}/{len(tests)} 통과")

# analyze() 통합 반환값 확인
print("\n=== analyze() 반환값 구조 확인 ===")
r = analyze("adjoint field plot 어떻게", use_llm=False)
required_keys = ['intent','lang','keywords','confidence','pipeline_hit',
                 'pipeline_category','pipeline_stage','pipeline_stage_idx']
missing = [k for k in required_keys if k not in r]
if missing:
    print(f"FAIL: 누락된 키 = {missing}")
else:
    print("PASS: 모든 키 정상 반환")
    for k in required_keys:
        print(f"  {k}: {r[k]}")
