# -*- coding: utf-8 -*-
import sqlite3
import json

conn = sqlite3.connect("/app/db/knowledge.db")

# Check a few examples to understand structure
for eid in [352, 336, 339]:
    row = conn.execute("SELECT code FROM examples WHERE id=?", (eid,)).fetchone()
    if row:
        code = row[0]
        print(f"\n=== ID {eid} - first 100 lines ===")
        lines = code.split('\n')
        for i, line in enumerate(lines[:80]):
            print(f"{i:3d}: {repr(line)[:100]}")

conn.close()
