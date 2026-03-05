"""Phase 2+3 end-to-end test"""
import requests, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = "https://rubi-unmirrored-corruptibly.ngrok-free.dev"

tests = [
    ("adjoint field plot how to",       "Stage 5-2"),
    ("gradient map visualization",      "Stage 5-3"),
    ("MaterialGrid setup",              "Category 3"),
    ("beta scheduling configuration",  "Stage 5-4"),
    ("conic filter length scale",       "Stage 5-5"),
]

for query, expected_tag in tests:
    try:
        resp = requests.post(f"{BASE}/api/chat", json={"message": query}, timeout=90)
        if not resp.ok:
            print(f"FAIL [{query}] HTTP {resp.status_code}")
            continue

        data   = resp.json()
        answer = data.get("answer", "")

        has_header  = "\U0001f4cd" in answer   # 📍
        has_prereq  = "\u26a0" in answer        # ⚠️
        has_footer  = "\u23ed" in answer        # ⏭️
        has_tag     = expected_tag in answer

        ok = "OK" if (has_header and has_footer) else "PARTIAL"
        print(f"\n[{ok}] Query: {query}")
        print(f"  header={has_header}  prereq={has_prereq}  footer={has_footer}  tag={has_tag}")

        lines = answer.split('\n')
        for line in lines[:5]:
            if line.strip():
                print(f"  TOP> {line[:100]}")

        for i, line in enumerate(lines):
            if "\u23ed" in line:
                snippet = "\n  ".join(lines[i:i+3])
                print(f"  FOOTER> {snippet[:250]}")
                break

    except Exception as e:
        print(f"ERROR [{query}]: {e}")
