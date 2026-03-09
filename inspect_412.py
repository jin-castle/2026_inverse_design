# -*- coding: utf-8 -*-
import json

with open(r"/tmp/typeb_truncated_codes.json", "r", encoding="utf-8") as f:
    codes = json.load(f)

code = codes["412"]["code"]
lines = code.split('\n')
print(f"Total lines: {len(lines)}")
for i, ln in enumerate(lines[:30]):
    print(f"{i:3d}: {repr(ln)[:120]}")
