# -*- coding: utf-8 -*-
"""마지막 2개 패턴 fix"""
import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'db/knowledge.db'
conn = sqlite3.connect(DB_PATH)

# 1. material_grid_adjoint: freq unbound local variable 수정
code = conn.execute(
    "SELECT code_snippet FROM patterns WHERE pattern_name='material_grid_adjoint'"
).fetchone()[0]

# "try:\n                freq = h.modes[0].freq" 앞에 freq = 0.0 기본값 삽입
fixed = re.sub(
    r'(try:\s*\n\s*for m in h\.modes:)',
    'freq = 0.0  # default if no modes found\n            try:\n                for m in h.modes:',
    code
)
if fixed != code:
    conn.execute("UPDATE patterns SET code_snippet=? WHERE pattern_name='material_grid_adjoint'", (fixed,))
    print("[FIXED] material_grid_adjoint: freq 기본값 추가")
else:
    print("[WARN] material_grid_adjoint: 패턴 매칭 실패 - 수동 확인 필요")
    # 라인 찾기
    for i, line in enumerate(code.split('\n'), 1):
        if 'try' in line or 'freq' in line:
            print(f"  {i}: {line}")

conn.commit()
conn.close()
print("Done.")
