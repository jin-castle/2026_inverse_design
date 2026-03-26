import sqlite3, re
from pathlib import Path

DB_PATH = Path("db/knowledge.db")
conn = sqlite3.connect(str(DB_PATH), timeout=15)

for name in ["PML", "Symmetry"]:
    code = conn.execute("SELECT demo_code FROM concepts WHERE name=?", (name,)).fetchone()[0]

    # def f():"""...""" → def f(): (docstring 한 줄 제거)
    # 패턴: def 함수명(...): 뒤에 바로 """..."""가 이어지는 경우
    fixed = re.sub(r'(def \w+\([^)]*\):)\s*"""[^"]*"""', r'\1', code)
    fixed = re.sub(r'(def \w+\([^)]*\):)\s*\'\'\'[^\']*\'\'\'', r'\1', fixed)

    if fixed != code:
        print(f"{name}: docstring 제거 완료")
        conn.execute("UPDATE concepts SET demo_code=? WHERE name=?", (fixed, name))
        conn.commit()
    else:
        print(f"{name}: 패턴 미발견 — 수동 확인 필요")
        # 문제 줄 출력
        for i, l in enumerate(code.splitlines(), 1):
            if 'def ' in l and '"""' in l:
                print(f"  L{i}: {repr(l)}")

conn.close()
