# -*- coding: utf-8 -*-
"""material_grid_adjoint - try/except 블록 인덴트 fix"""
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'db/knowledge.db'
conn = sqlite3.connect(DB_PATH)

code = conn.execute(
    "SELECT code_snippet FROM patterns WHERE pattern_name='material_grid_adjoint'"
).fetchone()[0]

lines = code.split('\n')
print("=== 해당 부분 (55~80줄) ===")
for i, line in enumerate(lines[54:80], start=55):
    print(f"{i:3d}: {repr(line)}")
conn.close()
