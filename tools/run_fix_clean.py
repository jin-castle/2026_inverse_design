# -*- coding: utf-8 -*-
"""
verified_fix_v2 배치 실행 - 마크다운 혼재 코드 제외하고 처리
NumericalError 중 original_code에 마크다운이 없는 것만 대상
"""
import sqlite3, subprocess, sys, re
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"

def has_markdown(code: str) -> bool:
    """마크다운 텍스트 혼재 여부 체크"""
    if not code:
        return True
    markers = ["```", "##", "**", "---", ">>>", "In [", "Out[", "# %%"]
    for m in markers:
        if m in code:
            return True
    # import meep 없으면 불완전 코드
    if "import meep" not in code and "import mp" not in code:
        return True
    return False

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row

# 처리 대상: fix_worked=0, Timeout/MPIDeadlockRisk/Unknown 제외, 마크다운 없는 것
rows = conn.execute("""
    SELECT id, error_type, error_class, original_code
    FROM sim_errors_v2
    WHERE fix_worked = 0
      AND error_type NOT IN ('Timeout', 'MPIDeadlockRisk', 'Unknown', '')
      AND original_code IS NOT NULL AND original_code != ''
    ORDER BY 
      CASE error_type
        WHEN 'ImportError' THEN 1
        WHEN 'AttributeError' THEN 2
        WHEN 'TypeError' THEN 3
        WHEN 'PML' THEN 4
        WHEN 'RuntimeError' THEN 5
        WHEN 'NumericalError' THEN 6
        WHEN 'Harminv' THEN 7
        ELSE 8
      END, id
    LIMIT 40
""").fetchall()
conn.close()

# 마크다운 필터링
runnable = [(r["id"], r["error_type"]) for r in rows if not has_markdown(r["original_code"])]
markdown_skip = [(r["id"], r["error_type"]) for r in rows if has_markdown(r["original_code"])]

print(f"전체 대상: {len(rows)}건")
print(f"  실행 가능 (마크다운 없음): {len(runnable)}건")
print(f"  스킵 (마크다운 혼재):     {len(markdown_skip)}건")
print()

for i, (vid, etype) in enumerate(runnable):
    print(f"[{i+1}/{len(runnable)}] id={vid} ({etype}) 처리 중...")
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "tools/verified_fix_v2.py", "--id", str(vid)],
        cwd=str(Path(__file__).parent.parent),
        capture_output=True, text=True, timeout=180
    )
    # 결과 확인
    output = result.stdout + result.stderr
    if "fix_worked=1" in output or "성공" in output or "success" in output.lower():
        print(f"  ✅ 수정 성공")
    elif "실패" in output or "failed" in output.lower() or "FAILED" in output:
        print(f"  ❌ 수정 실패")
    else:
        print(f"  ? 결과 불명확")
    if result.returncode != 0 and result.stderr:
        print(f"  stderr: {result.stderr[:100]}")

# 최종 현황
conn2 = sqlite3.connect(str(DB_PATH))
fw = conn2.execute("SELECT fix_worked, COUNT(*) FROM sim_errors_v2 GROUP BY fix_worked").fetchall()
conn2.close()
print()
print("=== 최종 fix_worked 현황 ===")
for f, c in fw:
    print(f"  fix_worked={f}: {c}건")
