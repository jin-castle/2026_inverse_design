# -*- coding: utf-8 -*-
"""Phase 1~3 end-to-end API 테스트"""
import sys, requests
sys.stdout.reconfigure(encoding='utf-8')

BASE = "https://rubi-unmirrored-corruptibly.ngrok-free.dev"

TESTS = [
    {
        "query": "adjoint field plot how to use mp.Animate2D",
        "label": "Stage 5-2 (Adjoint)",
        "expect_header": "Stage 5-2",
        "expect_prereq": "Stage 5-1",
        "expect_footer": "Stage 5-3",
    },
    {
        "query": "forward simulation DFT field visualization",
        "label": "Stage 5-1 (Forward)",
        "expect_header": "Stage 5-1",
        "expect_prereq": "Cat.1",
        "expect_footer": "Stage 5-2",
    },
    {
        "query": "MaterialGrid DesignRegion how to setup",
        "label": "Category 3 (DesignRegion)",
        "expect_header": "Category 3",
        "expect_prereq": "Cat.1",
        "expect_footer": "Category 4",
    },
    {
        "query": "beta scheduling tanh projection binarization",
        "label": "Stage 5-4 (Beta)",
        "expect_header": "Stage 5-4",
        "expect_prereq": "Stage 5-1",
        "expect_footer": "Stage 5-5",
    },
    {
        "query": "gradient sensitivity map plot reshape",
        "label": "Stage 5-3 (Gradient)",
        "expect_header": "Stage 5-3",
        "expect_prereq": "Stage 5-2",
        "expect_footer": "Stage 5-4",
    },
]

print("=== Phase 1~3 End-to-End API 테스트 ===\n")
total_ok = 0

for t in TESTS:
    query = t["query"]
    label = t["label"]
    try:
        resp = requests.post(
            f"{BASE}/api/chat",
            json={"message": query},
            timeout=90
        )
        if not resp.ok:
            print(f"[HTTP ERR] {label}: {resp.status_code}")
            continue

        answer = resp.json().get("answer", "")
        sources = resp.json().get("sources_used", 0)

        chk_header  = t["expect_header"] in answer
        chk_prereq  = t["expect_prereq"] in answer
        chk_footer  = t["expect_footer"] in answer
        chk_pin     = "\U0001f4cd" in answer   # 📍
        chk_next    = "\u23ed" in answer        # ⏭️

        all_ok = chk_header and chk_pin and chk_next
        if all_ok:
            total_ok += 1
            status = "PASS"
        else:
            status = "FAIL"

        print(f"[{status}] {label}")
        print(f"  sources={sources}")
        print(f"  pin(header)={chk_pin}  header_tag={chk_header}  prereq={chk_prereq}  footer_tag={chk_footer}  next_arrow={chk_next}")

        # 상단 블록 출력
        lines = answer.split('\n')
        print("  --- 상단 ---")
        for line in lines[:5]:
            if line.strip():
                print(f"  {line[:100]}")

        # 하단 블록 출력
        print("  --- 하단 ---")
        for i, line in enumerate(lines):
            if "\u23ed" in line or "\u2705" in line:
                for l in lines[i:i+4]:
                    print(f"  {l[:100]}")
                break

    except Exception as e:
        print(f"[ERROR] {label}: {e}")

    print()

print(f"=== 결과: {total_ok}/{len(TESTS)} PASS ===")
