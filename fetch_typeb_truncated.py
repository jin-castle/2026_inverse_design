# -*- coding: utf-8 -*-
"""Fetch TypeB_truncated example codes from DB"""
import sqlite3
import json

TYPEB_IDS = [269, 412, 428, 569, 597, 598]

conn = sqlite3.connect("/app/db/knowledge.db")

results = {}
for eid in TYPEB_IDS:
    row = conn.execute("SELECT code, title FROM examples WHERE id=?", (eid,)).fetchone()
    if row:
        results[eid] = {
            "code": row[0],
            "title": row[1] if row[1] else ""
        }
        print(f"ID {eid}: {len(row[0])} chars, title={row[1][:60] if row[1] else 'N/A'}")
    else:
        results[eid] = None
        print(f"ID {eid}: NOT FOUND")

conn.close()

out_path = "/tmp/typeb_truncated_codes.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\nFetched {sum(1 for v in results.values() if v)} examples")
