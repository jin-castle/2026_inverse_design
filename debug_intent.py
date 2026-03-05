# -*- coding: utf-8 -*-
import sys; sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'agent')
from intent_analyzer import detect_pipeline

# 문제 케이스 재현
queries = [
    "adjoint field plot how to use mp.Animate2D",
    "adjoint simulation 방법",
    "adjoint field visualization",
    "forward simulation DFT field visualization",
]
for q in queries:
    r = detect_pipeline(q)
    print(f"'{q}'")
    print(f"  -> cat={r['pipeline_category']}, stage_idx={r['pipeline_stage_idx']}, stage={r['pipeline_stage']}")
