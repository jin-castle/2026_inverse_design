#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

SUMMARY_FILE = Path("/root/autosim/run_summary.json")
data = json.loads(SUMMARY_FILE.read_text())

counts = Counter(r["status"] for r in data)
print("=== run_summary.json 현황 ===")
print(f"OK: {counts['ok']}  ERROR: {counts['error']}  TIMEOUT: {counts['timeout']}  SKIP: {counts['skip']}  Total: {len(data)}")
print()
print("--- NON-OK 목록 ---")
for r in sorted(data, key=lambda x: x["status"]):
    if r["status"] != "ok":
        reason = r.get("skip_reason") or r.get("error") or ""
        print(f"  [{r['status']:8s}] {r['pattern']}")
        if reason:
            print(f"             -> {str(reason)[:100]}")
