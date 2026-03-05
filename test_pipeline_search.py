"""Pipeline 패턴 검색 테스트"""
import requests

BASE = "https://rubi-unmirrored-corruptibly.ngrok-free.dev"

queries = [
    "adjoint field DFT plot",
    "어드조인트 필드 플롯",
    "MaterialGrid DesignRegion",
    "gradient map sensitivity",
    "beta scheduling tanh projection",
    "EigenModeSource eig_band",
    "conic filter minimum length scale",
    "forward simulation DFT field",
]

for q in queries:
    try:
        resp = requests.post(f"{BASE}/api/chat", json={"message": q, "n": 5}, timeout=60)
        if resp.ok:
            data = resp.json()
            answer = data.get("answer", "")
            sources = data.get("sources_used", 0)
            # pipeline 패턴 감지
            has_pipeline = any(name in answer for name in [
                "pipeline_cat", "pipeline_stage", "Category 1", "Category 2", "Category 3",
                "Category 4", "Category 5", "Stage 5", "stage51", "stage52"
            ])
            first_line = answer.split('\n')[0] if answer else "(empty)"
            print(f"\nQ: {q}")
            print(f"  sources={sources}  pipeline_hit={has_pipeline}")
            print(f"  first: {first_line[:100]}")
        else:
            print(f"\nQ: {q} -> {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"\nQ: {q} -> ERROR: {e}")
