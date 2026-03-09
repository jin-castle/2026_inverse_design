# -*- coding: utf-8 -*-
"""Fetch TypeE example codes from DB and save to files"""
import sqlite3
import json
import os
import sys

TYPEE_IDS = [336,339,340,342,349,352,358,362,368,386,388,395,397,399,403,411,
             507,510,511,514,522,525,533,537,544,570,572,579,581,583,588,599,601]

conn = sqlite3.connect("/app/db/knowledge.db")

results = {}
for eid in TYPEE_IDS:
    row = conn.execute("SELECT code, title FROM examples WHERE id=?", (eid,)).fetchone()
    if row:
        results[eid] = {"code": row[0], "title": row[1] if row[1] else ""}
    else:
        results[eid] = None

conn.close()

out_path = "/tmp/typee_codes.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"Fetched {sum(1 for v in results.values() if v)} / {len(TYPEE_IDS)} examples")
for eid, val in results.items():
    if val:
        code_len = len(val["code"]) if val["code"] else 0
        print(f"  ID {eid}: {code_len} chars - {val['title'][:60]}")
    else:
        print(f"  ID {eid}: NOT FOUND")
