# -*- coding: utf-8 -*-
"""material_grid_adjoint의 design_parameters kwarg 제거 (MEEP 신버전 API 변경)"""
import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'db/knowledge.db'
conn = sqlite3.connect(DB_PATH)

row = conn.execute(
    "SELECT code_snippet FROM patterns WHERE pattern_name='material_grid_adjoint'"
).fetchone()
code = row[0]

# design_parameters=... 인자 제거
# mp.MaterialGrid(..., design_parameters=filtered_design_params, ...) 에서 해당 kwarg 삭제
fixed = re.sub(
    r',\s*design_parameters\s*=\s*\w+',
    '',
    code
)

if fixed != code:
    conn.execute(
        "UPDATE patterns SET code_snippet=? WHERE pattern_name='material_grid_adjoint'",
        (fixed,)
    )
    conn.commit()
    print(f"[FIXED] material_grid_adjoint: design_parameters 제거")
    # 변경 확인
    for i, line in enumerate(fixed.split('\n'), 1):
        if 'MaterialGrid' in line or 'design_param' in line:
            print(f"  {i:3d}: {line}")
else:
    print("[NO CHANGE] design_parameters 패턴 없음")

conn.close()
