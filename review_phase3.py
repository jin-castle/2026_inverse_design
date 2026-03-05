# -*- coding: utf-8 -*-
"""Phase 3 검토: generator pipeline header/footer 로직 단위 테스트"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'agent')

from generator import _build_pipeline_header, _build_next_step_footer, _PREREQUISITES, _NEXT_STEP_PREVIEW

test_intents = [
    {"pipeline_hit": True,  "pipeline_category": "inv_loop",      "pipeline_stage_idx": 2, "pipeline_stage": "adjoint_sim"},
    {"pipeline_hit": True,  "pipeline_category": "inv_loop",      "pipeline_stage_idx": 1, "pipeline_stage": "forward_sim"},
    {"pipeline_hit": True,  "pipeline_category": "design_region", "pipeline_stage_idx": 0, "pipeline_stage": None},
    {"pipeline_hit": True,  "pipeline_category": "sim_setup",     "pipeline_stage_idx": 0, "pipeline_stage": None},
    {"pipeline_hit": True,  "pipeline_category": "inv_loop",      "pipeline_stage_idx": 3, "pipeline_stage": "gradient"},
    {"pipeline_hit": True,  "pipeline_category": "output",        "pipeline_stage_idx": 0, "pipeline_stage": None},
    {"pipeline_hit": False, "pipeline_category": None,            "pipeline_stage_idx": 0, "pipeline_stage": None},
]

print("=== Phase 3: Generator pipeline 블록 테스트 ===\n")

all_ok = True
for intent in test_intents:
    cat  = intent.get('pipeline_category')
    sidx = intent.get('pipeline_stage_idx', 0)
    hit  = intent.get('pipeline_hit')
    label = f"cat={cat}, stage={sidx}, hit={hit}"

    header = _build_pipeline_header(intent)
    footer = _build_next_step_footer(intent)

    if hit:
        has_header = "\U0001f4cd" in header   # 📍
        has_prereq = "\u26a0" in header or len(_PREREQUISITES.get((cat, sidx), [])) == 0
        has_footer = len(footer) > 0

        ok = has_header and has_footer
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False

        print(f"[{status}] {label}")
        print(f"  header_has_pin={has_header}  prereq_ok={has_prereq}  footer_exists={has_footer}")
        # header 첫 줄
        h_line = header.split('\n')[0] if header else ''
        print(f"  header[0]: {h_line[:80]}")
        # footer 첫 줄
        f_line = footer.split('\n')[2] if footer and len(footer.split('\n')) > 2 else footer[:80]
        print(f"  footer[0]: {f_line[:80]}")
    else:
        ok = (header == "" and footer == "")
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"[{status}] pipeline_hit=False -> header='{header[:30]}', footer='{footer[:30]}'")

print(f"\n전체 결과: {'ALL PASS' if all_ok else 'SOME FAIL'}")

# 커버리지 확인
print(f"\n=== 커버리지 ===")
print(f"  PREREQUISITES 항목: {len(_PREREQUISITES)}개")
print(f"  NEXT_STEP_PREVIEW 항목: {len(_NEXT_STEP_PREVIEW)}개")
all_keys = set(_PREREQUISITES.keys()) | set(_NEXT_STEP_PREVIEW.keys())
missing_preview = set(_PREREQUISITES.keys()) - set(_NEXT_STEP_PREVIEW.keys())
if missing_preview:
    print(f"  WARN: preview 없는 key = {missing_preview}")
else:
    print("  모든 prerequisite key에 next_step_preview 매핑됨")
